from __future__ import annotations

import numpy as np
import pandas as pd

LABEL_NAMES = {
    "V1": "V1 연체·채무조정 위험형",
    "V2": "V2 상환 과부하형",
    "V3": "V3 소득·생활 취약형",
    "S1": "S1 상위소득 여유형",
    "S2": "S2 부채·자산 균형 관리형",
    "S3": "S3 무부채 건전형",
}
CLASS_ORDER = list(LABEL_NAMES)


def _b(condition: pd.Series) -> pd.Series:
    return condition.fillna(False).astype(bool)


def rule_matches(frame: pd.DataFrame, q: dict[str, float]) -> dict[str, pd.Series]:
    level = frame["DELQ_LEVEL"]
    dsr = frame["DSR_PROXY"]
    rel_debt = frame["REL_DEBT"]
    score = frame["신용평점"]
    cash = frame["최근 12개월 현금서비스이용금액"]
    loans = frame["총대출건수"]
    inc_chg = frame["INC_CHG"]
    buffer = frame["BUFFER"].eq(1)
    high = frame["HIGH_INC"].eq(1)
    low = frame["LOW_INC"].eq(1)
    debt_unobs = frame["DEBT_UNOBS"].eq(1)
    cash_heavy = frame["CASH_HEAVY"].eq(1)

    v1 = (
        level.eq(3)
        & (dsr.ge(q["D50"]) | cash.gt(0) | frame["REL_INC"].le(1.0) | score.le(q["C20"]))
        & ~buffer
        & ~high
        & ~level.eq(1)
    )
    v2 = (
        level.isin([0, 1])
        & dsr.ge(q["D80"])
        & (rel_debt.ge(1.0) | cash_heavy)
        & (rel_debt.ge(q["RD80"]) | score.le(q["C50"]))
        & ~high
        & ~buffer
        & ~debt_unobs
        & ~level.eq(3)
    )
    v3 = (
        low
        & level.eq(0)
        & (loans.eq(0) | rel_debt.le(q["RD20"]))
        & (
            frame["CARD_CONSUME_RATIO"].ge(frame["EXT_CARD_RATIO"])
            | cash.gt(0)
            | inc_chg.le(q["IC10"])
        )
        & ~buffer
        & ~score.ge(q["C80"])
        & ~dsr.ge(q["D80"])
        & ~cash_heavy
    )
    s1 = (
        high
        & level.eq(0)
        & cash.eq(0)
        & (loans.eq(0) | dsr.le(q["D50"]))
        & (score.ge(q["C50"]) | (loans.ge(1) & rel_debt.le(1.0)))
        & level.eq(0)
        & ~debt_unobs
    )
    s2 = (
        ((loans.ge(1) & frame["DEBT_SUM"].gt(0) & rel_debt.le(1.0)) | buffer)
        & level.eq(0)
        & dsr.le(q["D50"])
        & score.ge(q["C50"])
        & (cash.eq(0) | inc_chg.ge(0))
        & ~high
        & ~debt_unobs
        & ~inc_chg.le(q["IC10"])
        & ~low
    )
    s3 = (
        loans.eq(0)
        & frame["DEBT_SUM"].eq(0)
        & cash.eq(0)
        & level.eq(0)
        & frame["REL_INC"].ge(1.0)
        & frame["CARD_CONSUME_RATIO"].le(frame["EXT_CARD_RATIO"])
        & (inc_chg.ge(0) | score.ge(q["C50"]))
        & ~high
        & ~inc_chg.le(q["IC10"])
    )
    return {"V1": _b(v1), "V2": _b(v2), "V3": _b(v3), "S1": _b(s1), "S2": _b(s2), "S3": _b(s3)}


def label_dataframe(frame: pd.DataFrame, q: dict[str, float], *, strict_overlap: bool = True) -> pd.DataFrame:
    matches = rule_matches(frame, q)
    match_table = pd.DataFrame(matches, index=frame.index)
    match_count = match_table.sum(axis=1).astype(int)

    missing_key = frame[["추정 연소득", "대출연체건수", "카드연체건수", "총대출건수"]].isna().any(axis=1)
    thin = frame["Thin Filer 여부"].eq(1)
    vulnerable_signals = pd.DataFrame(
        {
            "severe": frame["DELQ_LEVEL"].eq(3),
            "high_dsr": frame["DSR_PROXY"].ge(q["D80"]),
            "low_income": frame["LOW_INC"].eq(1),
            "cash_heavy": frame["CASH_HEAVY"].eq(1),
            "income_drop": frame["INC_CHG"].le(q["IC10"]),
        }
    ).fillna(False).any(axis=1)
    stable_signals = pd.DataFrame(
        {
            "high_income": frame["HIGH_INC"].eq(1),
            "buffer": frame["BUFFER"].eq(1),
            "clean_strong_credit": frame["DELQ_LEVEL"].eq(0) & frame["신용평점"].ge(q["C80"]) & frame["DSR_PROXY"].le(q["D50"]),
        }
    ).fillna(False).any(axis=1)
    mixed = vulnerable_signals & stable_signals

    eligible = ~missing_key & ~thin & ~mixed
    effective_matches = match_table.mul(eligible, axis=0)
    effective_count = effective_matches.sum(axis=1).astype(int)
    overlaps = effective_count.gt(1)
    if strict_overlap and overlaps.any():
        examples = frame.loc[overlaps, ["_ROW_ID"]].head(10).to_dict("records") if "_ROW_ID" in frame else list(frame.index[overlaps][:10])
        raise ValueError(f"Rule contract failed: {int(overlaps.sum())} rows match multiple types. Examples: {examples}")

    label = pd.Series(pd.NA, index=frame.index, dtype="string")
    for code in CLASS_ORDER:
        label.loc[eligible & effective_matches[code] & label.isna()] = code
    reason = pd.Series(pd.NA, index=frame.index, dtype="string")
    reason.loc[missing_key] = "MISSING_KEY"
    reason.loc[~missing_key & thin] = "THIN"
    reason.loc[~missing_key & ~thin & mixed] = "MIXED"
    unclassified = label.isna() & reason.isna()
    reason.loc[unclassified & frame["DEBT_UNOBS"].eq(1)] = "DEBT_UNOBS"
    reason.loc[reason.isna() & label.isna()] = "NO_MATCH"

    output = pd.DataFrame(index=frame.index)
    if "_ROW_ID" in frame:
        output["_ROW_ID"] = frame["_ROW_ID"]
    output["LABEL"] = label
    output["LABEL_NAME"] = label.map(LABEL_NAMES)
    output["MAJOR_CLASS"] = np.where(label.str.startswith("V", na=False), "경제적 취약 청년", np.where(label.str.startswith("S", na=False), "경제적 안정 청년", pd.NA))
    output["HOLDOUT_REASON"] = reason
    output["RAW_MATCH_COUNT"] = match_count
    output["EFFECTIVE_MATCH_COUNT"] = effective_count
    output["RAW_MATCHES"] = match_table.apply(lambda row: ",".join(row.index[row].tolist()), axis=1)
    output["MIXED_SIGNAL"] = mixed.astype("int8")
    return output
