from __future__ import annotations

import pandas as pd
import pytest

from src.features import build_base_features, finalize_features
from src.io_load import load_config
from src.labeling import label_dataframe
from src.preprocess import preprocess_main


QUANTILES = {
    "D50": 0.1,
    "D80": 0.5,
    "RD80": 1.2,
    "C20": 650,
    "C50": 750,
    "C80": 850,
    "NW50": 150000,
    "IC10": -0.2,
    "DLQ25": 7,
    "DLQ75": 45,
    "RD20": 0.4,
}


def _record(**overrides):
    config = load_config()
    row = {column: 0 for column in config["columns"]["required"]}
    row.update(
        {
            "연령대": 25,
            "거주지 시군구 코드": 26110,
            "추정 연소득": 28110,
            "2년전 추정 연소득 금액": 25000,
            "신용평점": 800,
            "Thin Filer 여부": 0,
            "추정가구원수": 1,
        }
    )
    row.update(overrides)
    return row


def _features(**overrides):
    config = load_config()
    raw = pd.DataFrame([_record(**overrides)])
    processed, _ = preprocess_main(raw, config)
    return build_base_features(processed, config)


def test_feature_calculation_uses_controlled_values() -> None:
    features = _features(
        총대출건수=1,
        **{
            "신용대출-총대출잔액": 10000,
            "주택담보대출-총대출잔액": 20000,
            "정책자금대출-총대출잔액": 8600,
            "총 대출 상환금액 (최근 12개월)": 2811,
            "최근 12개월 신용카드소비금액": 4000,
            "최근 12개월 체크카드소비금액": 1622,
        },
    )
    row = features.iloc[0]
    assert row.REL_INC == pytest.approx(1.0)
    assert row.INC_CHG == pytest.approx(0.1244, abs=5e-5)
    assert row.DEBT_SUM == 38600
    assert row.REL_DEBT == pytest.approx(1.0)
    assert row.DSR_PROXY == pytest.approx(0.1)
    assert row.CARD_CONSUME_RATIO == pytest.approx(0.2)
    assert row.DEBT_UNOBS == 0


def test_preprocessing_keeps_non_one_person_households() -> None:
    config = load_config()
    processed, stats = preprocess_main(pd.DataFrame([_record(**{"추정가구원수": 2})]), config)
    assert len(processed) == 1
    assert processed.loc[0, "추정가구원수"] == 2
    assert set(stats) == {"input_rows", "after_youth", "after_busan", "conversion_failures"}


def test_unobserved_debt_is_held_out() -> None:
    base = _features(총대출건수=1, **{"2년전 추정 연소득 금액": 28110})
    labels = label_dataframe(finalize_features(base, QUANTILES), QUANTILES)
    assert labels.loc[0, "HOLDOUT_REASON"] == "DEBT_UNOBS"
    assert pd.isna(labels.loc[0, "LABEL"])


def test_bankruptcy_is_severe_even_without_delinquency_count() -> None:
    base = _features(**{"파산, 개인회생 신청 여부": 1})
    features = finalize_features(base, QUANTILES)
    assert features.loc[0, "DELQ_LEVEL"] == 3
