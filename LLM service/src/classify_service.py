from __future__ import annotations

import json
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .calibration import apply_temperature
from .features import MODEL_FEATURES, build_base_features, finalize_features
from .io_load import ROOT, SchemaContractError, load_config
from .labeling import CLASS_ORDER, label_dataframe
from .preprocess import preprocess_main


def _probability_contract(probabilities: dict[str, float]) -> dict[str, float]:
    missing = set(CLASS_ORDER) - set(probabilities)
    if missing:
        raise ValueError(f"6유형 확률이 누락되었습니다: {sorted(missing)}")
    values = np.asarray([float(probabilities[code]) for code in CLASS_ORDER], dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("확률은 0 이상의 유한값이어야 합니다.")
    total = float(values.sum())
    if not np.isclose(total, 1.0, atol=1e-6):
        raise AssertionError(f"6유형 확률 합은 1이어야 합니다: {total}")
    return {code: float(value) for code, value in zip(CLASS_ORDER, values)}


def scores_from_probabilities(probabilities: dict[str, float]) -> tuple[float, float]:
    probabilities = _probability_contract(probabilities)
    stable = round(100.0 * sum(probabilities[code] for code in ("S1", "S2", "S3")), 1)
    unstable = round(100.0 - stable, 1)
    return stable, unstable


def _response(probabilities: dict[str, float], *, caution: bool) -> dict[str, Any]:
    probabilities = _probability_contract(probabilities)
    code = max(CLASS_ORDER, key=lambda item: probabilities[item])
    stable, unstable = scores_from_probabilities(probabilities)
    user_type = "경제적 안정 청년" if stable >= unstable else "경제적 취약 청년"
    return {
        "대분류": "안정" if user_type == "경제적 안정 청년" else "취약",
        "유형": user_type,
        "세부유형코드": code,
        "확률": probabilities,
        "유형확률": {
            "경제적 취약 청년": round(unstable / 100.0, 6),
            "경제적 안정 청년": round(stable / 100.0, 6),
        },
        "유형점수": max(stable, unstable),
        "안정점수": stable,
        "불안정점수": unstable,
        "신뢰주의": bool(caution),
    }


def _artifact_paths(config: dict[str, Any]) -> tuple[Path, Path, Path]:
    directory = ROOT / config["project"]["artifacts_dir"]
    return directory / "model.cbm", directory / "quantiles.json", directory / "calibration.json"


def _artifact_signature(paths: tuple[Path, Path, Path]) -> tuple[int, ...]:
    return tuple(path.stat().st_mtime_ns for path in paths)


@lru_cache(maxsize=2)
def _load_runtime(
    model_path_text: str,
    quantile_path_text: str,
    calibration_path_text: str,
    signature: tuple[int, ...],
) -> tuple[Any, dict[str, Any], dict[str, Any], str]:
    # signature는 파일 교체 시 캐시 키를 바꾸기 위한 값이다.
    del signature
    try:
        from catboost import CatBoostClassifier
    except ImportError as exc:  # pragma: no cover - 실제 모델 환경에서만 필요
        raise RuntimeError("실제 모델 추론에는 catboost가 필요합니다: pip install -r requirements.lock") from exc
    model_path = Path(model_path_text)
    model = CatBoostClassifier()
    model.load_model(str(model_path))
    quantile_payload = json.loads(Path(quantile_path_text).read_text(encoding="utf-8"))
    calibration = json.loads(Path(calibration_path_text).read_text(encoding="utf-8"))
    model_version = hashlib.sha256(model_path.read_bytes()).hexdigest()[:12]
    return model, quantile_payload, calibration, model_version


def classification_capability(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """정밀 분류 아티팩트의 존재뿐 아니라 실제 로딩 가능 여부를 확인한다."""
    config = config or load_config()
    paths = _artifact_paths(config)
    missing = [path.name for path in paths if not path.is_file() or path.stat().st_size == 0]
    if missing:
        return {"available": False, "reason": "MODEL_ARTIFACTS_MISSING", "missing": missing}
    try:
        _load_runtime(*(str(path) for path in paths), _artifact_signature(paths))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return {"available": False, "reason": "MODEL_ARTIFACTS_INVALID", "missing": []}
    return {"available": True, "reason": None, "missing": []}


def classify(record: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    required = config["columns"]["required"]
    missing = [column for column in required if column not in record]
    if missing:
        raise SchemaContractError("단건 KCB 입력 필수 컬럼 누락: " + ", ".join(missing))
    model_path, quantile_path, calibration_path = _artifact_paths(config)
    missing_artifacts = [path for path in (model_path, quantile_path, calibration_path) if not path.exists()]
    if missing_artifacts:
        raise FileNotFoundError(f"분류 아티팩트가 없습니다: {missing_artifacts}")
    raw = pd.DataFrame([record])
    processed, _ = preprocess_main(raw, config)
    if processed.empty:
        raise ValueError("KCB 레코드가 청년·부산 전처리 조건을 통과하지 못했습니다.")
    model, quantile_payload, calibration, model_version = _load_runtime(
        str(model_path),
        str(quantile_path),
        str(calibration_path),
        _artifact_signature((model_path, quantile_path, calibration_path)),
    )
    quantiles = quantile_payload.get("full", quantile_payload)
    base = build_base_features(processed, config)
    features = finalize_features(base, quantiles)

    raw_probabilities = np.asarray(model.predict_proba(features[MODEL_FEATURES]))[0]
    class_probabilities = {str(code): float(value) for code, value in zip(model.classes_, raw_probabilities)}
    ordered = _probability_contract(class_probabilities)
    if calibration.get("method") != "temperature_scaling":
        raise ValueError(f"지원하지 않는 확률 보정 방식입니다: {calibration}")
    calibrated = apply_temperature(
        np.asarray([[ordered[code] for code in CLASS_ORDER]]),
        float(calibration["temperature"]),
    )[0]
    probabilities = {code: float(value) for code, value in zip(CLASS_ORDER, calibrated)}
    labels = label_dataframe(features, quantiles, strict_overlap=False)
    caution = bool(pd.notna(labels.iloc[0]["HOLDOUT_REASON"]))
    response = _response(probabilities, caution=caution)
    response.update(
        {
            "thin_filer": bool(float(record.get("Thin Filer 여부", 0)) == 1),
            "key_drivers": [],
            "model_version": model_version,
        }
    )
    return response
