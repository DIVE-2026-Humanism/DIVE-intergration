from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import DERIVED_FEATURES


def detect_anomalies(df: pd.DataFrame, split: pd.Series, outdir: Path, seed: int) -> tuple[pd.DataFrame, dict]:
    features = [c for c in DERIVED_FEATURES + ["credit_score_residual"] if c in df]
    model = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", IsolationForest(n_estimators=200, contamination=.05, n_jobs=1, random_state=seed))])
    model.fit(df.loc[split.eq("train"), features])
    pred = model.predict(df[features])
    result = df.copy()
    result["anomaly"] = (pred == -1).astype("int8")
    detected = result["anomaly"].eq(1)
    overlap = float(result.loc[detected, "segment"].eq("T4").mean()) if detected.any() else 0.0
    t4_recall = float(result.loc[result["segment"].eq("T4"), "anomaly"].mean()) if result["segment"].eq("T4").any() else 0.0
    joblib.dump({"features": features, "pipeline": model}, outdir / "anomaly_model.pkl")
    return result, {"anomaly_count": int(detected.sum()), "anomaly_rate": float(detected.mean()), "t4_share_among_anomalies": overlap, "t4_detection_rate": t4_recall}
