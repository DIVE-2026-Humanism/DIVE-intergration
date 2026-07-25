from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from .config import EMPLOYMENT_AXIS, FINANCIAL_AXIS


def _fit_percentile(series: pd.Series) -> dict:
    clean = series.dropna().astype(float)
    probs = np.linspace(0, 1, 101)
    values = np.quantile(clean, probs) if len(clean) else np.zeros(101)
    return {"probs": probs.tolist(), "values": values.tolist()}


def _apply_percentile(series: pd.Series, params: dict) -> pd.Series:
    values = np.asarray(params["values"], dtype=float)
    probs = np.asarray(params["probs"], dtype=float) * 100
    unique, indices = np.unique(values, return_index=True)
    mapped = np.interp(series.astype(float), unique, probs[indices], left=0, right=100)
    result = pd.Series(mapped, index=series.index)
    return result.where(series.notna(), 50.0)


def _axis(df: pd.DataFrame, train: pd.Series, definition: dict[str, int], name: str) -> tuple[pd.DataFrame, dict]:
    normalized = pd.DataFrame(index=df.index)
    percentile_params = {}
    for feature, direction in definition.items():
        directed = df[feature].astype(float) * direction
        percentile_params[feature] = _fit_percentile(directed.loc[train])
        normalized[feature] = _apply_percentile(directed, percentile_params[feature])
        normalized[f"{feature}__imputed"] = directed.isna().astype("int8")
    values = normalized[list(definition)].loc[train]
    pca = PCA().fit(values)
    pc1 = float(pca.explained_variance_ratio_[0])
    if pc1 >= .40:
        weights = np.abs(pca.components_[0])
        weights /= weights.sum()
        method = "pca_pc1"
    else:
        weights = np.repeat(1 / len(definition), len(definition))
        method = "equal"
    normalized[name] = normalized[list(definition)].to_numpy() @ weights
    return normalized, {
        "pc1_explained_variance": pc1, "weight_method": method,
        "weights": dict(zip(definition, map(float, weights))),
        "percentiles": percentile_params,
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
    }


def build_scores(df: pd.DataFrame, split: pd.Series) -> tuple[pd.DataFrame, dict]:
    train = split.eq("train")
    financial, fp = _axis(df, train, FINANCIAL_AXIS, "financial_stress_score")
    employment, ep = _axis(df, train, EMPLOYMENT_AXIS, "employment_instability_score")
    frame = df.copy()
    for column in financial:
        if column == "financial_stress_score" or column.endswith("__imputed"):
            frame[column] = financial[column]
    for column in employment:
        if column == "employment_instability_score" or column.endswith("__imputed"):
            frame[column] = employment[column]
    params = {"financial_axis": fp, "employment_axis": ep}
    return frame, params
