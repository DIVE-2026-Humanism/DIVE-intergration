from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, recall_score
from sklearn.model_selection import StratifiedKFold

from .features import MODEL_FEATURES, REDUCED_FEATURES
from .io_load import ROOT, write_json
from .labeling import CLASS_ORDER
from .train import _model, load_metrics, prepare_full


def _evaluate(features: pd.DataFrame, labels: pd.Series, feature_names: list[str], params: dict[str, Any], iterations: int, config: dict[str, Any]) -> dict[str, Any]:
    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=int(config["project"]["seed"]))
    truth: list[str] = []
    predicted: list[str] = []
    for train_index, valid_index in splitter.split(features, labels):
        model = _model(config, params, iterations=iterations)
        model.set_params(early_stopping_rounds=None)
        model.fit(features.iloc[train_index][feature_names], labels.iloc[train_index])
        fold_pred = np.asarray(model.predict(features.iloc[valid_index][feature_names])).reshape(-1).astype(str)
        truth.extend(labels.iloc[valid_index].astype(str).tolist())
        predicted.extend(fold_pred.tolist())
    recalls = recall_score(truth, predicted, labels=CLASS_ORDER, average=None, zero_division=0)
    return {
        "features": feature_names,
        "macro_f1": float(f1_score(truth, predicted, labels=CLASS_ORDER, average="macro", zero_division=0)),
        "class_recall": {code: float(value) for code, value in zip(CLASS_ORDER, recalls)},
        "confusion_matrix": confusion_matrix(truth, predicted, labels=CLASS_ORDER).tolist(),
    }


def leakage_report(raw: pd.DataFrame, config: dict[str, Any]) -> Path:
    _, features, _, labels = prepare_full(raw, config)
    keep = labels["LABEL"].notna()
    x = features.loc[keep].reset_index(drop=True)
    y = labels.loc[keep, "LABEL"].reset_index(drop=True)
    best = load_metrics(config)["best"]
    iterations = int(best["suggested_iterations"])
    full = _evaluate(x, y, MODEL_FEATURES, best["params"], iterations, config)
    reduced = _evaluate(x, y, REDUCED_FEATURES, best["params"], iterations, config)
    payload = {"full": full, "reduced": reduced, "macro_f1_drop": full["macro_f1"] - reduced["macro_f1"]}
    artifacts = ROOT / config["project"]["artifacts_dir"]
    reports = ROOT / config["project"]["reports_dir"]
    write_json(artifacts / "leakage_metrics.json", payload)
    lines = [
        "# 의사레이블 누출/규칙 복제 비교",
        "",
        "> 높은 성능은 실제 경제상태나 미래 위험의 예측력이 아니라 의사레이블 규칙 재현 정도다.",
        "",
        "| 모델 | 피처 수 | Macro-F1 |",
        "|---|---:|---:|",
        f"| 전체 12피처 | {len(MODEL_FEATURES)} | {full['macro_f1']:.4f} |",
        f"| 직접 규칙 피처 제외 | {len(REDUCED_FEATURES)} | {reduced['macro_f1']:.4f} |",
        "",
        f"Macro-F1 차이(전체-축소)는 **{payload['macro_f1_drop']:.4f}**다. 직접적 레이블 피처 `DELQ_LEVEL`, `REL_INC`, `DSR_PROXY`, `REL_DEBT` 제거 후의 하락폭을 규칙 복제 의존성으로 해석한다.",
        "",
        "## 클래스별 Recall",
        "",
        "| 유형 | 전체 | 축소 |",
        "|---|---:|---:|",
    ]
    for code in CLASS_ORDER:
        lines.append(f"| {code} | {full['class_recall'][code]:.4f} | {reduced['class_recall'][code]:.4f} |")
    report_path = reports / "leakage.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
