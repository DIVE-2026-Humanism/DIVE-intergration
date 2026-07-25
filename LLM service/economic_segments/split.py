from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split


def split_labels(df: pd.DataFrame, seed: int) -> pd.Series:
    stratify = df["연령대"].astype("Int64").astype(str) + "_" + df["성별"].astype("Int64").astype(str)
    train_idx, temp_idx = train_test_split(df.index, test_size=.30, random_state=seed, stratify=stratify)
    valid_idx, test_idx = train_test_split(temp_idx, test_size=.50, random_state=seed, stratify=stratify.loc[temp_idx])
    result = pd.Series(index=df.index, dtype="string")
    result.loc[train_idx] = "train"
    result.loc[valid_idx] = "valid"
    result.loc[test_idx] = "test"
    return result
