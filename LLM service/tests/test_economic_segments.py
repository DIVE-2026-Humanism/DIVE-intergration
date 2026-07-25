from __future__ import annotations

import numpy as np
import pandas as pd

from economic_segments.features import _divide
from economic_segments.full_questionnaire import predict_full_questionnaire
from economic_segments.load import load_csv
from economic_segments.config import REQUIRED_COLUMNS
from economic_segments.reduced_model import _edges, _questions
from economic_segments.split import split_labels


def test_safe_divide_keeps_invalid_denominator_missing():
    result = _divide(pd.Series([2.0, 2.0, 2.0]), pd.Series([1.0, 0.0, np.nan]))
    assert result.iloc[0] == 2.0
    assert result.iloc[1:].isna().all()


def test_split_is_reproducible_and_complete():
    frame = pd.DataFrame({
        "연령대": np.repeat([20, 25], 50),
        "성별": np.tile(np.repeat([1, 2], 25), 2),
    })
    first = split_labels(frame, 42)
    second = split_labels(frame, 42)
    assert first.equals(second)
    assert first.notna().all()
    assert first.value_counts().to_dict() == {"train": 70, "valid": 15, "test": 15}


def test_load_always_emits_missingness_flags(tmp_path):
    source = pd.DataFrame([{column: 1 for column in REQUIRED_COLUMNS}])
    path = tmp_path / "input.csv"
    source.to_csv(path, index=False, encoding="utf-8-sig")
    frame, _ = load_csv(path)
    assert all(f"{column}__missing" in frame for column in REQUIRED_COLUMNS)
    assert frame.filter(like="__missing").to_numpy().sum() == 0


def test_reduced_debt_band_uses_credit_balance_and_loan_count():
    frame = pd.DataFrame({
        "연령대": [20, 20], "성별": [1, 1], "거주지 시군구 코드": [1, 1],
        "추정 연소득": [100, 100], "2년내 현거주지평균전세거래가": [100, 100],
        "신용대출-총대출잔액": [0, 100], "총대출건수": [0, 2],
        "job_turnover": [0, 0], "cash_advance_flag": [0, 0], "total_delinq_cnt": [0, 0],
    })
    bins = {
        "income_band": _edges(frame["추정 연소득"]),
        "housing_cost_band": _edges(frame["2년내 현거주지평균전세거래가"]),
        "debt_band": _edges(frame["신용대출-총대출잔액"]),
    }
    questions = _questions(frame, bins)
    assert questions.loc[0, "debt_band"] != questions.loc[1, "debt_band"]


def test_full_questionnaire_respects_special_precedence_and_quadrants():
    frame = pd.DataFrame({
        "파산, 개인회생 신청 여부": [1, 0, 0, 0, 0, 0],
        "thin_filer": [1, 1, 0, 0, 0, 0],
        "총대출건수": [0, 0, 1, 1, 1, 1],
        "score_floor": [1, 1, 0, 0, 0, 0],
        "financial_stress_score": [0, 0, 49, 51, 49, 51],
        "employment_instability_score": [0, 0, 49, 49, 51, 51],
    })
    assert predict_full_questionnaire(frame, 50, 50).tolist() == [
        "T6", "T5", "T1", "T2", "T3", "T4"
    ]
