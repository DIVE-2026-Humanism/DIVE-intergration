from __future__ import annotations

import fnmatch
import json
import logging
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


class SchemaContractError(ValueError):
    """Raised when the main input violates its required schema contract."""


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else ROOT / "config" / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    return config


def normalized_glob(directory: str | Path, pattern: str) -> list[Path]:
    """Match paths after NFC normalization so NFD Korean filenames are found."""
    directory = Path(directory)
    normalized_pattern = unicodedata.normalize("NFC", pattern)
    return sorted(
        path
        for path in directory.iterdir()
        if fnmatch.fnmatch(unicodedata.normalize("NFC", path.name), normalized_pattern)
    )


def resolve_single(directory: str | Path, pattern: str) -> Path:
    paths = normalized_glob(directory, pattern)
    if not paths:
        raise FileNotFoundError(f"NFC-normalized glob matched no file: {directory}/{pattern}")
    if len(paths) > 1:
        LOGGER.warning("Multiple files matched %s; selecting newest: %s", pattern, [p.name for p in paths])
        paths.sort(key=lambda p: (p.stat().st_mtime_ns, p.name))
    return paths[-1]


def read_csv_fallback(path: str | Path, encodings: list[str] | tuple[str, ...]) -> tuple[pd.DataFrame, str]:
    errors: list[str] = []
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise UnicodeError(f"CSV decoding failed for {path}; tried {encodings}. Details: {' | '.join(errors)}")


def validate_schema(df: pd.DataFrame, required: list[str]) -> list[str]:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise SchemaContractError(
            "Main data schema contract failed. Missing required columns: " + ", ".join(missing)
        )
    extras = [column for column in df.columns if column not in required]
    if extras:
        LOGGER.warning("Additional main-data columns are allowed and logged: %s", extras)
    return extras


def load_main(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    dataset_dir = ROOT / config["project"]["dataset_dir"]
    path = resolve_single(dataset_dir, config["paths"]["main_csv"])
    df, encoding = read_csv_fallback(path, config["io"]["csv_encodings"])
    df.columns = [unicodedata.normalize("NFC", str(column).strip()) for column in df.columns]
    extras = validate_schema(df, config["columns"]["required"])
    return df, {"path": str(path), "encoding": encoding, "extras": extras}


def _dataframe_profile(df: pd.DataFrame, sentinel: float) -> list[str]:
    lines = [f"- 행수: {len(df):,}", f"- 열수: {len(df.columns):,}", "", "| 컬럼 | dtype | 결측 | 센티널 | 최솟값 | 최댓값 | 고유값 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for column in df.columns:
        series = df[column]
        numeric = pd.to_numeric(series, errors="coerce")
        sentinel_count = int(numeric.eq(sentinel).sum())
        clean = numeric.mask(numeric.eq(sentinel))
        min_value = "-" if clean.dropna().empty else f"{clean.min():.6g}"
        max_value = "-" if clean.dropna().empty else f"{clean.max():.6g}"
        lines.append(
            f"| {column} | {series.dtype} | {int(series.isna().sum()):,} | {sentinel_count:,} | {min_value} | {max_value} | {series.nunique(dropna=True):,} |"
        )
    return lines


def write_data_profile(config: dict[str, Any]) -> Path:
    report_path = ROOT / config["project"]["reports_dir"] / "data_profile.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    main_df, main_meta = load_main(config)
    lines = ["# 데이터 프로파일", "", "## 메인 KCB 입력", "", f"- 파일: `{main_meta['path']}`", f"- 감지 인코딩: `{main_meta['encoding']}`", f"- 추가 컬럼: `{main_meta['extras'] or '없음'}`", ""]
    lines.extend(_dataframe_profile(main_df, config["io"]["sentinel"]))
    suspicious = [
        "`자가거주여부`와 `직업군` 코드값을 대회 당일 정의서와 대조한다.",
        "개인 ID·시점 컬럼 유무에 따라 교차검증 분할 방식이 달라진다.",
        "가구소득 통계는 개인소득과 직접 비교하지 않고 대표성 교차검증에만 사용한다.",
    ]
    lines.extend(["## 확인 필요", "", *[f"- {item}" for item in suspicious], ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
