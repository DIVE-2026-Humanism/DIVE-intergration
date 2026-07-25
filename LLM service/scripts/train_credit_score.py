#!/usr/bin/env python3
"""Train and evaluate a reproducible credit-score regression model.

The target in the supplied synthetic dataset is ``신용평점``.  The script keeps
the test split untouched, selects CatBoost parameters on a validation split,
then refits using the selected iteration count on train+validation data.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


TARGET = "신용평점"
CATEGORICAL_FEATURES = [
    "성별",
    "연령대",
    "직업군",
    "거주지 시군구 코드",
    "근무지 시군구 코드",
    "자가거주여부",
    "차량보유(국산/수입)",
]
# Values are codes rather than continuous quantities. Binary/ordinal flags are
# left numeric because their ordering has a direct financial interpretation.
SENTINELS = {-99999999, -9999999, -999999, -99999}
PARAMETER_CANDIDATES = [
    {"depth": 6, "learning_rate": 0.05, "l2_leaf_reg": 5.0},
    {"depth": 8, "learning_rate": 0.04, "l2_leaf_reg": 8.0},
    {"depth": 10, "learning_rate": 0.03, "l2_leaf_reg": 10.0},
]


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    default_data = next((root / "Dataset").glob("*합성데이터*.csv"), None)
    parser = argparse.ArgumentParser(description="신용평점 CatBoost 회귀 모델 학습")
    parser.add_argument("--data", type=Path, default=default_data)
    parser.add_argument("--output-dir", type=Path, default=root / "artifacts" / "credit_score")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--iterations", type=int, default=3000)
    parser.add_argument("--early-stopping-rounds", type=int, default=150)
    parser.add_argument("--thread-count", type=int, default=-1)
    parser.add_argument("--devices", default="0", help="사용할 GPU ID. 예: 0 또는 0:1")
    parser.add_argument("--gpu-ram-part", type=float, default=0.9)
    parser.add_argument("--quick", action="store_true", help="파이프라인 점검용: 1개 후보, 최대 100회")
    return parser.parse_args()


def load_data(path: Path) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    if path is None or not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if TARGET not in frame:
        raise ValueError(f"Target column {TARGET!r} is absent")
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate columns are not allowed")

    y = pd.to_numeric(frame.pop(TARGET), errors="coerce")
    keep = y.notna()
    frame, y = frame.loc[keep].copy(), y.loc[keep].copy()
    numeric_features = [column for column in frame if column not in CATEGORICAL_FEATURES]
    for column in numeric_features:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame[column] = frame[column].mask(frame[column].isin(SENTINELS), np.nan)
    for column in CATEGORICAL_FEATURES:
        if column not in frame:
            raise ValueError(f"Required categorical feature is absent: {column}")
        # CatBoost requires categorical missing values to be represented as text.
        frame[column] = frame[column].astype("string").fillna("__MISSING__").astype(str)
    return frame, y, numeric_features


def metrics(y_true: pd.Series, prediction: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, prediction)),
        "rmse": float(mean_squared_error(y_true, prediction) ** 0.5),
        "r2": float(r2_score(y_true, prediction)),
        "within_20_points": float(np.mean(np.abs(y_true.to_numpy() - prediction) <= 20)),
        "within_50_points": float(np.mean(np.abs(y_true.to_numpy() - prediction) <= 50)),
    }


def make_model(args: argparse.Namespace, params: dict, iterations: int) -> CatBoostRegressor:
    return CatBoostRegressor(
        loss_function="RMSE",
        eval_metric="MAE",
        iterations=iterations,
        random_seed=args.seed,
        thread_count=args.thread_count,
        task_type="GPU",
        devices=args.devices,
        gpu_ram_part=args.gpu_ram_part,
        allow_writing_files=False,
        verbose=100,
        **params,
    )


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    x, y, numeric_features = load_data(args.data)

    # 70/15/15. Only validation is used for selection; test remains untouched.
    x_train, x_temp, y_train, y_temp = train_test_split(
        x, y, test_size=0.30, random_state=args.seed
    )
    x_valid, x_test, y_valid, y_test = train_test_split(
        x_temp, y_temp, test_size=0.50, random_state=args.seed
    )
    candidates = PARAMETER_CANDIDATES[:1] if args.quick else PARAMETER_CANDIDATES
    max_iterations = min(args.iterations, 100) if args.quick else args.iterations
    results = []
    best_model = None
    for index, params in enumerate(candidates):
        model = make_model(args, params, max_iterations)
        model.fit(
            x_train,
            y_train,
            cat_features=CATEGORICAL_FEATURES,
            eval_set=(x_valid, y_valid),
            early_stopping_rounds=args.early_stopping_rounds,
            use_best_model=True,
        )
        result = {
            "candidate": index,
            "params": params,
            "best_iteration": max(1, model.get_best_iteration() + 1),
            "validation": metrics(y_valid, model.predict(x_valid)),
        }
        results.append(result)
        if best_model is None or result["validation"]["mae"] < min(
            item["validation"]["mae"] for item in results[:-1]
        ):
            best_model = result

    assert best_model is not None
    x_fit = pd.concat([x_train, x_valid])
    y_fit = pd.concat([y_train, y_valid])
    final_model = make_model(args, best_model["params"], best_model["best_iteration"])
    final_model.fit(x_fit, y_fit, cat_features=CATEGORICAL_FEATURES, verbose=100)
    test_prediction = final_model.predict(x_test)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    final_model.save_model(str(args.output_dir / "credit_score_model.cbm"))
    importance = sorted(
        zip(x.columns, final_model.get_feature_importance()), key=lambda item: item[1], reverse=True
    )
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data": str(args.data.resolve()),
        "rows": len(x),
        "target": TARGET,
        "target_summary": {key: float(value) for key, value in y.describe().items()},
        "features": list(x.columns),
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": numeric_features,
        "excluded_features": [TARGET],
        "sentinels_converted_to_missing": sorted(SENTINELS),
        "split": {"train": len(x_train), "validation": len(x_valid), "test": len(x_test)},
        "selection_results": results,
        "selected": best_model,
        "test": metrics(y_test, test_prediction),
        "baseline_test_mae": float(mean_absolute_error(y_test, np.repeat(y_train.median(), len(y_test)))),
        "feature_importance": [{"feature": name, "importance": float(value)} for name, value in importance],
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "training_device": {"task_type": "GPU", "devices": args.devices},
        "warning": "합성데이터 성능은 실제 신규 고객에 대한 일반화 성능을 보장하지 않습니다.",
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "feature_schema.json").write_text(
        json.dumps(
            {
                "target": TARGET,
                "features": list(x.columns),
                "categorical_features": CATEGORICAL_FEATURES,
                "numeric_features": numeric_features,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"selected": best_model, "test": report["test"]}, ensure_ascii=False, indent=2))
    print(f"Saved artifacts to: {args.output_dir}")


if __name__ == "__main__":
    main()
