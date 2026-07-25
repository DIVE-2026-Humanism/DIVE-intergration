"""STEP 4 — 파생변수 (method.md §8).

분모가 0 또는 NaN이면 결과는 NaN. 0으로 채우지 않는다.
§4.2 열 제거에 따라 연쇄 폐기된 파생변수(housing_equity_ratio, job_change_return,
downward_move, credit_limit_util, installment_ratio, irregular_income_ratio)는 정의하지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

DERIVED_NUMERIC = [
    "income_trajectory", "job_turnover",
    "jeonse_income_multiple", "pir",
    "dsr", "total_loan_balance", "avg_loan_balance",
    "consumption_ratio", "credit_dependency",
    "total_delinq_cnt", "delinq_severity",
]
DERIVED_FLAGS = [
    "has_verified_income", "income_declined", "commute_mismatch",
    "multi_debt", "has_mortgage", "has_policy_loan", "is_owner",
    "cash_advance_flag", "score_floor", "thin_filer",
]
DERIVED_ALL = DERIVED_NUMERIC + DERIVED_FLAGS


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    """분모가 0 또는 NaN이면 NaN."""
    den = den.where((den != 0) & den.notna())
    return num / den


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    income = out[C.COL_INCOME_Y]
    income_prev = out[C.COL_INCOME_Y_PREV]

    # 8.1 소득 · 고용
    out["has_verified_income"] = (out[C.COL_INCOME_VERIFIED] > 0).astype("int8")
    out["income_trajectory"] = _safe_div(income - income_prev, income_prev)
    out["income_declined"] = (out["income_trajectory"] < 0).astype("float").where(
        out["income_trajectory"].notna()
    )
    out["job_turnover"] = out[C.COL_JOB_HIST]

    # 8.2 주거
    out["jeonse_income_multiple"] = _safe_div(out["jeonse_value"], income)
    out["pir"] = _safe_div(out[C.COL_HOME_PRICE], income)
    out["commute_mismatch"] = (
        out[C.COL_REGION_HOME] != out[C.COL_REGION_WORK]
    ).astype("int8")

    # 8.3 부채 · 상환
    out["dsr"] = _safe_div(out[C.COL_REPAY_12M], income)
    balances = [C.COL_CREDIT_BAL, C.COL_MORT_BAL, C.COL_POLICY_BAL]
    out["total_loan_balance"] = out[balances].sum(axis=1, min_count=1)
    out["avg_loan_balance"] = _safe_div(out["total_loan_balance"], out[C.COL_LOAN_CNT])
    out["multi_debt"] = (out[C.COL_LOAN_CNT] >= 3).astype("int8")
    out["has_mortgage"] = (out[C.COL_MORT_BAL] > 0).astype("int8")
    out["has_policy_loan"] = (out[C.COL_POLICY_BAL] > 0).astype("int8")
    out["is_owner"] = (out[C.COL_OWNERSHIP] != 3).astype("int8")

    # 8.4 소비 · 유동성
    card_sum = out[[C.COL_CARD_CREDIT, C.COL_CARD_CHECK]].sum(axis=1, min_count=1)
    out["consumption_ratio"] = _safe_div(card_sum, income)
    out["credit_dependency"] = _safe_div(out[C.COL_CARD_CREDIT], card_sum)
    out["cash_advance_flag"] = (out[C.COL_CASH_ADVANCE] > 0).astype("int8")

    # 8.5 신용 · 연체
    out["total_delinq_cnt"] = out[[C.COL_DELINQ_LOAN_CNT, C.COL_DELINQ_CARD_CNT]].sum(
        axis=1, min_count=1
    )
    delinq_amt = out[[C.COL_DELINQ_LOAN_AMT, C.COL_DELINQ_CARD_AMT]].sum(axis=1, min_count=1)
    out["delinq_severity"] = _safe_div(delinq_amt, income / 12)
    out["score_floor"] = (out[C.COL_SCORE] == 150).astype("int8")
    out["thin_filer"] = out[C.COL_THIN].fillna(0).astype("int8")

    return out


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in DERIVED_ALL:
        s = pd.to_numeric(df[col], errors="coerce")
        rows.append(
            {
                "variable": col,
                "n": int(s.notna().sum()),
                "nan_rate": float(s.isna().mean()),
                "mean": float(s.mean()),
                "std": float(s.std()),
                "min": float(s.min()),
                "p25": float(s.quantile(0.25)),
                "median": float(s.median()),
                "p75": float(s.quantile(0.75)),
                "p95": float(s.quantile(0.95)),
                "max": float(s.max()),
            }
        )
    return pd.DataFrame(rows)
