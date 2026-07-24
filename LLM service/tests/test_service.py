from __future__ import annotations

from src.io_load import load_config
from src.service import diagnose


def open_policy():
    return {
        "plcy_no": "P1", "plcy_nm": "청년 지원", "plcy_expln_cn": "", "plcy_sprt_cn": "",
        "lclsf_nm": "복지문화", "lclsf_categories": ["복지문화"], "mclsf_nm": "취약계층 및 금융지원",
        "plcy_kywd_nm": [], "pvsn_inst_group_cd": "0054002", "sprt_trgt_min_age": 18,
        "sprt_trgt_max_age": 39, "sprt_trgt_age_lmt": "N", "zip_cd": ["26110"],
        "job_cd": ["0013010"], "school_cd": ["0049010"], "plcy_major_cd": ["0011009"],
        "sbiz_cd": ["0014010"], "mrg_stts_cd": "0055003", "earn_cnd_se_cd": "0043001",
        "earn_min_amt": 0, "earn_max_amt": 0, "earn_etc_cn": "", "add_aply_qlfc_cn": "",
        "ptcp_prp_trgt_cn": "", "aply_prd_se_cd": "0057002", "aply_bgng_ymd": None,
        "aply_end_ymd": None, "plcy_aprv_stts_cd": "0044002", "ref_url_addr1": "", "aply_url_addr": "", "raw": {},
    }


def base_user():
    return {"성별": "남", "결혼여부": "미혼", "연소득": 31_410_000, "직업군": "재직자", "학력": "대학 졸업", "특화": [], "사는곳": "중구", "나이": 27}


def complete_kcb(**updates):
    config = load_config()
    record = {column: 0 for column in config["columns"]["required"]}
    record.update({"연령대": 35, "거주지 시군구 코드": 26110, "근무지 시군구 코드": 26110, "추정가구원수": 1})
    return {**record, **updates}


def stable_classification():
    return {
        "대분류": "안정", "유형": "경제적 안정 청년", "세부유형코드": "S3",
        "확률": {"V1": 0.05, "V2": 0.05, "V3": 0.1, "S1": 0.1, "S2": 0.2, "S3": 0.5},
        "유형확률": {"경제적 취약 청년": 0.2, "경제적 안정 청년": 0.8}, "유형점수": 80.0,
        "안정점수": 80.0, "불안정점수": 20.0, "신뢰주의": False,
    }


def test_light_contract_returns_policy_and_income_feedback() -> None:
    config = load_config()
    config["local_llm"]["enabled"] = False
    result = diagnose({"mode": "light", "user_inputs": base_user()}, config=config, policies=[open_policy()])
    assert result["유형"] is None and result["안정점수"] is None
    assert result["지원가능정책"][0]["정책"][0]["plcyNo"] == "P1"
    assert result["추천정책"] == []
    assert result["추천상태"] == "미사용"
    assert result["추천방식"] == "없음"
    assert result["분류상태"] == "미사용"
    assert result["소비피드백"]["분석모드"] == "light"
    assert result["모델결과"] is None
    assert "연령확인필요" not in result
    assert "정책판정요약" not in result
    assert "확인필요정책" not in result


def test_precise_contract_uses_model_result(monkeypatch) -> None:
    kcb = complete_kcb(**{"연령대": 35, "추정 연소득": 30_000})
    config = load_config()
    config["local_llm"]["enabled"] = False
    observed = {}

    def classify_record(record, cfg):
        observed.update(record)
        return stable_classification()

    monkeypatch.setattr("src.service.classify", classify_record)
    result = diagnose({"mode": "precise", "user_inputs": base_user(), "kcb_record": kcb}, config=config, policies=[open_policy()])
    assert result["유형"] == "경제적 안정 청년"
    assert result["유형점수"] == 80.0
    assert result["세부유형코드"] == "S3"
    assert result["안정점수"] + result["불안정점수"] == 100.0
    assert result["신뢰주의"] is False
    assert result["분류상태"] == "완료"
    assert result["모델결과"]["type_code"] == "S3"
    assert result["추천정책"][0]["plcyNo"] == "P1"
    assert result["소비피드백"]["주거지원_우선"] is True
    assert observed["연령대"] == 25


def test_precise_model_failure_still_returns_policy_recommendation(monkeypatch) -> None:
    kcb = complete_kcb(**{
        "연령대": 35,
        "추정 연소득": 39_916,
        "최근 12개월 신용카드소비금액": 15_755,
        "최근 12개월 체크카드소비금액": 5_469,
        "총대출건수": 2,
        "신용대출-총대출잔액": 0,
        "주택담보대출-총대출잔액": 0,
        "정책자금대출-총대출잔액": 0,
        "Thin Filer 여부": 0,
        "신용평점": 670,
        "추정가구원수": 1,
    })
    config = load_config()
    config["local_llm"]["enabled"] = False

    def missing_model(record, cfg):
        raise FileNotFoundError("분류 아티팩트가 없습니다")

    monkeypatch.setattr("src.service.classify", missing_model)
    result = diagnose(
        {"mode": "precise", "user_inputs": base_user(), "kcb_record": kcb},
        config=config,
        policies=[open_policy()],
    )
    assert result["유형"] is None
    assert result["분류상태"] == "사용불가"
    assert result["진단상태"] == "부분완료"
    assert result["분류오류코드"] == "MODEL_ARTIFACTS_MISSING"
    assert "아티팩트" in result["분류오류"]
    assert result["추천정책"][0]["plcyNo"] == "P1"
    assert result["추천방식"] == "규칙기반대체"


def test_light_never_calls_llm() -> None:
    def broken_llm(system: str, user: str) -> str:
        raise RuntimeError("Ollama unavailable")

    result = diagnose(
        {"mode": "light", "user_inputs": base_user()},
        config=load_config(),
        policies=[open_policy()],
        llm_callable=broken_llm,
    )
    assert result["추천정책"] == []
    assert result["추천방식"] == "없음"
    assert result["추천오류"] is None


def test_no_eligible_policy_is_reported_without_fabrication() -> None:
    config = load_config()
    config["local_llm"]["enabled"] = False
    result = diagnose(
        {"mode": "light", "user_inputs": base_user()},
        config=config,
        policies=[],
    )
    assert result["추천정책"] == []
    assert result["추천상태"] == "미사용"
    assert result["추천방식"] == "없음"


def test_unknown_policy_is_not_exposed_or_recommended_as_eligible() -> None:
    config = load_config()
    config["local_llm"]["enabled"] = False
    natural = {**open_policy(), "plcy_expln_cn": "미취업 청년만 신청 가능"}
    result = diagnose(
        {"mode": "light", "user_inputs": base_user()},
        config=config,
        policies=[natural],
    )
    assert result["지원가능정책"] == []
    assert result["추천정책"] == []
    assert result["추천상태"] == "미사용"


def test_non_one_person_record_is_still_diagnosed_and_recommended(monkeypatch) -> None:
    monkeypatch.setattr("src.service.classify", lambda record, cfg: stable_classification())
    result = diagnose(
        {"mode": "precise", "user_inputs": base_user(), "kcb_record": complete_kcb(**{"추정가구원수": 2})},
        config=load_config(),
        policies=[open_policy()],
    )
    assert result["진단상태"] == "완료"
    assert result["분류상태"] == "완료"
    assert result["추천정책"][0]["plcyNo"] == "P1"
    assert result["소비피드백"]["1인가구여부"] is False
    assert result["소비피드백"]["1인가구상세가이드"] == []
