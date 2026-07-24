from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from ..io_load import ROOT, load_config

LOGGER = logging.getLogger(__name__)
MULTI_FIELDS = {
    "plcyKywdNm": "plcy_kywd_nm",
    "zipCd": "zip_cd",
    "jobCd": "job_cd",
    "schoolCd": "school_cd",
    "plcyMajorCd": "plcy_major_cd",
    "sbizCd": "sbiz_cd",
}
DATE_RANGE = re.compile(r"^\s*(\d{8})\s*~\s*(\d{8})\s*$")


def split_multi(value: Any) -> list[str]:
    if value is None:
        return []
    result: list[str] = []
    for item in str(value).split(","):
        clean = item.strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def parse_application_dates(value: Any) -> tuple[date | None, date | None]:
    match = DATE_RANGE.fullmatch(str(value or ""))
    if not match:
        return None, None
    try:
        parsed = [datetime.strptime(item, "%Y%m%d").date() for item in match.groups()]
        return parsed[0], parsed[1]
    except ValueError:
        return None, None


def normalize_categories(value: Any, normalization: dict[str, str]) -> list[str]:
    categories: list[str] = []
    for item in split_multi(value):
        normalized = normalization.get(item, item)
        if normalized and normalized not in categories:
            categories.append(normalized)
    return categories


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    clean = str(value).strip().replace(",", "")
    if not clean:
        return None
    try:
        return int(float(clean))
    except ValueError:
        return None


def transform_policy(policy: dict[str, Any], codebook: dict[str, Any]) -> dict[str, Any]:
    start, end = parse_application_dates(policy.get("aplyYmd"))
    normalization = codebook.get("lclsfNm", {}).get("_normalize", {})
    categories = normalize_categories(policy.get("lclsfNm"), normalization)
    row: dict[str, Any] = {
        "plcy_no": str(policy.get("plcyNo") or "").strip(),
        "plcy_nm": str(policy.get("plcyNm") or "").strip(),
        "plcy_expln_cn": str(policy.get("plcyExplnCn") or "").strip(),
        "plcy_sprt_cn": str(policy.get("plcySprtCn") or "").strip(),
        "lclsf_nm": ",".join(categories),
        "lclsf_categories": categories,
        "mclsf_nm": str(policy.get("mclsfNm") or "").strip(),
        "pvsn_inst_group_cd": str(policy.get("pvsnInstGroupCd") or "").strip(),
        "sprt_trgt_min_age": _optional_int(policy.get("sprtTrgtMinAge")),
        "sprt_trgt_max_age": _optional_int(policy.get("sprtTrgtMaxAge")),
        "sprt_trgt_age_lmt": str(policy.get("sprtTrgtAgeLmtYn") or "").strip(),
        "mrg_stts_cd": str(policy.get("mrgSttsCd") or "").strip(),
        "earn_cnd_se_cd": str(policy.get("earnCndSeCd") or "").strip(),
        "earn_min_amt": _optional_int(policy.get("earnMinAmt")),
        "earn_max_amt": _optional_int(policy.get("earnMaxAmt")),
        "earn_etc_cn": str(policy.get("earnEtcCn") or "").strip(),
        "add_aply_qlfc_cn": str(policy.get("addAplyQlfcCndCn") or "").strip(),
        "ptcp_prp_trgt_cn": str(policy.get("ptcpPrpTrgtCn") or "").strip(),
        "aply_prd_se_cd": str(policy.get("aplyPrdSeCd") or "").strip(),
        "aply_bgng_ymd": start,
        "aply_end_ymd": end,
        "plcy_aprv_stts_cd": str(policy.get("plcyAprvSttsCd") or "").strip(),
        "ref_url_addr1": str(policy.get("refUrlAddr1") or "").strip(),
        "aply_url_addr": str(policy.get("aplyUrlAddr") or "").strip(),
        "raw": policy,
    }
    for source, target in MULTI_FIELDS.items():
        row[target] = split_multi(policy.get(source))
    return row


def _dataset_path(config: dict[str, Any], key: str) -> Path:
    return ROOT / config["project"]["dataset_dir"] / config["paths"][key]


def database_dsn(config: dict[str, Any]) -> str:
    env_name = str(config["policy_db"].get("dsn_env", "DIVE_DATABASE_URL"))
    dsn = os.getenv(env_name) or config["policy_db"].get("dsn")
    if not dsn:
        raise RuntimeError(f"PostgreSQL 연결 문자열이 없습니다. 환경변수 {env_name}을 설정하세요.")
    if not str(dsn).startswith(("postgresql://", "postgres://")):
        raise ValueError("정책 DB는 PostgreSQL DSN만 허용합니다.")
    return str(dsn)


def load_transformed_policies(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    source = json.loads(_dataset_path(config, "policy_json").read_text(encoding="utf-8"))
    codebook = json.loads(_dataset_path(config, "codebook_json").read_text(encoding="utf-8"))
    retained = [transform_policy(item, codebook) for item in source if item.get("aplyPrdSeCd") != "0057003"]
    return retained, {"source": len(source), "excluded_closed": len(source) - len(retained), "loaded": len(retained)}


def iter_code_labels(codebook: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    for group, mapping in codebook.items():
        if group.startswith("_") or not isinstance(mapping, dict):
            continue
        for code, label in mapping.items():
            if not code.startswith("_") and isinstance(label, str):
                yield group, code, label


def _postgres_value(key: str, value: Any) -> Any:
    return Jsonb(value) if key == "raw" else value


def ingest(config: dict[str, Any]) -> dict[str, int]:
    policies, stats = load_transformed_policies(config)
    if not policies:
        raise ValueError("적재할 정책이 없습니다.")
    codebook = json.loads(_dataset_path(config, "codebook_json").read_text(encoding="utf-8"))
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    columns = [key for key in policies[0] if key != "lclsf_categories"]
    insert_sql = sql.SQL("INSERT INTO busan_policies ({}) VALUES ({})").format(
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with psycopg.connect(database_dsn(config)) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('dive_policy_ingest'))")
        connection.execute(schema)
        connection.execute("TRUNCATE TABLE busan_policies, code_labels, policy_meta")
        with connection.cursor() as cursor:
            cursor.executemany(
                insert_sql,
                [[_postgres_value(key, row[key]) for key in columns] for row in policies],
            )
            cursor.executemany(
                "INSERT INTO code_labels (group_name, code, label) VALUES (%s, %s, %s)",
                list(iter_code_labels(codebook)),
            )
            cursor.executemany(
                "INSERT INTO policy_meta (key, value) VALUES (%s, %s)",
                [(key, str(value)) for key, value in stats.items()],
            )
    LOGGER.info("PostgreSQL 정책 DB 적재 완료: %s", stats)
    return stats


def database_counts(config: dict[str, Any]) -> dict[str, int]:
    with psycopg.connect(database_dsn(config)) as connection:
        return {
            "policies": int(connection.execute("SELECT COUNT(*) FROM busan_policies").fetchone()[0]),
            "code_labels": int(connection.execute("SELECT COUNT(*) FROM code_labels").fetchone()[0]),
        }


def database_is_ready(config: dict[str, Any]) -> bool:
    try:
        with psycopg.connect(database_dsn(config), connect_timeout=3) as connection:
            counts = connection.execute(
                "SELECT (SELECT COUNT(*) FROM busan_policies), (SELECT COUNT(*) FROM code_labels)"
            ).fetchone()
            if counts is None or int(counts[0]) <= 0 or int(counts[1]) <= 0:
                return False
        return True
    except (psycopg.Error, RuntimeError, TypeError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="부산 청년정책 PostgreSQL DB 적재")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 변환 건수만 확인")
    args = parser.parse_args()
    config = load_config(args.config)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.dry_run:
        _, stats = load_transformed_policies(config)
    else:
        stats = ingest(config)
        stats.update(database_counts(config))
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
