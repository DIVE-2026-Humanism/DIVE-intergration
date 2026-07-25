"""STEP 2 — 데이터 분할 (method.md §6).

train 70 / valid 15 / test 15, stratify = 연령대 × 성별.
이 지점 이후 모든 통계량(분위수·경계·중앙값·모델 파라미터)은 train에서만 산출한다.
"""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from . import config as C


def assign_split(df: pd.DataFrame, seed: int = C.SEED) -> pd.DataFrame:
    strata = df[C.COL_AGE].astype(str) + "_" + df[C.COL_GENDER].astype(str)

    # 층이 너무 작으면 stratify가 실패하므로 3건 미만 층은 하나로 묶는다.
    counts = strata.value_counts()
    rare = counts[counts < 3].index
    strata = strata.where(~strata.isin(rare), "__rare__")

    idx = df.index.to_numpy()
    train_idx, rest_idx = train_test_split(
        idx,
        train_size=C.SPLIT_RATIO["train"],
        random_state=seed,
        stratify=strata.to_numpy(),
    )
    rest_strata = strata.loc[rest_idx].to_numpy()
    valid_share = C.SPLIT_RATIO["valid"] / (C.SPLIT_RATIO["valid"] + C.SPLIT_RATIO["test"])
    valid_idx, test_idx = train_test_split(
        rest_idx,
        train_size=valid_share,
        random_state=seed,
        stratify=rest_strata,
    )

    out = df.copy()
    out["split"] = "train"
    out.loc[valid_idx, "split"] = "valid"
    out.loc[test_idx, "split"] = "test"
    return out


def split_summary(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    s = df["split"].value_counts().rename("count").to_frame()
    s["share"] = s["count"] / n
    return s.reindex(["train", "valid", "test"])
