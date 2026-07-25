"""STEP 6 — 축 스코어 (method.md §10).

방향 통일 → train 기준 분위수 정규화(0~100) → PC1 진단 분기로 가중치 결정.
train에서 산출한 분위수 격자를 저장해 valid/test·실서비스에 그대로 적용한다(누수 방지).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from . import config as C

GRID = np.linspace(0, 100, 101)  # 0~100 퍼센타일 격자


def fit_quantile_grid(train_values: pd.Series) -> list[float]:
    """train 기준 분위수 경계(101점). 저장 후 valid/test·실서비스에 재사용."""
    s = pd.to_numeric(train_values, errors="coerce").dropna()
    if s.empty:
        return [0.0] * len(GRID)
    return [float(v) for v in np.percentile(s, GRID)]


def apply_quantile_grid(values: pd.Series, grid: list[float]) -> pd.Series:
    """저장된 격자로 값을 0~100 퍼센타일에 매핑. NaN은 NaN 유지."""
    s = pd.to_numeric(values, errors="coerce")
    # np.interp는 단조 증가하는 x가 필요하다 (분위수 격자는 이미 비감소).
    knots = np.maximum.accumulate(np.asarray(grid, dtype=float))
    pct = np.interp(s.to_numpy(dtype=float), knots, GRID)
    return pd.Series(pct, index=s.index).where(s.notna())


def build_scores(df: pd.DataFrame, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    train_mask = out["split"] == "train"
    info: dict = {"axes": {}, "quantile_grids": {}}

    axis_columns: dict[str, list[str]] = {}

    for axis_name, spec, score_col in [
        ("financial", C.FINANCIAL_AXIS, C.FINANCIAL_SCORE),
        ("employment", C.EMPLOYMENT_AXIS, C.EMPLOYMENT_SCORE),
    ]:
        pct_cols: list[str] = []
        for var, sign in spec:
            grid = fit_quantile_grid(out.loc[train_mask, var])
            info["quantile_grids"][var] = grid
            pct = apply_quantile_grid(out[var], grid)
            if sign < 0:  # 방향 반전 — 전 변수를 "높을수록 나쁨"으로 통일
                pct = 100 - pct
            col = f"{var}__pct"
            out[f"{col}__imputed"] = pct.isna().astype("int8")
            out[col] = pct.fillna(50.0)  # NaN은 중앙값(50) 대체
            pct_cols.append(col)
        axis_columns[axis_name] = pct_cols

        # ★ 진단 분기 — PC1 설명분산비율로 가중치 결정
        Xtr = out.loc[train_mask, pct_cols].to_numpy(dtype=float)
        pca = PCA(n_components=min(len(pct_cols), Xtr.shape[1]), random_state=seed)
        pca.fit(Xtr - Xtr.mean(axis=0))
        evr = float(pca.explained_variance_ratio_[0])
        loadings = np.abs(pca.components_[0])

        if evr >= C.PC1_WEIGHT_THRESHOLD:
            weights = loadings / loadings.sum()
            mode = "pca_pc1_loading"
        else:
            weights = np.full(len(pct_cols), 1.0 / len(pct_cols))
            mode = "equal"

        out[score_col] = out[pct_cols].to_numpy(dtype=float) @ weights
        out[score_col] = out[score_col].clip(0, 100)

        info["axes"][axis_name] = {
            "score_column": score_col,
            "variables": [v for v, _ in spec],
            "reversed": [v for v, s in spec if s < 0],
            "pc1_evr": evr,
            "explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_],
            "weight_mode": mode,
            "weights": {c: float(w) for c, w in zip(pct_cols, weights)},
            "nan_imputed_rate": {
                c: float(out[f"{c}__imputed"].mean()) for c in pct_cols
            },
        }

    info["axis_columns"] = axis_columns
    return out, info
