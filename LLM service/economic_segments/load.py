from __future__ import annotations

import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .config import REQUIRED_COLUMNS, SENTINEL, TARGET_ROWS


def load_csv(path: Path) -> tuple[pd.DataFrame, dict]:
    errors = []
    for encoding in ("utf-8-sig", "cp949"):
        try:
            frame = pd.read_csv(path, encoding=encoding)
            break
        except UnicodeDecodeError as exc:
            errors.append(str(exc))
    else:
        raise UnicodeError(f"CSV decoding failed: {errors}")
    frame.columns = [unicodedata.normalize("NFC", str(c).strip()) for c in frame.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in frame]
    if missing:
        raise ValueError(f"Required columns missing: {missing}")
    if len(frame) != TARGET_ROWS:
        warnings.warn(f"Expected {TARGET_ROWS:,} rows, received {len(frame):,}")
    frame = frame[REQUIRED_COLUMNS].copy()
    frame.insert(0, "row_id", np.arange(len(frame), dtype=np.int64))
    numeric = [c for c in REQUIRED_COLUMNS]
    sentinel_counts = {}
    for column in numeric:
        series = pd.to_numeric(frame[column], errors="coerce")
        sentinel_counts[column] = int(series.eq(SENTINEL).sum())
        frame[column] = series.mask(series.eq(SENTINEL))
        # Keep a stable inference schema: every source column gets a missingness
        # indicator even when the training file happens to contain no sentinel.
        frame[f"{column}__missing"] = frame[column].isna().astype("int8")
    ratio = (frame["추정월소득"] * 12 / frame["추정 연소득"].replace(0, np.nan)).describe()
    return frame, {
        "path": str(path.resolve()), "encoding": encoding, "rows": len(frame),
        "sentinel_counts": sentinel_counts,
        "monthly_annual_ratio": {k: float(v) for k, v in ratio.items()},
    }
