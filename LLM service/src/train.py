from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Iterator

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import confusion_matrix, f1_score, recall_score
from sklearn.model_selection import GroupKFold, StratifiedKFold, TimeSeriesSplit

from .calibration import fit_temperature
from .features import MODEL_FEATURES, build_base_features, finalize_features
from .benchmarks import build_credit_benchmarks
from .io_load import ROOT, write_json
from .labeling import CLASS_ORDER, LABEL_NAMES, label_dataframe
from .quantiles import compute_quantiles

LOGGER = logging.getLogger(__name__)


def _determine_splitter(
    raw: pd.DataFrame,
    indices: np.ndarray,
    labels: pd.Series,
    config: dict[str, Any],
) -> tuple[str, Iterator[tuple[np.ndarray, np.ndarray]]]:
    n_splits = int(config["split"]["n_splits"])
    time_column = next((column for column in config["split"]["time_candidates"] if column in raw.columns), None)
    id_column = next((column for column in config["split"]["id_candidates"] if column in raw.columns), None)
    if time_column:
        ordered = np.argsort(pd.to_datetime(raw.iloc[indices][time_column], errors="coerce").fillna(pd.Timestamp.min).to_numpy())
        splitter = TimeSeriesSplit(n_splits=n_splits)
        return f"time:{time_column}", splitter.split(ordered)
    if id_column:
        groups = raw.iloc[indices][id_column].astype("string").fillna("__MISSING_GROUP__")
        splitter = GroupKFold(n_splits=n_splits)
        return f"group:{id_column}", splitter.split(indices, labels, groups)
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=int(config["project"]["seed"]))
    return "stratified", splitter.split(indices, labels)


def _model(config: dict[str, Any], params: dict[str, Any], *, iterations: int | None = None) -> CatBoostClassifier:
    training = config["training"]
    return CatBoostClassifier(
        loss_function="MultiClass",
        eval_metric="MultiClass",
        iterations=iterations or int(training["iterations"]),
        early_stopping_rounds=int(training["early_stopping_rounds"]),
        auto_class_weights="Balanced",
        random_seed=int(config["project"]["seed"]),
        verbose=training["verbose"],
        thread_count=int(training["thread_count"]),
        allow_writing_files=False,
        **params,
    )


def prepare_full(raw: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], pd.DataFrame]:
    base = build_base_features(raw, config)
    quantiles = compute_quantiles(base, config)
    features = finalize_features(base, quantiles)
    labels = label_dataframe(features, quantiles)
    return base, features, quantiles, labels


def _score(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    recalls = recall_score(y_true, y_pred, labels=CLASS_ORDER, average=None, zero_division=0)
    return {
        "macro_f1": float(f1_score(y_true, y_pred, labels=CLASS_ORDER, average="macro", zero_division=0)),
        "class_recall": {code: float(value) for code, value in zip(CLASS_ORDER, recalls)},
        "min_class_recall": float(np.min(recalls)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CLASS_ORDER).tolist(),
        "n_validation": len(y_true),
    }


def train_pipeline(raw: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    artifacts = ROOT / config["project"]["artifacts_dir"]
    artifacts.mkdir(parents=True, exist_ok=True)
    base, full_features, full_quantiles, full_labels = prepare_full(raw, config)
    confirmed = full_labels["LABEL"].notna()
    confirmed_indices = np.flatnonzero(confirmed.to_numpy())
    confirmed_labels = full_labels.loc[confirmed, "LABEL"].reset_index(drop=True)
    counts = confirmed_labels.value_counts()
    missing_classes = [code for code in CLASS_ORDER if counts.get(code, 0) < int(config["split"]["n_splits"])]
    if missing_classes:
        raise ValueError(f"Training requires at least {config['split']['n_splits']} rows per class; insufficient: {missing_classes}; counts={counts.to_dict()}")

    split_name, split_iterator = _determine_splitter(raw, confirmed_indices, confirmed_labels, config)
    # Materialize once because all three hyperparameter combinations must see identical folds.
    relative_splits = list(split_iterator)
    candidates: list[dict[str, Any]] = []
    calibration_inputs: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    all_fold_quantiles: list[dict[str, Any]] = []
    for candidate_index, params in enumerate(config["training"]["hyperparameters"]):
        fold_scores: list[dict[str, Any]] = []
        oof_true: list[str] = []
        oof_pred: list[str] = []
        oof_probabilities: list[list[float]] = []
        best_iterations: list[int] = []
        for fold_index, (train_rel, valid_rel) in enumerate(relative_splits):
            # TimeSeriesSplit yields positions into its ordered array; other splitters yield direct positions.
            if split_name.startswith("time:"):
                time_column = split_name.split(":", 1)[1]
                ordered = np.argsort(pd.to_datetime(raw.iloc[confirmed_indices][time_column], errors="coerce").fillna(pd.Timestamp.min).to_numpy())
                train_orig = confirmed_indices[ordered[train_rel]]
                valid_orig = confirmed_indices[ordered[valid_rel]]
            else:
                train_orig = confirmed_indices[train_rel]
                valid_orig = confirmed_indices[valid_rel]
            fold_quantiles = compute_quantiles(base.iloc[train_orig], config)
            train_features = finalize_features(base.iloc[train_orig], fold_quantiles)
            valid_features = finalize_features(base.iloc[valid_orig], fold_quantiles)
            train_labels = label_dataframe(train_features, fold_quantiles)
            valid_labels = label_dataframe(valid_features, fold_quantiles)
            train_keep = train_labels["LABEL"].notna()
            valid_keep = valid_labels["LABEL"].notna()
            y_train = train_labels.loc[train_keep, "LABEL"]
            y_valid = valid_labels.loc[valid_keep, "LABEL"]
            if set(CLASS_ORDER) - set(y_train.unique()):
                raise ValueError(f"Fold {fold_index} lost classes after train-only quantile relabeling: {sorted(set(CLASS_ORDER) - set(y_train.unique()))}")
            model = _model(config, params)
            model.fit(
                train_features.loc[train_keep, MODEL_FEATURES],
                y_train,
                eval_set=(valid_features.loc[valid_keep, MODEL_FEATURES], y_valid),
                use_best_model=True,
            )
            prediction = np.asarray(model.predict(valid_features.loc[valid_keep, MODEL_FEATURES])).reshape(-1).astype(str).tolist()
            fold_probabilities = np.asarray(model.predict_proba(valid_features.loc[valid_keep, MODEL_FEATURES]), dtype=float)
            class_index = {str(code): index for index, code in enumerate(model.classes_)}
            oof_probabilities.extend(
                [[float(row[class_index[code]]) for code in CLASS_ORDER] for row in fold_probabilities]
            )
            truth = y_valid.astype(str).tolist()
            score = _score(truth, prediction)
            score["fold"] = fold_index
            score["best_iteration"] = int(model.get_best_iteration())
            fold_scores.append(score)
            oof_true.extend(truth)
            oof_pred.extend(prediction)
            best_iterations.append(max(1, int(model.get_best_iteration()) + 1))
            if candidate_index == 0:
                all_fold_quantiles.append({"fold": fold_index, "train_rows": len(train_orig), "valid_rows": len(valid_orig), **fold_quantiles})
        aggregate = _score(oof_true, oof_pred)
        aggregate["mean_fold_macro_f1"] = float(np.mean([item["macro_f1"] for item in fold_scores]))
        aggregate["params"] = dict(params)
        aggregate["folds"] = fold_scores
        aggregate["suggested_iterations"] = int(np.median(best_iterations))
        aggregate["candidate_index"] = candidate_index
        candidates.append(aggregate)
        calibration_inputs[candidate_index] = (
            np.asarray(oof_probabilities, dtype=float),
            np.asarray([CLASS_ORDER.index(code) for code in oof_true], dtype=int),
        )

    candidates.sort(key=lambda item: (item["mean_fold_macro_f1"], item["min_class_recall"]), reverse=True)
    best = candidates[0]
    final_keep = full_labels["LABEL"].notna()
    final_model = _model(config, best["params"], iterations=best["suggested_iterations"])
    final_model.set_params(early_stopping_rounds=None)
    final_model.fit(full_features.loc[final_keep, MODEL_FEATURES], full_labels.loc[final_keep, "LABEL"])
    model_path = artifacts / "model.cbm"
    final_model.save_model(str(model_path))
    calibration = fit_temperature(*calibration_inputs[int(best["candidate_index"])])

    label_artifact = pd.concat([raw[["_ROW_ID"]].reset_index(drop=True), full_labels.drop(columns=["_ROW_ID"], errors="ignore").reset_index(drop=True)], axis=1)
    label_artifact.to_parquet(artifacts / "labels.parquet", index=False)
    write_json(artifacts / "features.json", {"model_features": MODEL_FEATURES, "label_binary_flags_excluded": ["LOW_INC", "HIGH_INC", "CASH_HEAVY", "DEBT_UNOBS", "SCORE_NA", "INC_CHG_NA"]})
    write_json(artifacts / "quantiles.json", {"full": full_quantiles, "folds": all_fold_quantiles})
    write_json(artifacts / "credit_benchmarks.json", build_credit_benchmarks(raw, sentinel=float(config["io"]["sentinel"])))
    write_json(artifacts / "calibration.json", calibration)
    metrics = {
        "split_strategy": split_name,
        "data_provenance": {
            "data_kind": str(config["project"].get("data_kind", "official_kcb")),
            "source_csv": str(config["paths"]["main_csv"]),
        },
        "class_names": LABEL_NAMES,
        "class_counts": {code: int(counts.get(code, 0)) for code in CLASS_ORDER},
        "best": best,
        "candidates": candidates,
        "calibration": calibration,
        "interpretation_warning": "높은 성능은 실제 경제상태 또는 미래 위험 예측이 아니라 의사레이블 규칙 재현 성능이다.",
    }
    write_json(artifacts / "metrics.json", metrics)
    write_json(
        artifacts / "model_provenance.json",
        {
            "data_kind": metrics["data_provenance"]["data_kind"],
            "source_csv": metrics["data_provenance"]["source_csv"],
            "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "do_not_use_for_production": metrics["data_provenance"]["data_kind"] != "official_kcb",
        },
    )
    LOGGER.info("Saved final model with %s rows; best CV Macro-F1 %.4f", int(final_keep.sum()), best["mean_fold_macro_f1"])
    return {"model": final_model, "features": full_features, "labels": full_labels, "quantiles": full_quantiles, "metrics": metrics}


def load_metrics(config: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / config["project"]["artifacts_dir"] / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))
