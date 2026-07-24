from __future__ import annotations

import pytest
import numpy as np

from src.calibration import apply_temperature, fit_temperature
from src.classify_service import _response, classification_capability, scores_from_probabilities
from src.io_load import load_config


def test_stability_and_instability_scores() -> None:
    probabilities = {"V1": 0.10, "V2": 0.15, "V3": 0.05, "S1": 0.20, "S2": 0.30, "S3": 0.20}
    stable, unstable = scores_from_probabilities(probabilities)
    assert stable == 70.0
    assert unstable == 30.0


def test_probability_sum_must_equal_one() -> None:
    with pytest.raises(AssertionError, match="확률 합"):
        scores_from_probabilities({"V1": 0.1, "V2": 0.1, "V3": 0.1, "S1": 0.1, "S2": 0.1, "S3": 0.1})


def test_user_type_uses_two_group_probability_sum_not_argmax_subtype() -> None:
    result = _response(
        {"V1": 0.35, "V2": 0.03, "V3": 0.02, "S1": 0.20, "S2": 0.20, "S3": 0.20},
        caution=False,
    )
    assert result["세부유형코드"] == "V1"
    assert result["유형"] == "경제적 안정 청년"
    assert result["유형점수"] == 60.0
    assert result["유형확률"] == {"경제적 취약 청년": 0.4, "경제적 안정 청년": 0.6}


def test_temperature_is_fitted_from_oof_probabilities() -> None:
    probabilities = np.asarray([[0.8, 0.2], [0.7, 0.3], [0.4, 0.6], [0.3, 0.7]])
    targets = np.asarray([0, 1, 1, 1])
    calibration = fit_temperature(probabilities, targets)
    calibrated = apply_temperature(probabilities, calibration["temperature"])
    assert np.allclose(calibrated.sum(axis=1), 1.0)
    assert calibration["after"]["log_loss"] <= calibration["before"]["log_loss"]
    assert calibration["after"]["ece"] <= calibration["before"]["ece"]


def test_classification_capability_reports_missing_artifacts(tmp_path) -> None:
    config = load_config()
    config["project"]["artifacts_dir"] = str(tmp_path)
    capability = classification_capability(config)
    assert capability["available"] is False
    assert capability["reason"] == "MODEL_ARTIFACTS_MISSING"
    assert set(capability["missing"]) == {"model.cbm", "quantiles.json", "calibration.json"}
