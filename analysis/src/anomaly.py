"""STEP 9 — [학습④] 이상탐지 (method.md §13).

군집 구조가 없어도 Isolation Forest는 작동한다.
탐지된 이상치와 T4(복합 위기군)의 중복률로 규칙 분류의 타당성 또는 추가 발견을 확인한다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C
from .features import DERIVED_ALL


def detect_anomaly(df: pd.DataFrame, outdir: Path, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    cols = [c for c in DERIVED_ALL if c in out.columns]
    X = out[cols].apply(pd.to_numeric, errors="coerce")

    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", IsolationForest(
            contamination=C.ANOMALY_CONTAMINATION, random_state=seed, n_jobs=-1
        )),
    ])
    train_mask = out["split"] == "train"
    pipe.fit(X[train_mask])
    pipe.set_params(model__n_jobs=1)  # 병렬 누적 오차 제거 (재현성)

    pred = pipe.predict(X)  # -1 = 이상치
    out["anomaly"] = (pred == -1).astype("int8")
    out["anomaly_score"] = np.round(pipe.decision_function(X), 9)

    is_t4 = (out["segment"] == "T4")
    anom = out["anomaly"] == 1
    metrics = {
        "features_used": cols,
        "contamination": C.ANOMALY_CONTAMINATION,
        "n_anomalies": int(anom.sum()),
        "anomaly_rate": float(anom.mean()),
        "share_of_anomalies_in_T4": float(is_t4[anom].mean()) if anom.any() else float("nan"),
        "share_of_T4_flagged": float(anom[is_t4].mean()) if is_t4.any() else float("nan"),
        "segment_distribution_of_anomalies": {
            str(k): int(v) for k, v in out.loc[anom, "segment"].value_counts().items()
        },
    }
    metrics["interpretation"] = (
        "T4와 중복이 높다 → 규칙 기반 분류의 타당성 근거"
        if metrics["share_of_anomalies_in_T4"] >= 0.5
        else "T4와 중복이 낮다 → 규칙이 못 잡는 위험군 존재(추가 발견)"
    )

    joblib.dump({"model": pipe, "features": cols}, outdir / "anomaly_model.pkl")
    return out, metrics
