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
    "income_to_median", "income_percentile_busan", "income_trajectory", "job_turnover",
    "jeonse_income_multiple", "pir",
    "dsr", "total_loan_balance", "avg_loan_balance",
    "consumption_ratio", "credit_dependency",
    "total_delinq_cnt", "delinq_severity",
]
DERIVED_FLAGS = [
    "policy_eligible_by_income", "self_employed", "no_stable_job", "no_housing_record",
    "has_verified_income", "income_declined", "commute_mismatch",
    "multi_debt", "has_mortgage", "has_policy_loan", "is_owner",
    "cash_advance_flag", "score_floor", "thin_filer",
]
DERIVED_ALL = DERIVED_NUMERIC + DERIVED_FLAGS


def busan_income_percentile(annual_thousand: pd.Series) -> pd.Series:
    """부산 청년 소득 분포(외부 통계) 대비 백분위 0~100.

    KCB 추정 연소득(천원/년)을 만원/월로 환산한 뒤, 구간별 비율의 누적분포에 선형보간한다.
    표본 내부 분위수가 아니라 **실제 부산 청년**이 비교군이라는 점이 핵심이다.
    """
    monthly_manwon = pd.to_numeric(annual_thousand, errors="coerce") / 12 / 10
    cum = np.cumsum([0.0] + list(C.BUSAN_YOUTH_INCOME_BAND_SHARES))
    pct = np.interp(monthly_manwon.to_numpy(dtype=float),
                    C.BUSAN_YOUTH_INCOME_BAND_EDGES, cum)
    return pd.Series(pct, index=annual_thousand.index).where(monthly_manwon.notna())


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    """분모가 0 또는 NaN이면 NaN."""
    den = den.where((den != 0) & den.notna())
    return num / den


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    income = out[C.COL_INCOME_Y]
    income_prev = out[C.COL_INCOME_Y_PREV]

    # 8.0 정책 기준 대비 소득 위치 (외부 절대 기준 — 분위수 원칙의 유일한 예외, config 참조)
    out["income_to_median"] = income / C.MEDIAN_INCOME_ANNUAL_THOUSAND
    out["income_grade"] = pd.cut(
        out["income_to_median"], bins=C.INCOME_GRADE_EDGES,
        labels=C.INCOME_GRADE_LABELS, right=True, include_lowest=True,
    )
    out["policy_eligible_by_income"] = (
        out["income_grade"].isin(C.POLICY_ELIGIBLE_GRADES).astype("int8")
    )
    # 부산 청년 소득 분포 대비 백분위 (외부 기준 — 표본이 아닌 실제 부산 청년이 비교군)
    out["income_percentile_busan"] = busan_income_percentile(income)

    # 8.1 소득 · 고용
    out["has_verified_income"] = (out[C.COL_INCOME_VERIFIED] > 0).astype("int8")
    out["income_trajectory"] = _safe_div(income - income_prev, income_prev)
    out["income_declined"] = (out["income_trajectory"] < 0).astype("float").where(
        out["income_trajectory"].notna()
    )
    out["job_turnover"] = out[C.COL_JOB_HIST]

    # 고용형태 (코드북 확보로 사용 가능 — 정의서 [코드] 시트)
    out["self_employed"] = out[C.COL_JOB].isin(C.JOB_SELF_EMPLOYED).astype("int8")
    out["no_stable_job"] = out[C.COL_JOB].isin(C.JOB_NONE).astype("int8")
    out["job_name"] = out[C.COL_JOB].map(C.JOB_CODE_NAMES)
    out["employment_type"] = out[C.COL_JOB].map(C.EMPLOYMENT_TYPE)
    out["region_name"] = out[C.COL_REGION_HOME].map(C.REGION_NAMES)

    # 8.2 주거
    # `2년내 현거주지평균전세거래가` 결측 = 해당 주소지에 최근 2년간 실거래 신고 기록이 없음(정의서).
    # 전수 검증 결과 결측군은 비아파트 거주 71.9% vs 아파트 58.9%, 소득 -6.0%, 신용평점 -31점으로
    # 실제 취약 신호다(method.md §16-1 가설 확인). 대체값으로 덮이지 않도록 정식 변수로 승격한다.
    out["no_housing_record"] = out["jeonse_imputed"].astype("int8")
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
    out["is_owner"] = (out[C.COL_OWNERSHIP] == C.OWNERSHIP_SELF).astype("int8")

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
