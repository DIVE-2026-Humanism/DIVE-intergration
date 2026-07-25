from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

TARGET = "2년내 현거주지평균전세거래가"
CAT = ["거주지 시군구 코드", "연령대", "현 거주지의 아파트여부"]
NUM = ["추정 연소득", "현 거주지의 매매가(국토부 실거래가) 또는 공시가격"]


def fit_imputer(df: pd.DataFrame, split: pd.Series, outdir: Path, seed: int) -> tuple[pd.DataFrame, dict]:
    frame = df.copy()
    observed = frame.index[(split.eq("train")) & frame[TARGET].notna()]
    train_idx, holdout_idx = train_test_split(observed, test_size=.20, random_state=seed)
    transformer = ColumnTransformer([
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("ohe", OneHotEncoder(handle_unknown="ignore"))]), CAT),
        ("num", SimpleImputer(strategy="median"), NUM),
    ])
    model = Pipeline([("prep", transformer), ("model", RandomForestRegressor(n_estimators=120, min_samples_leaf=5, n_jobs=1, random_state=seed))])
    model.fit(frame.loc[train_idx, CAT + NUM], frame.loc[train_idx, TARGET])
    pred = model.predict(frame.loc[holdout_idx, CAT + NUM])
    district_median = frame.loc[train_idx].groupby("거주지 시군구 코드")[TARGET].median()
    global_median = float(frame.loc[train_idx, TARGET].median())
    baseline = frame.loc[holdout_idx, "거주지 시군구 코드"].map(district_median).fillna(global_median)
    model_mae = float(mean_absolute_error(frame.loc[holdout_idx, TARGET], pred))
    baseline_mae = float(mean_absolute_error(frame.loc[holdout_idx, TARGET], baseline))
    use_model = model_mae < baseline_mae
    missing = frame[TARGET].isna()
    frame["jeonse_imputed"] = missing.astype("int8")
    if use_model:
        model.fit(frame.loc[observed, CAT + NUM], frame.loc[observed, TARGET])
        frame.loc[missing, TARGET] = np.maximum(0, model.predict(frame.loc[missing, CAT + NUM]))
        artifact = {"method": "random_forest", "model": model, "district_median": district_median, "global_median": global_median}
    else:
        frame.loc[missing, TARGET] = frame.loc[missing, "거주지 시군구 코드"].map(district_median).fillna(global_median)
        artifact = {"method": "district_median", "model": None, "district_median": district_median, "global_median": global_median}
    joblib.dump(artifact, outdir / "imputer_jeonse.pkl")
    return frame, {"selected": artifact["method"], "model_mae": model_mae, "baseline_mae": baseline_mae, "r2": float(r2_score(frame.loc[holdout_idx, TARGET], pred)), "observed_train": len(observed)}
