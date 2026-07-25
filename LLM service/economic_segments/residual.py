from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "추정 연소득", "income_trajectory", "has_verified_income", "job_turnover",
    "total_loan_balance", "avg_loan_balance", "총대출건수", "dsr",
    "consumption_ratio", "credit_dependency", "cash_advance_flag",
    "total_delinq_cnt", "delinq_severity", "thin_filer", "commute_mismatch",
]


def fit_residual(df: pd.DataFrame, split: pd.Series, outdir: Path, seed: int) -> tuple[pd.DataFrame, dict]:
    frame = df.copy()
    train = split.eq("train") & frame["신용평점"].notna() & frame["score_floor"].eq(0)
    valid = split.eq("valid") & frame["신용평점"].notna() & frame["score_floor"].eq(0)
    test = split.eq("test") & frame["신용평점"].notna() & frame["score_floor"].eq(0)
    candidates = {
        "ridge": Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler()), ("model", Ridge(alpha=10.0))]),
        "random_forest": Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)), ("model", RandomForestRegressor(n_estimators=160, min_samples_leaf=5, max_features=.8, n_jobs=1, random_state=seed))]),
    }
    results = {}
    for name, model in candidates.items():
        model.fit(frame.loc[train, FEATURES], frame.loc[train, "신용평점"])
        pred = model.predict(frame.loc[valid, FEATURES])
        results[name] = {"validation_rmse": float(mean_squared_error(frame.loc[valid, "신용평점"], pred) ** .5), "validation_r2": float(r2_score(frame.loc[valid, "신용평점"], pred))}
    selected = min(results, key=lambda name: results[name]["validation_rmse"])
    model = candidates[selected]
    test_pred = model.predict(frame.loc[test, FEATURES])
    test_metrics = {"rmse": float(mean_squared_error(frame.loc[test, "신용평점"], test_pred) ** .5), "r2": float(r2_score(frame.loc[test, "신용평점"], test_pred))}
    # Keep the selected candidate fitted on train only. Validation selects the
    # model family; it must not become fitting data under the leakage contract.
    expected = model.predict(frame[FEATURES])
    frame["predicted_credit_score"] = expected
    frame["credit_score_residual"] = frame["신용평점"] - expected
    frame.loc[frame["score_floor"].eq(1), "credit_score_residual"] = np.nan
    joblib.dump({"features": FEATURES, "model": model, "selected": selected}, outdir / "score_residual_model.pkl")
    return frame, {"selected": selected, "candidates": results, "test": test_metrics, "floor_rows_excluded": int(frame["score_floor"].sum())}
