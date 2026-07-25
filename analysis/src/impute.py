"""STEP 3 — [학습①] 전세가 결측 대체 (method.md §7).

`2년내 현거주지평균전세거래가`는 65.7%가 결측이지만 주거 부담을 재는 유일한 직접 지표다.
RandomForest 모델과 구·군 중앙값 베이스라인을 train 홀드아웃에서 비교하고,
이기지 못하면 미련 없이 중앙값을 쓴다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from . import config as C

TARGET = C.COL_JEONSE_2Y
FEATURES = [C.COL_REGION_HOME, C.COL_AGE, C.COL_INCOME_Y, C.COL_IS_APT, C.COL_HOME_PRICE]


def _round(a: np.ndarray) -> np.ndarray:
    """재현성 고정용 반올림. 병렬 누적 오차(~1e-13)보다 큰 자릿수에서 자른다."""
    return np.round(np.asarray(a, dtype=float), 6)


def _design(df: pd.DataFrame, regions: list[int], medians: dict[str, float]) -> pd.DataFrame:
    """원핫(거주지 시군구) + 수치 피처. 결측은 train 중앙값 대입 + 플래그."""
    X = pd.DataFrame(index=df.index)
    region = df[C.COL_REGION_HOME].astype("Int64")
    for r in regions:
        X[f"region_{r}"] = (region == r).astype("int8")
    for col in [C.COL_AGE, C.COL_INCOME_Y, C.COL_IS_APT, C.COL_HOME_PRICE]:
        s = pd.to_numeric(df[col], errors="coerce")
        X[f"{col}__na"] = s.isna().astype("int8")
        X[col] = s.fillna(medians[col])
    return X


def impute_jeonse(df: pd.DataFrame, outdir: Path, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    train = out[out["split"] == "train"]

    regions = sorted(int(r) for r in out[C.COL_REGION_HOME].dropna().unique())
    medians = {c: float(pd.to_numeric(train[c], errors="coerce").median()) for c in
               [C.COL_AGE, C.COL_INCOME_Y, C.COL_IS_APT, C.COL_HOME_PRICE]}

    # 베이스라인: 거주지 시군구별 train 중앙값 (없으면 전체 중앙값)
    obs_train = train[train[TARGET].notna()]
    region_median = obs_train.groupby(C.COL_REGION_HOME)[TARGET].median().to_dict()
    global_median = float(obs_train[TARGET].median())

    def baseline_pred(frame: pd.DataFrame) -> np.ndarray:
        return (
            frame[C.COL_REGION_HOME].map(region_median).fillna(global_median).to_numpy(dtype=float)
        )

    # train 관측분 내부 홀드아웃으로 모델 vs 베이스라인 비교
    fit_idx, hold_idx = train_test_split(obs_train.index.to_numpy(), test_size=0.2, random_state=seed)
    X_all = _design(out, regions, medians)
    y = out[TARGET]

    model = RandomForestRegressor(
        n_estimators=150, min_samples_leaf=20, n_jobs=-1, random_state=seed
    )
    model.fit(X_all.loc[fit_idx], y.loc[fit_idx])
    # 병렬 예측은 누적 순서에 따라 마지막 자리가 흔들린다 → 단일 스레드 + 반올림으로 고정
    model.set_params(n_jobs=1)
    pred_hold = _round(model.predict(X_all.loc[hold_idx]))
    base_hold = baseline_pred(out.loc[hold_idx])

    metrics = {
        "n_observed": int(out[TARGET].notna().sum()),
        "observed_rate": float(out[TARGET].notna().mean()),
        "model_mae": float(mean_absolute_error(y.loc[hold_idx], pred_hold)),
        "model_r2": float(r2_score(y.loc[hold_idx], pred_hold)),
        "baseline_mae": float(mean_absolute_error(y.loc[hold_idx], base_hold)),
        "baseline_r2": float(r2_score(y.loc[hold_idx], base_hold)),
    }
    use_model = metrics["model_mae"] < metrics["baseline_mae"]
    metrics["chosen"] = "RandomForestRegressor" if use_model else "region_median_baseline"

    # 채택안을 train 관측분 전체로 재학습 후 결측 대입
    missing = out[TARGET].isna()
    if use_model:
        model.fit(X_all.loc[obs_train.index], y.loc[obs_train.index])
        model.set_params(n_jobs=1)
        filled = pd.Series(_round(model.predict(X_all[missing])), index=out.index[missing])
        joblib.dump(
            {"model": model, "regions": regions, "medians": medians, "features": FEATURES},
            outdir / "imputer_jeonse.pkl",
        )
    else:
        filled = pd.Series(baseline_pred(out[missing]), index=out.index[missing])
        joblib.dump(
            {"model": None, "region_median": region_median, "global_median": global_median},
            outdir / "imputer_jeonse.pkl",
        )

    out["jeonse_imputed"] = missing.astype("int8")
    out["jeonse_value"] = out[TARGET]
    out.loc[missing, "jeonse_value"] = filled.clip(lower=0)
    metrics["imputed_rows"] = int(missing.sum())
    metrics["region_median"] = {str(k): float(v) for k, v in region_median.items()}
    metrics["global_median"] = global_median
    return out, metrics
