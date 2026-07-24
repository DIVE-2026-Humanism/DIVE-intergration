from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _quantile(series: pd.Series, percentile: float) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return float("nan")
    return float(clean.quantile(min(1.0, max(0.0, percentile))))


def compute_quantiles(base: pd.DataFrame, config: dict[str, Any], *, percentile_shift: float = 0.0) -> dict[str, float]:
    definitions = config["quantiles"]
    loan_holders = base["총대출건수"].ge(1)
    observed_debt = loan_holders & base["DEBT_SUM"].gt(0)
    scored = ~base["Thin Filer 여부"].eq(1)
    owner = base["OWNER"].eq(1)
    changed_income = base["INC_CHG"].notna()
    delinquent = base["DELQ_COUNT"].ge(1)

    population = {
        "D50": base.loc[loan_holders, "DSR_PROXY"],
        "D80": base.loc[loan_holders, "DSR_PROXY"],
        "RD80": base.loc[observed_debt, "REL_DEBT"],
        "C20": base.loc[scored, "신용평점"],
        "C50": base.loc[scored, "신용평점"],
        "C80": base.loc[scored, "신용평점"],
        "NW50": base.loc[owner, "순자산평가금액(주택)"],
        "IC10": base.loc[changed_income, "INC_CHG"],
        "DLQ25": base.loc[delinquent, "연체일수"],
        "DLQ75": base.loc[delinquent, "연체일수"],
        "RD20": base.loc[observed_debt, "REL_DEBT"],
    }
    values = {name: _quantile(series, float(definitions[name]) + percentile_shift) for name, series in population.items()}
    values["percentile_shift"] = float(percentile_shift)
    missing = [name for name, value in values.items() if name != "percentile_shift" and not np.isfinite(value)]
    if missing:
        raise ValueError(f"Cannot calculate required quantiles because populations are empty: {missing}")
    return values


def compute_age_quantiles(base: pd.DataFrame, config: dict[str, Any], *, percentile_shift: float = 0.0) -> dict[int, dict[str, float]]:
    result: dict[int, dict[str, float]] = {}
    for age in config["filters"]["youth_age_codes"]:
        subset = base[base["연령대"].eq(age)]
        try:
            result[int(age)] = compute_quantiles(subset, config, percentile_shift=percentile_shift)
        except ValueError:
            # Sparse cells intentionally fall back to the global training-fold values at application time.
            continue
    return result
