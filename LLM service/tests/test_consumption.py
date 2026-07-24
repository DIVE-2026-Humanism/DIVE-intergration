from __future__ import annotations

from src.consumption import feedback
from src.io_load import load_config


def precise_record(**updates):
    base = {
        "연령대": 25, "추정 연소득": 30_921, "최근 12개월 신용카드소비금액": 10_000,
        "최근 12개월 체크카드소비금액": 4_050, "총대출건수": 1,
        "신용대출-총대출잔액": 38_600, "주택담보대출-총대출잔액": 0,
        "정책자금대출-총대출잔액": 0, "Thin Filer 여부": 0, "신용평점": 800,
        "추정가구원수": 1, "2년내 현거주지평균전세거래가": -99999999,
    }
    return {**base, **updates}


def test_precise_gaps_and_one_person_housing_feedback() -> None:
    result = feedback(
        precise_record(), user_inputs={"사는곳": "중구"}, config=load_config(),
        credit_benchmarks={25: {"mean": 800, "q20": 700, "q50": 800, "q80": 900}},
    )
    items = {item["지표"]: item for item in result["items"]}
    assert items["연소득"]["격차%"] == 10.0
    assert items["월 카드소비"]["격차%"] == 0.0
    assert items["대출잔액"]["격차%"] == 0.0
    assert items["신용평점"]["격차%"] == 0.0
    assert result["1인가구여부"] is True
    assert result["주거지원_우선"] is True
    assert result["주거피드백"]["상태"] == "데이터_미확보"
    assert "구군평균" not in items["연소득"]
    assert items["연소득"]["출처"]
    assert len(result["1인가구상세가이드"]) >= 4


def test_no_loan_thin_and_sentinel_are_excluded() -> None:
    result = feedback(
        precise_record(**{"총대출건수": 0, "Thin Filer 여부": 1, "최근 12개월 신용카드소비금액": -99999999}),
        user_inputs={"사는곳": "중구"}, config=load_config(),
        credit_benchmarks={25: {"mean": 800, "q20": 700, "q50": 800, "q80": 900}},
    )
    names = {item["지표"] for item in result["items"]}
    assert "대출잔액" not in names
    assert "신용평점" not in names
    assert "월 카드소비" not in names


def test_light_uses_required_age_for_income_comparison() -> None:
    result = feedback(None, user_inputs={"연소득": 28_110_000, "나이": 27}, config=load_config())
    assert [item["지표"] for item in result["items"]] == ["연소득"]
    assert result["items"][0]["격차%"] == 0.0
    assert "입력 나이" in result["items"][0]["기준설명"]
    assert result["1인가구여부"] is None


def test_missing_household_column_is_unknown_not_false() -> None:
    record = precise_record()
    record.pop("추정가구원수")
    result = feedback(record, user_inputs={"사는곳": "중구"}, config=load_config())
    assert result["1인가구여부"] is None
    assert result["1인가구확인상태"] == "입력컬럼_없음"
