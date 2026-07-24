from __future__ import annotations

from typing import Any

import numpy as np


def apply_temperature(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    """확률을 logit으로 바꿔 단일 temperature로 보정한다."""
    values = np.asarray(probabilities, dtype=float)
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("확률 배열은 (행, 클래스) 형태여야 합니다.")
    if not np.isfinite(values).all() or (values < 0).any() or temperature <= 0:
        raise ValueError("확률과 temperature 값을 확인하세요.")
    row_sums = values.sum(axis=1, keepdims=True)
    if not np.allclose(row_sums, 1.0, atol=1e-6):
        raise ValueError("각 행의 클래스 확률 합은 1이어야 합니다.")
    logits = np.log(np.clip(values, 1e-12, 1.0)) / float(temperature)
    logits -= logits.max(axis=1, keepdims=True)
    scaled = np.exp(logits)
    return scaled / scaled.sum(axis=1, keepdims=True)


def _metrics(probabilities: np.ndarray, targets: np.ndarray, bins: int = 10) -> dict[str, float]:
    rows = np.arange(len(targets))
    nll = -float(np.mean(np.log(np.clip(probabilities[rows, targets], 1e-12, 1.0))))
    one_hot = np.eye(probabilities.shape[1])[targets]
    brier = float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))
    confidence = probabilities.max(axis=1)
    correct = probabilities.argmax(axis=1) == targets
    ece = 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
        mask = (confidence >= lower if index == 0 else confidence > lower) & (confidence <= upper)
        if mask.any():
            ece += float(mask.mean()) * abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
    return {"log_loss": nll, "brier": brier, "ece": ece}


def fit_temperature(probabilities: np.ndarray, targets: np.ndarray) -> dict[str, Any]:
    """OOF 확률에서 Log Loss와 ECE를 악화시키지 않는 temperature를 선택한다."""
    values = np.asarray(probabilities, dtype=float)
    labels = np.asarray(targets, dtype=int)
    if len(values) == 0 or values.shape[0] != len(labels):
        raise ValueError("OOF 확률과 정답이 비어 있거나 행 수가 다릅니다.")
    before = _metrics(values, labels)
    candidates = np.unique(np.concatenate([np.geomspace(0.25, 4.0, 161), [1.0]]))
    evaluated: list[tuple[float, dict[str, float]]] = []
    for temperature in candidates:
        metrics = _metrics(apply_temperature(values, float(temperature)), labels)
        if metrics["log_loss"] <= before["log_loss"] + 1e-12 and metrics["ece"] <= before["ece"] + 1e-12:
            evaluated.append((float(temperature), metrics))
    temperature, after = min(evaluated, key=lambda item: (item[1]["log_loss"], item[1]["ece"]))
    return {
        "method": "temperature_scaling",
        "temperature": temperature,
        "n_oof": int(len(labels)),
        "before": before,
        "after": after,
    }
