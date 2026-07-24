from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .io_load import ROOT, read_csv_fallback, resolve_single

LOGGER = logging.getLogger(__name__)
AGE_ROW_TO_CODES = {"18~24세": (18, 20), "25~29세": (25,), "30~34세": (30,), "35~39세": (35,)}


@lru_cache(maxsize=8)
def _read_raw_cached(path_text: str, encodings: tuple[str, ...], modified_ns: int) -> pd.DataFrame:
    del modified_ns
    path = Path(path_text)
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding, header=None)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Cannot decode external statistics file: {path}")


def _read_raw(config: dict[str, Any], path_key: str) -> pd.DataFrame:
    dataset_dir = ROOT / config["project"]["dataset_dir"]
    path = resolve_single(dataset_dir, config["paths"][path_key])
    return _read_raw_cached(
        str(path), tuple(config["io"]["csv_encodings"]), path.stat().st_mtime_ns
    ).copy()


def parse_income_card(config: dict[str, Any]) -> dict[int, dict[str, float]]:
    frame = _read_raw(config, "income_card_glob")
    parsed: dict[int, dict[str, float]] = {}
    for _, row in frame.iloc[3:].iterrows():
        label = str(row.iloc[1]).strip()
        if label not in AGE_ROW_TO_CODES:
            continue
        values = {"inc": float(row.iloc[2]), "q1": float(row.iloc[3]), "q5": float(row.iloc[7]), "card": float(row.iloc[8])}
        for code in AGE_ROW_TO_CODES[label]:
            parsed[code] = values.copy()
    return parsed


def parse_debt(config: dict[str, Any]) -> dict[int, float]:
    frame = _read_raw(config, "debt_glob")
    parsed: dict[int, float] = {}
    for _, row in frame.iloc[3:].iterrows():
        label = str(row.iloc[1]).strip()
        if label not in AGE_ROW_TO_CODES:
            continue
        for code in AGE_ROW_TO_CODES[label]:
            parsed[code] = float(row.iloc[3])
    return parsed


def configured_anchors(config: dict[str, Any], scale: float = 1.0) -> tuple[dict[int, dict[str, float]], dict[int, float]]:
    anchors = {int(age): {key: float(value) * scale for key, value in values.items()} for age, values in config["external"]["anchors"].items()}
    debt = {int(age): float(value) * scale for age, value in config["external"]["debt"].items()}
    return anchors, debt


def parse_household_crosscheck(config: dict[str, Any]) -> dict[str, Any]:
    """Parse 2023 household-income distributions for cross-validation only."""
    dataset_dir = ROOT / config["project"]["dataset_dir"]
    yearly_path = resolve_single(dataset_dir, config["paths"]["yearly_household_glob"])
    yearly, _ = read_csv_fallback(yearly_path, config["io"]["csv_encodings"])
    year_column = yearly.columns[0]
    yearly_2023 = yearly[pd.to_numeric(yearly[year_column], errors="coerce").eq(2023)]
    if yearly_2023.empty:
        raise ValueError(f"2023 row missing in household-income file: {yearly_path}")
    yearly_values = pd.to_numeric(yearly_2023.iloc[0, 1:], errors="coerce").astype(float).tolist()

    age_path = resolve_single(dataset_dir, config["paths"]["age_household_glob"])
    age_frame = pd.read_excel(age_path, sheet_name="데이터", header=None)
    youth_row = age_frame[(age_frame.iloc[:, 0].astype(str).str.strip() == "청년(18~39세)") & (age_frame.iloc[:, 1].astype(str).str.strip() == "소계")]
    if youth_row.empty:
        raise ValueError(f"Youth aggregate row missing in household-income workbook: {age_path}")
    age_values = pd.to_numeric(youth_row.iloc[0, 2:], errors="coerce").astype(float).tolist()
    agrees = len(yearly_values) == len(age_values) and bool(np.allclose(yearly_values, age_values, equal_nan=True))
    return {
        "yearly_2023": yearly_values,
        "age_workbook_youth_2023": age_values,
        "aggregate_distribution_matches": agrees,
        "usage": "가구소득은 개인소득과 직접 비교하지 않고 교차검증에만 사용",
    }


def validate_external(config: dict[str, Any]) -> dict[str, Any]:
    expected_income, expected_debt = configured_anchors(config)
    actual_income = parse_income_card(config)
    actual_debt = parse_debt(config)
    tolerance = float(config["external"].get("tolerance", 1e-6))
    mismatches: list[str] = []
    for age, expected in expected_income.items():
        if age not in actual_income:
            mismatches.append(f"income/card age {age}: missing")
            continue
        for key, value in expected.items():
            if abs(actual_income[age][key] - value) > tolerance:
                mismatches.append(f"income/card age {age} {key}: config={value}, file={actual_income[age][key]}")
    for age, value in expected_debt.items():
        if age not in actual_debt or abs(actual_debt[age] - value) > tolerance:
            mismatches.append(f"debt age {age}: config={value}, file={actual_debt.get(age)}")
    if mismatches:
        LOGGER.warning("External anchor mismatch:\n%s", "\n".join(mismatches))
    household = parse_household_crosscheck(config)
    if not household["aggregate_distribution_matches"]:
        LOGGER.warning("2023 youth household-income distributions differ between CSV and XLSX")
    return {"income_card": actual_income, "debt": actual_debt, "household_crosscheck": household, "mismatches": mismatches}
