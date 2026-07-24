from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.labeling import label_dataframe


def _fixture():
    payload = json.loads((Path(__file__).parent / "fixtures" / "counter_examples.json").read_text(encoding="utf-8"))
    return pd.DataFrame(payload["cases"]), payload["quantiles"]


def test_ten_counter_examples_are_not_misclassified() -> None:
    frame, q = _fixture()
    labels = label_dataframe(frame, q)
    result = labels.set_index(frame["case"])
    def is_label(case: int, code: str) -> bool:
        return bool(pd.notna(result.loc[case, "LABEL"]) and result.loc[case, "LABEL"] == code)

    assert not is_label(1, "V1")
    assert result.loc[2, "LABEL"] == "V2"
    assert result.loc[3, "LABEL"] in {"S1", "S2"}
    assert not str(result.loc[4, "LABEL"]).startswith("V")
    assert not is_label(5, "V3")
    assert not is_label(6, "S2")
    assert not str(result.loc[7, "LABEL"]).startswith("V")
    assert result.loc[8, "HOLDOUT_REASON"] == "THIN"
    assert result.loc[9, "HOLDOUT_REASON"] == "DEBT_UNOBS"
    assert not str(result.loc[10, "LABEL"]).startswith("V")
    assert labels["EFFECTIVE_MATCH_COUNT"].le(1).all()
