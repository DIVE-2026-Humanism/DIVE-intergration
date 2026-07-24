from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .external import configured_anchors

MODEL_FEATURES = [
    "추정 연소득",
    "REL_INC",
    "INC_CHG",
    "DEBT_SUM",
    "REL_DEBT",
    "DSR_PROXY",
    "최근 12개월 현금서비스이용금액",
    "CARD_CONSUME_RATIO",
    "DELQ_LEVEL",
    "신용평점",
    "총대출건수",
    "BUFFER",
]

REDUCED_FEATURES = [
    feature
    for feature in MODEL_FEATURES
    if feature not in {"DELQ_LEVEL", "REL_INC", "DSR_PROXY", "REL_DEBT"}
]

DEBT_BALANCE_COLUMNS = [
    "신용대출-총대출잔액",
    "주택담보대출-총대출잔액",
    "정책자금대출-총대출잔액",
]


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    valid = numerator.notna() & denominator.notna() & denominator.gt(0)
    output = pd.Series(np.nan, index=numerator.index, dtype=float)
    output.loc[valid] = numerator.loc[valid] / denominator.loc[valid]
    return output


def build_base_features(
    df: pd.DataFrame,
    config: dict[str, Any],
    *,
    anchor_scale: float = 1.0,
) -> pd.DataFrame:
    """Build features that do not depend on train-derived quantiles."""
    frame = df.copy()
    anchors, debt_anchors = configured_anchors(config, scale=anchor_scale)
    amount_scale = float(config["external"]["amount_scale_to_kcb"])
    age = frame["연령대"].astype("Int64")
    ext_inc = age.map({key: value["inc"] * amount_scale for key, value in anchors.items()})
    ext_q1 = age.map({key: value["q1"] * amount_scale for key, value in anchors.items()})
    ext_q5 = age.map({key: value["q5"] * amount_scale for key, value in anchors.items()})
    ext_card = age.map({key: value["card"] * amount_scale for key, value in anchors.items()})
    ext_debt = age.map({key: value * amount_scale for key, value in debt_anchors.items()})

    income = frame["추정 연소득"].astype(float)
    previous_income = frame["2년전 추정 연소득 금액"].astype(float)
    frame["EXT_INC"] = ext_inc.astype(float)
    frame["EXT_Q1"] = ext_q1.astype(float)
    frame["EXT_Q5"] = ext_q5.astype(float)
    frame["EXT_CARD"] = ext_card.astype(float)
    frame["EXT_DEBT"] = ext_debt.astype(float)
    frame["EXT_CARD_RATIO"] = _safe_divide(ext_card.astype(float), ext_inc.astype(float))
    frame["REL_INC"] = _safe_divide(income, ext_inc.astype(float))
    frame["INC_CHG"] = _safe_divide(income - previous_income, previous_income)
    frame["INC_CHG_NA"] = frame["INC_CHG"].isna().astype("int8")

    balances = frame[DEBT_BALANCE_COLUMNS].astype(float)
    complete_balance = balances.notna().all(axis=1)
    frame["DEBT_SUM"] = balances.sum(axis=1).where(complete_balance)
    loan_count = frame["총대출건수"].astype(float)
    observable_debt = loan_count.ge(1) & frame["DEBT_SUM"].gt(0)
    frame["REL_DEBT"] = _safe_divide(frame["DEBT_SUM"], ext_debt.astype(float)).where(observable_debt)
    frame["DEBT_UNOBS"] = (loan_count.ge(1) & frame["DEBT_SUM"].eq(0)).astype("int8")

    repayment = frame["총 대출 상환금액 (최근 12개월)"].astype(float)
    frame["DSR_PROXY"] = _safe_divide(repayment, income)
    cash = frame["최근 12개월 현금서비스이용금액"].astype(float)
    frame["CASH_HEAVY"] = (cash.notna() & income.gt(0) & cash.ge(income / 12.0)).astype("int8")
    card_total = frame["최근 12개월 신용카드소비금액"].astype(float) + frame["최근 12개월 체크카드소비금액"].astype(float)
    card_total = card_total.where(frame[["최근 12개월 신용카드소비금액", "최근 12개월 체크카드소비금액"]].notna().all(axis=1))
    frame["CARD_CONSUME_RATIO"] = _safe_divide(card_total, income)

    thin = frame["Thin Filer 여부"].eq(1)
    frame.loc[thin, "신용평점"] = np.nan
    frame["SCORE_NA"] = frame["신용평점"].isna().astype("int8")
    mortgage = frame["주택담보대출-총대출잔액"].astype(float)
    frame["OWNER"] = (frame["자가거주여부"].eq(1) | mortgage.gt(0)).astype("int8")
    frame["LOW_INC"] = (income.notna() & ext_q1.notna() & income.le(ext_q1)).astype("int8")
    frame["HIGH_INC"] = (income.notna() & ext_q5.notna() & income.ge(ext_q5)).astype("int8")

    delinquency_counts = frame[["대출연체건수", "카드연체건수"]].astype(float)
    delinquency_amounts = frame[["대출연체금액", "카드연체금액"]].astype(float)
    frame["DELQ_COUNT"] = delinquency_counts.sum(axis=1).where(delinquency_counts.notna().all(axis=1))
    frame["DELQ_AMOUNT"] = delinquency_amounts.sum(axis=1).where(delinquency_amounts.notna().all(axis=1))
    return frame


def finalize_features(base: pd.DataFrame, quantiles: dict[str, float]) -> pd.DataFrame:
    frame = base.copy()
    counts = frame["DELQ_COUNT"]
    amounts = frame["DELQ_AMOUNT"]
    days = frame["연체일수"].astype(float)
    monthly_income = frame["추정 연소득"].astype(float) / 12.0
    bankruptcy = frame["파산, 개인회생 신청 여부"].eq(1)

    level = pd.Series(np.nan, index=frame.index, dtype=float)
    level.loc[counts.eq(0)] = 0
    delinquent = counts.gt(0)
    severe = bankruptcy | (
        delinquent
        & (
            counts.ge(2)
            | (amounts.notna() & monthly_income.gt(0) & amounts.ge(monthly_income))
            | (days.notna() & days.ge(quantiles["DLQ75"]))
        )
    )
    minor = delinquent & ~severe & counts.eq(1) & amounts.lt(monthly_income) & days.le(quantiles["DLQ25"])
    medium = delinquent & ~severe & ~minor
    level.loc[minor] = 1
    level.loc[medium] = 2
    level.loc[severe] = 3
    frame["DELQ_LEVEL"] = level

    owner = frame["OWNER"].eq(1)
    net_worth = frame["순자산평가금액(주택)"].astype(float)
    frame["BUFFER"] = np.nan
    frame.loc[owner, "BUFFER"] = (net_worth.loc[owner].notna() & net_worth.loc[owner].ge(quantiles["NW50"])).astype(float)
    return frame
