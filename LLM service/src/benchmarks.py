from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

AGE_BANDS = (18, 20, 25, 30, 35)


def age_to_band(value: Any) -> int | None:
    try:
        age = int(float(value))
    except (TypeError, ValueError):
        return None
    if age in AGE_BANDS:
        return age
    if 18 <= age <= 19:
        return 18
    if 20 <= age <= 24:
        return 20
    if 25 <= age <= 29:
        return 25
    if 30 <= age <= 34:
        return 30
    if 35 <= age <= 39:
        return 35
    return None


def build_credit_benchmarks(frame: pd.DataFrame, *, sentinel: float = -99999999) -> dict[int, dict[str, float]]:
    """실제 KCB 표본에서 연령별 신용평점 평균과 분위수를 만든다."""
    age = pd.to_numeric(frame["연령대"], errors="coerce")
    score = pd.to_numeric(frame["신용평점"], errors="coerce").mask(lambda item: item.eq(sentinel))
    thin = pd.to_numeric(frame.get("Thin Filer 여부", 0), errors="coerce").eq(1)
    output: dict[int, dict[str, float]] = {}
    for band in AGE_BANDS:
        values = score[age.eq(band) & ~thin].dropna()
        if not values.empty:
            output[band] = {
                "mean": float(values.mean()),
                "q20": float(values.quantile(0.2)),
                "q50": float(values.quantile(0.5)),
                "q80": float(values.quantile(0.8)),
            }
    return output


def load_credit_benchmarks(path: str | Path) -> dict[int, dict[str, float]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {int(key): {name: float(value) for name, value in values.items()} for key, values in payload.items()}
