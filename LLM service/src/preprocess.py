from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


def preprocess_main(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = df.copy()
    required = config["columns"]["required"]
    sentinel = float(config["io"]["sentinel"])
    conversion_failures: dict[str, int] = {}
    for column in required:
        original = frame[column]
        # Commas in numeric strings are tolerated, but non-numeric payloads become explicit NaN.
        cleaned = original.astype("string").str.replace(",", "", regex=False).replace("<NA>", pd.NA)
        numeric = pd.to_numeric(cleaned, errors="coerce")
        failures = int(original.notna().sum() - numeric.notna().sum())
        if failures:
            conversion_failures[column] = failures
        frame[column] = numeric.mask(numeric.eq(sentinel), np.nan)
    if conversion_failures:
        LOGGER.warning("Numeric conversion produced NaN values: %s", conversion_failures)

    before = len(frame)
    youth = set(config["filters"]["youth_age_codes"])
    frame = frame[frame["연령대"].isin(youth)]
    after_youth = len(frame)
    busan_prefix = str(config["filters"]["busan_code_prefix"])
    residence = frame["거주지 시군구 코드"].round().astype("Int64").astype("string")
    frame = frame[residence.str.startswith(busan_prefix, na=False)]
    after_busan = len(frame)

    frame = frame.copy()
    frame.insert(0, "_ROW_ID", frame.index.astype(str))
    frame.reset_index(drop=True, inplace=True)
    return frame, {
        "input_rows": before,
        "after_youth": after_youth,
        "after_busan": after_busan,
        "conversion_failures": conversion_failures,
    }
