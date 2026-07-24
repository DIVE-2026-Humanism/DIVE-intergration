from __future__ import annotations

from copy import deepcopy
from datetime import date
import os

import pytest
from pydantic import ValidationError

from src.io_load import load_config
from src.policy_db.ingest import ingest
from src.policy_db.ingest import load_transformed_policies
from src.rule_engine import UserInputs, evaluate_policy, find_eligible_policies, policy_matches


def policy(**updates):
    base = {
        "plcy_no": "P1", "plcy_nm": "정책", "plcy_expln_cn": "설명", "plcy_sprt_cn": "지원",
        "lclsf_nm": "주거", "lclsf_categories": ["주거"], "mclsf_nm": "전월세 및 주거급여 지원",
        "plcy_kywd_nm": ["주거지원"], "pvsn_inst_group_cd": "0054002",
        "sprt_trgt_min_age": 18, "sprt_trgt_max_age": 39, "sprt_trgt_age_lmt": "N",
        "zip_cd": ["26110"], "job_cd": ["0013010"], "school_cd": ["0049010"],
        "plcy_major_cd": ["0011009"], "sbiz_cd": ["0014010"], "mrg_stts_cd": "0055003",
        "earn_cnd_se_cd": "0043001", "earn_min_amt": 0, "earn_max_amt": 0,
        "earn_etc_cn": "", "add_aply_qlfc_cn": "", "ptcp_prp_trgt_cn": "",
        "aply_prd_se_cd": "0057002", "aply_bgng_ymd": None, "aply_end_ymd": None,
        "plcy_aprv_stts_cd": "0044002", "ref_url_addr1": "", "aply_url_addr": "", "raw": {},
    }
    return {**base, **updates}


def user(**updates):
    base = {"성별": "남", "결혼여부": "미혼", "연소득": 30_000_000, "직업군": "재직자", "학력": "대학 졸업", "특화": [], "사는곳": "중구", "나이": 25}
    return UserInputs.model_validate({**base, **updates})


def test_special_region_and_national_rules() -> None:
    female_only = policy(sbiz_cd=["0014002"])
    assert not policy_matches(female_only, user())
    assert policy_matches(female_only, user(성별="여"))
    assert policy_matches(policy(sbiz_cd=["0014010"]), user())
    assert not policy_matches(policy(zip_cd=["26350"]), user())
    assert not policy_matches(policy(zip_cd=["26350"], pvsn_inst_group_cd="0054001"), user())


def test_non_busan_local_government_policy_is_not_confirmed() -> None:
    other_city = policy(
        zip_cd=["26110"],
        pvsn_inst_group_cd="0054002",
        raw={"sprvsnInstCdNm": "전라남도 광양시 미래산업국"},
    )
    decision = evaluate_policy(other_city, user())
    assert decision["status"] == "UNKNOWN"
    assert "부산 기관" in " ".join(decision["unknown"])


def test_income_period_boundaries_and_free_text_passthrough() -> None:
    annual = policy(earn_cnd_se_cd="0043002", earn_min_amt=30_000_000, earn_max_amt=40_000_000)
    decision = evaluate_policy(annual, user(연소득=30_000_000))
    assert decision["status"] == "UNKNOWN"
    assert "공식 단위" in " ".join(decision["unknown"])
    assert not policy_matches(annual, user(연소득=30_000_000))
    assert not policy_matches(policy(aply_prd_se_cd="0057003"), user())
    assert not policy_matches(policy(aply_prd_se_cd="0057001", aply_bgng_ymd=date(2025, 1, 1), aply_end_ymd=date(2025, 12, 31)), user(), today=date(2026, 7, 23))

    text_policy = policy(earn_cnd_se_cd="0043003", earn_etc_cn="중위소득 확인", add_aply_qlfc_cn="무주택", ptcp_prp_trgt_cn="재학생 제외")
    result = find_eligible_policies(user(), config=load_config(), policies=[text_policy], today=date(2026, 7, 23))
    assert result == {"groups": [], "count": 0}


def test_age_is_required() -> None:
    payload = user().model_dump()
    payload.pop("나이")
    with pytest.raises(ValidationError):
        UserInputs.model_validate(payload)


def test_explicit_age_range_is_enforced_without_guessing_flag_semantics() -> None:
    ranged = policy(sprt_trgt_age_lmt="Y", sprt_trgt_min_age=18, sprt_trgt_max_age=39)
    assert evaluate_policy(ranged, user(나이=25))["status"] == "PASS"
    assert evaluate_policy(ranged, user(나이=40))["status"] == "FAIL"


def test_uncollected_major_and_natural_description_are_unknown() -> None:
    major = policy(plcy_major_cd=["0011005"])
    assert evaluate_policy(major, user())["status"] == "UNKNOWN"
    regional_talent = policy(sbiz_cd=["0014008"])
    assert evaluate_policy(regional_talent, user())["status"] == "UNKNOWN"
    internship = policy(plcy_expln_cn="미취업 청년의 경력 형성을 위한 인턴십 지원")
    decision = evaluate_policy(internship, user(직업군="재직자"))
    assert decision["status"] == "UNKNOWN"
    assert "자연어 자격조건" in " ".join(decision["unknown"])


def test_known_dataset_counterexamples_are_not_confirmed() -> None:
    rows, _ = load_transformed_policies(load_config())
    by_name = {row["plcy_nm"]: row for row in rows}
    employed = user(직업군="재직자")
    internship = evaluate_policy(by_name["부산청년 잡(JOB)매칭 인턴사업"], employed)
    assert internship["status"] == "UNKNOWN"
    other_city = evaluate_policy(by_name["(광양시) 청년 일자리 만들기 확대"], employed)
    assert other_city["status"] == "UNKNOWN"
    income = evaluate_policy(by_name["청년주택드림청약통장"], employed)
    assert income["status"] == "UNKNOWN"


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("DIVE_TEST_DATABASE_URL"), reason="PostgreSQL integration DSN not configured")
def test_postgresql_rule_query_matches_real_policy_database() -> None:
    config = deepcopy(load_config())
    config["policy_db"]["dsn_env"] = "DIVE_TEST_DATABASE_URL"
    ingest(config)
    result = find_eligible_policies(user(), config=config, today=date(2026, 7, 23))
    assert result["count"] > 0
    assert {group["대분류"] for group in result["groups"]}.issubset({"일자리", "주거", "교육", "복지문화", "참여권리"})
