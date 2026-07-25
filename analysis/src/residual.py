"""STEP 5 — [학습②] 신용평점 잔차 모델 (method.md §9).

"조건 대비 설명되지 않는 저평점"을 정량 정의한다.
타깃은 실제 관측된 `신용평점`이므로 순환논리가 없다.
신용평점 150(하한 절단) 행은 학습에서 제외한다(§16-5).
연체 변수는 X축(재무 스트레스)에 이미 들어가므로 축 간 중복을 피해 입력에서 뺀다(§9 입력 정의).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C

# 소득 · 대출 · 소비 · 고용 파생변수 (신용평점 및 그 파생물 제외)
RESIDUAL_FEATURES = [
    C.COL_INCOME_Y, C.COL_AGE,
    "has_verified_income", "income_trajectory", "job_turnover",
    "jeonse_income_multiple", "pir", "commute_mismatch",
    "dsr", "total_loan_balance", "avg_loan_balance", "multi_debt",
    "has_mortgage", "has_policy_loan", "is_owner",
    "consumption_ratio", "credit_dependency", "cash_advance_flag",
    "thin_filer",
]


def _design(df: pd.DataFrame) -> pd.DataFrame:
    X = df[RESIDUAL_FEATURES].apply(pd.to_numeric, errors="coerce")
    # 성별 원핫 (2수준) + 직업군 원핫 (코드 의미 부여 금지, §16-4)
    X = X.assign(gender_1=(df[C.COL_GENDER] == 1).astype("int8"))
    for code in sorted(df[C.COL_JOB].dropna().unique()):
        X[f"job_{int(code)}"] = (df[C.COL_JOB] == code).astype("int8")
    return X


def fit_residual(df: pd.DataFrame, outdir: Path, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    X = _design(out)
    y = out[C.COL_SCORE]

    trainable = (out["split"] == "train") & (out["score_floor"] == 0) & y.notna()
    validable = (out["split"] == "valid") & (out["score_floor"] == 0) & y.notna()
    testable = (out["split"] == "test") & (out["score_floor"] == 0) & y.notna()

    candidates = {
        "RandomForestRegressor": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(
                n_estimators=200, min_samples_leaf=20, n_jobs=-1, random_state=seed
            )),
        ]),
        "Ridge": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=1.0, random_state=seed)),
        ]),
    }

    scores: dict[str, dict] = {}
    for name, pipe in candidates.items():
        pipe.fit(X[trainable], y[trainable])
        if "n_jobs" in pipe.named_steps["model"].get_params():
            # 병렬 예측의 누적 순서 차이를 없애 비트 단위 재현성을 확보한다.
            pipe.set_params(model__n_jobs=1)
        pv = np.round(pipe.predict(X[validable]), 6)
        scores[name] = {
            "valid_rmse": float(np.sqrt(mean_squared_error(y[validable], pv))),
            "valid_r2": float(r2_score(y[validable], pv)),
        }

    chosen = min(scores, key=lambda k: scores[k]["valid_rmse"])
    model = candidates[chosen]
    pt = np.round(model.predict(X[testable]), 6)
    metrics = {
        "candidates": scores,
        "chosen": chosen,
        "test_rmse": float(np.sqrt(mean_squared_error(y[testable], pt))),
        "test_r2": float(r2_score(y[testable], pt)),
        "train_rows_used": int(trainable.sum()),
        "score_floor_rows_excluded": int((out["score_floor"] == 1).sum()),
    }

    pred = pd.Series(np.round(model.predict(X), 6), index=out.index)
    out["credit_score_pred"] = pred
    out["credit_score_residual"] = y - pred
    # 하한 절단 행은 잔차가 인위적으로 음수가 되므로 별도 표기 (스코어에서는 NaN 처리)
    out["residual_is_floor"] = out["score_floor"]
    out.loc[out["score_floor"] == 1, "credit_score_residual"] = np.nan

    joblib.dump({"model": model, "features": list(X.columns)}, outdir / "score_residual_model.pkl")

    resid = out["credit_score_residual"]
    metrics["residual_summary"] = {
        "mean": float(resid.mean()), "std": float(resid.std()),
        "p05": float(resid.quantile(0.05)), "median": float(resid.median()),
        "p95": float(resid.quantile(0.95)),
        "nan_rate": float(resid.isna().mean()),
    }
    return out, metrics
