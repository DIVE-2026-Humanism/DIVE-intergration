from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import DERIVED_FEATURES


def _divide(a: pd.Series, b: pd.Series) -> pd.Series:
    result = a / b
    return result.where(b.notna() & b.ne(0)).replace([np.inf, -np.inf], np.nan)


def build_features(df: pd.DataFrame, outdir: Path | None = None) -> pd.DataFrame:
    f = df.copy()
    income = f["추정 연소득"]
    prev = f["2년전 추정 연소득 금액"]
    f["has_verified_income"] = f["증빙연소득"].gt(0).astype("int8")
    f["income_trajectory"] = _divide(income - prev, prev)
    f["income_declined"] = f["income_trajectory"].lt(0).astype("int8")
    f["job_turnover"] = f["2년내 직장명이력건수"]
    f["jeonse_income_multiple"] = _divide(f["2년내 현거주지평균전세거래가"], income)
    f["pir"] = _divide(f["현 거주지의 매매가(국토부 실거래가) 또는 공시가격"], income)
    f["commute_mismatch"] = f["거주지 시군구 코드"].ne(f["근무지 시군구 코드"]).astype("int8")
    f["dsr"] = _divide(f["총 대출 상환금액 (최근 12개월)"], income)
    balances = ["신용대출-총대출잔액", "주택담보대출-총대출잔액", "정책자금대출-총대출잔액"]
    f["total_loan_balance"] = f[balances].sum(axis=1, min_count=len(balances))
    f["avg_loan_balance"] = _divide(f["total_loan_balance"], f["총대출건수"])
    f["multi_debt"] = f["총대출건수"].ge(3).astype("int8")
    f["has_mortgage"] = f["주택담보대출-총대출잔액"].gt(0).astype("int8")
    f["has_policy_loan"] = f["정책자금대출-총대출잔액"].gt(0).astype("int8")
    f["is_owner"] = f["자가거주여부"].ne(3).astype("int8")
    card = f["최근 12개월 신용카드소비금액"] + f["최근 12개월 체크카드소비금액"]
    f["consumption_ratio"] = _divide(card, income)
    f["credit_dependency"] = _divide(f["최근 12개월 신용카드소비금액"], card)
    f["cash_advance_flag"] = f["최근 12개월 현금서비스이용금액"].gt(0).astype("int8")
    f["total_delinq_cnt"] = f["대출연체건수"] + f["카드연체건수"]
    f["delinq_severity"] = _divide(f["대출연체금액"] + f["카드연체금액"], income / 12)
    f["score_floor"] = f["신용평점"].eq(150).astype("int8")
    f["thin_filer"] = f["Thin Filer 여부"].fillna(0).astype("int8")
    if outdir is not None:
        summary = f[DERIVED_FEATURES].describe(percentiles=[.05, .25, .5, .75, .95]).T
        summary["nan_rate"] = f[DERIVED_FEATURES].isna().mean()
        summary.to_csv(outdir / "features_summary.csv", encoding="utf-8-sig")
    return f
