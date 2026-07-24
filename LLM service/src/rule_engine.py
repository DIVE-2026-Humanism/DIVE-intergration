from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .io_load import load_config
from .policy_db.ingest import database_dsn

MRG = {"기혼": "0055001", "미혼": "0055002"}
JOB_MAP = {
    "재직자": "0013001", "자영업자": "0013002", "미취업자": "0013003",
    "프리랜서": "0013004", "일용근로자": "0013005", "(예비)창업자": "0013006",
    "단기근로자": "0013007", "영농종사자": "0013008", "기타": "0013009",
}
SCHOOL_MAP = {
    "고졸 미만": "0049001", "고교 재학": "0049002", "고졸 예정": "0049003",
    "고교 졸업": "0049004", "대학 재학": "0049005", "대졸 예정": "0049006",
    "대학 졸업": "0049007", "석·박사": "0049008", "기타": "0049009",
}
SBIZ = {"여성": "0014002", "기초생활수급자": "0014003", "한부모가정": "0014004", "장애인": "0014005", "군인": "0014007"}
GU_CODE = {
    "중구": "26110", "서구": "26140", "동구": "26170", "영도구": "26200",
    "부산진구": "26230", "동래구": "26260", "남구": "26290", "북구": "26320",
    "해운대구": "26350", "사하구": "26380", "금정구": "26410", "강서구": "26440",
    "연제구": "26470", "수영구": "26500", "사상구": "26530", "기장군": "26710",
}
NO_LIMIT = {"job": "0013010", "school": "0049010", "major": "0011009", "sbiz": "0014010", "mrg": "0055003"}
CATEGORY_ORDER = ["일자리", "주거", "교육", "복지문화", "참여권리"]
JobType = Literal["재직자", "자영업자", "미취업자", "프리랜서", "일용근로자", "(예비)창업자", "단기근로자", "영농종사자", "기타"]
SchoolType = Literal["고졸 미만", "고교 재학", "고졸 예정", "고교 졸업", "대학 재학", "대졸 예정", "대학 졸업", "석·박사", "기타"]
SpecialType = Literal["기초생활수급자", "한부모가정", "장애인", "군인"]
DistrictType = Literal["중구", "서구", "동구", "영도구", "부산진구", "동래구", "남구", "북구", "해운대구", "사하구", "금정구", "강서구", "연제구", "수영구", "사상구", "기장군"]


class UserInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    성별: Literal["남", "여"]
    결혼여부: Literal["기혼", "미혼"]
    연소득: int = Field(ge=0)
    직업군: JobType
    학력: SchoolType
    특화: list[SpecialType] = Field(default_factory=list)
    사는곳: DistrictType
    나이: int = Field(ge=0, le=120)

    @field_validator("직업군")
    @classmethod
    def validate_job(cls, value: str) -> str:
        if value not in JOB_MAP:
            raise ValueError(f"지원하지 않는 직업군입니다: {value}")
        return value

    @field_validator("학력")
    @classmethod
    def validate_school(cls, value: str) -> str:
        if value not in SCHOOL_MAP:
            raise ValueError(f"지원하지 않는 학력입니다: {value}")
        return value

    @field_validator("사는곳")
    @classmethod
    def validate_gu(cls, value: str) -> str:
        if value not in GU_CODE:
            raise ValueError(f"부산 구·군 이름을 확인하세요: {value}")
        return value

    @field_validator("특화")
    @classmethod
    def validate_special(cls, value: list[str]) -> list[str]:
        invalid = sorted(set(value) - (set(SBIZ) - {"여성"}))
        if invalid:
            raise ValueError(f"지원하지 않는 특화 조건입니다: {invalid}")
        return list(dict.fromkeys(value))


POLICY_SELECT_SQL = """
SELECT plcy_no, plcy_nm, plcy_expln_cn, plcy_sprt_cn, lclsf_nm, mclsf_nm,
       plcy_kywd_nm, pvsn_inst_group_cd, sprt_trgt_min_age, sprt_trgt_max_age,
       sprt_trgt_age_lmt, zip_cd, job_cd, school_cd, plcy_major_cd, sbiz_cd,
       mrg_stts_cd, earn_cnd_se_cd, earn_min_amt, earn_max_amt, earn_etc_cn,
       add_aply_qlfc_cn, ptcp_prp_trgt_cn, aply_prd_se_cd, aply_bgng_ymd,
       aply_end_ymd, plcy_aprv_stts_cd, ref_url_addr1, aply_url_addr, raw
FROM busan_policies
WHERE plcy_aprv_stts_cd = '0044002'
"""

EligibilityStatus = Literal["PASS", "UNKNOWN", "FAIL"]

# 전용 자연어요건 필드가 비어 있어도 설명문에 명백한 자격 표현이 들어간 정책이 있다.
# 의미를 LLM으로 확정하지 않고 확인 필요(UNKNOWN)로만 내리기 위한 보수적 탐지식이다.
NATURAL_REQUIREMENT_PATTERN = re.compile(
    r"미취업|무주택|중위소득|4\s*대\s*보험|소득\s*(?:월|연)?\s*[\d,]+\s*만?\s*원|"
    r"(?:이하|이상)\s*(?:인|인 자|청년)|취[·\s-]*창업\s*\d+\s*년\s*이내|"
    r"(?:신용|복지)\s*조건|근로[·\s]?사업소득|구직단념|예비\s*창업|창업[자가]|"
    r"입사자|신입직원|해외일경험\s*참여|귀농귀촌\s*희망",
)


def _user_codes(user: UserInputs) -> dict[str, Any]:
    special = [SBIZ[item] for item in user.특화]
    if user.성별 == "여":
        special.append(SBIZ["여성"])
    return {
        "mrg": MRG[user.결혼여부],
        "job": [JOB_MAP[user.직업군]],
        "school": [SCHOOL_MAP[user.학력]],
        "user_sbiz": list(dict.fromkeys(special)),
        "sigungu": [GU_CODE[user.사는곳]],
    }


def _date_value(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def evaluate_policy(
    policy: dict[str, Any],
    user: UserInputs,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """정책을 PASS/UNKNOWN/FAIL로 판정하고 근거를 남긴다.

    코드북으로 의미를 확인할 수 있는 정형 조건만 확정 판정한다. 단위가 정의되지
    않은 소득 금액과 자연어 조건은 신청 가능으로 추측하지 않는다.
    """
    today = today or date.today()
    codes = _user_codes(user)
    passed: list[str] = []
    unknown: list[str] = []
    failed: list[str] = []

    if policy.get("plcy_aprv_stts_cd") != "0044002":
        failed.append("승인된 정책이 아님")

    minimum = policy.get("sprt_trgt_min_age")
    maximum = policy.get("sprt_trgt_max_age")
    has_age_range = any(value not in (None, 0) for value in (minimum, maximum))
    if has_age_range:
        if minimum is None or maximum is None:
            unknown.append("정책의 연령 범위가 불완전함")
        elif minimum <= user.나이 <= maximum:
            passed.append(f"연령 범위 일치({minimum}~{maximum}세)")
        else:
            failed.append(f"연령 범위 불일치({minimum}~{maximum}세)")

    if policy.get("mrg_stts_cd") not in {NO_LIMIT["mrg"], codes["mrg"]}:
        failed.append("결혼 상태 불일치")
    else:
        passed.append("결혼 상태 일치")

    job_codes = set(policy.get("job_cd") or [])
    school_codes = set(policy.get("school_cd") or [])
    sbiz_codes = set(policy.get("sbiz_cd") or [])
    if NO_LIMIT["job"] not in job_codes and not job_codes.intersection(codes["job"]):
        failed.append("직업 요건 불일치")
    else:
        passed.append("직업 요건 일치")
    if NO_LIMIT["school"] not in school_codes and not school_codes.intersection(codes["school"]):
        failed.append("학력 요건 불일치")
    else:
        passed.append("학력 요건 일치")
    supported_sbiz_codes = set(SBIZ.values())
    uncollected_sbiz_codes = sbiz_codes - supported_sbiz_codes - {NO_LIMIT["sbiz"]}
    if NO_LIMIT["sbiz"] in sbiz_codes or sbiz_codes.intersection(codes["user_sbiz"]):
        passed.append("특화 요건 일치")
    elif uncollected_sbiz_codes:
        unknown.append("현재 입력으로 확인할 수 없는 특화 요건 확인 필요")
    else:
        failed.append("특화 요건 불일치")

    zip_codes = set(policy.get("zip_cd") or [])
    if not zip_codes:
        unknown.append("정책 대상지역 코드가 없어 지역 확인 필요")
    elif not zip_codes.intersection(codes["sigungu"]):
        failed.append("거주지역 요건 불일치")
    else:
        passed.append("거주지역 요건 일치")
    if policy.get("pvsn_inst_group_cd") == "0054002":
        raw = policy.get("raw") if isinstance(policy.get("raw"), dict) else {}
        institution_text = " ".join(
            str(raw.get(key) or "")
            for key in ("rgtrInstCdNm", "rgtrHghrkInstCdNm", "sprvsnInstCdNm", "operInstCdNm")
        ).strip()
        if institution_text and "부산" not in institution_text:
            unknown.append("지자체 제공기관이 부산 기관인지 확인 필요")

    major_codes = set(policy.get("plcy_major_cd") or [])
    if major_codes and NO_LIMIT["major"] not in major_codes:
        unknown.append("사용자 전공 정보가 없어 전공 요건 확인 필요")

    income_type = policy.get("earn_cnd_se_cd")
    if income_type == "0043002":
        unknown.append("정책 소득금액의 공식 단위가 없어 연소득 요건 확인 필요")
    elif income_type == "0043003":
        unknown.append("자연어 소득 요건 확인 필요")
    elif income_type == "0043001":
        passed.append("정형 소득 제한 없음")
    else:
        unknown.append("소득조건 코드 의미 확인 필요")

    period = policy.get("aply_prd_se_cd")
    if period == "0057001":
        start = _date_value(policy.get("aply_bgng_ymd"))
        end = _date_value(policy.get("aply_end_ymd"))
        if (start and today < start) or (end and today > end):
            failed.append("현재 신청기간이 아님")
        elif start is None or end is None:
            unknown.append("신청기간 날짜 확인 필요")
        else:
            passed.append("신청기간 일치")
    elif period == "0057002":
        passed.append("상시 신청 정책")
    elif period == "0057003":
        failed.append("신청 마감 정책")
    else:
        unknown.append("신청기간 코드 확인 필요")

    natural_fields = {
        "소득기타": str(policy.get("earn_etc_cn") or "").strip(),
        "추가자격": str(policy.get("add_aply_qlfc_cn") or "").strip(),
        "제외대상": str(policy.get("ptcp_prp_trgt_cn") or "").strip(),
    }
    for label, value in natural_fields.items():
        if value:
            unknown.append(f"{label} 자연어 조건 확인 필요")
    descriptive_text = " ".join(
        (str(policy.get("plcy_expln_cn") or ""), str(policy.get("plcy_sprt_cn") or ""))
    )
    if not any(natural_fields.values()) and NATURAL_REQUIREMENT_PATTERN.search(descriptive_text):
        unknown.append("정책 설명·지원내용의 자연어 자격조건 확인 필요")

    if failed:
        status: EligibilityStatus = "FAIL"
    elif unknown:
        status = "UNKNOWN"
    else:
        status = "PASS"
    return {"status": status, "passed": passed, "unknown": unknown, "failed": failed}


def policy_matches(policy: dict[str, Any], user: UserInputs, *, today: date | None = None) -> bool:
    """하위 호환용: 확정적으로 PASS인 정책에만 True를 반환한다."""
    return evaluate_policy(policy, user, today=today)["status"] == "PASS"


def _public_policy(row: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    categories = row.get("lclsf_categories") or [item for item in str(row.get("lclsf_nm") or "").split(",") if item]
    return {
        "plcyNo": row.get("plcy_no"),
        "plcyNm": row.get("plcy_nm"),
        "대분류": categories,
        "중분류": row.get("mclsf_nm"),
        "키워드": row.get("plcy_kywd_nm") or [],
        "설명": row.get("plcy_expln_cn") or "",
        "지원내용": row.get("plcy_sprt_cn") or "",
        "소득기타": row.get("earn_etc_cn") or "",
        "추가자격": row.get("add_aply_qlfc_cn") or "",
        "제외대상": row.get("ptcp_prp_trgt_cn") or "",
        "신청시작일": _date_value(row.get("aply_bgng_ymd")).isoformat() if _date_value(row.get("aply_bgng_ymd")) else None,
        "신청종료일": _date_value(row.get("aply_end_ymd")).isoformat() if _date_value(row.get("aply_end_ymd")) else None,
        "참고URL": row.get("ref_url_addr1") or None,
        "신청URL": row.get("aply_url_addr") or None,
        "자격판정": decision["status"],
        "판정근거": decision["passed"],
    }


def _fetch_db_policies(config: dict[str, Any]) -> list[dict[str, Any]]:
    with psycopg.connect(database_dsn(config), row_factory=dict_row) as connection:
        rows = [dict(row) for row in connection.execute(POLICY_SELECT_SQL).fetchall()]
    for row in rows:
        row["lclsf_categories"] = [item for item in row["lclsf_nm"].split(",") if item]
    return rows


def find_eligible_policies(
    user_inputs: UserInputs | dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    policies: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    user = user_inputs if isinstance(user_inputs, UserInputs) else UserInputs.model_validate(user_inputs)
    today = today or date.today()
    if policies is None:
        candidates = _fetch_db_policies(config)
    else:
        candidates = policies

    decisions = [(row, evaluate_policy(row, user, today=today)) for row in candidates]
    eligible = [
        _public_policy(row, decision)
        for row, decision in decisions
        if decision["status"] == "PASS"
    ]

    def grouped(public: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for category in CATEGORY_ORDER:
            items = [policy for policy in public if category in policy["대분류"]]
            if items:
                groups.append({"대분류": category, "정책": items})
        return groups

    return {
        "groups": grouped(eligible),
        "count": len(eligible),
    }
