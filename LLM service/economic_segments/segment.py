from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import DERIVED_FEATURES, SEGMENT_NAMES


def segment(df: pd.DataFrame, split: pd.Series, seed: int) -> tuple[pd.DataFrame, dict]:
    frame = df.copy()
    train = split.eq("train")
    f_cut = float(frame.loc[train, "financial_stress_score"].median())
    e_cut = float(frame.loc[train, "employment_instability_score"].median())
    h_cut = float(frame.loc[train, "jeonse_income_multiple"].quantile(.75))
    labels = pd.Series(index=frame.index, dtype="string")
    labels.loc[frame["파산, 개인회생 신청 여부"].eq(1)] = "T6"
    t5 = labels.isna() & frame["thin_filer"].eq(1) & frame["총대출건수"].eq(0) & frame["score_floor"].eq(1)
    labels.loc[t5] = "T5"
    remaining = labels.isna()
    bad_f = frame["financial_stress_score"].ge(f_cut)
    bad_e = frame["employment_instability_score"].ge(e_cut)
    labels.loc[remaining & ~bad_f & ~bad_e] = "T1"
    labels.loc[remaining & bad_f & ~bad_e] = "T2"
    labels.loc[remaining & ~bad_f & bad_e] = "T3"
    labels.loc[remaining & bad_f & bad_e] = "T4"
    if labels.isna().any():
        raise RuntimeError(f"Unassigned segments: {int(labels.isna().sum())}")
    frame["segment"] = labels
    frame["segment_name"] = labels.map(SEGMENT_NAMES)
    frame["H_flag"] = (frame["jeonse_income_multiple"].ge(h_cut) | frame["commute_mismatch"].eq(1)).astype("int8")
    frame["operational_segment"] = frame["segment"] + np.where(frame["H_flag"].eq(1), "-H", "")

    gmm_features = [c for c in DERIVED_FEATURES + ["credit_score_residual", "신용평점"] if c in frame]
    prep = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("pca", PCA(n_components=3, random_state=seed))])
    train_positions = np.flatnonzero(train.to_numpy())
    rng = np.random.default_rng(seed)
    fit_positions = rng.choice(train_positions, size=min(30_000, len(train_positions)), replace=False)
    train_pca = prep.fit_transform(frame.iloc[fit_positions][gmm_features])
    score_positions = rng.choice(np.arange(len(fit_positions)), size=min(8_000, len(fit_positions)), replace=False)
    diagnostics = []
    models = {}
    for k in range(2, 9):
        model = GaussianMixture(n_components=k, covariance_type="diag", n_init=2, random_state=seed).fit(train_pca)
        pred = model.predict(train_pca)
        sil = float(silhouette_score(train_pca[score_positions], pred[score_positions])) if len(np.unique(pred[score_positions])) > 1 else -1.0
        diagnostics.append({"k": k, "bic": float(model.bic(train_pca)), "silhouette": sil})
        models[k] = model
    best = max(diagnostics, key=lambda item: item["silhouette"])
    best_model = models[best["k"]]
    sample_cluster = best_model.predict(train_pca)
    sample_rules = frame.iloc[fit_positions]["segment"].to_numpy()
    ari = float(adjusted_rand_score(sample_rules, sample_cluster))
    cross = pd.crosstab(pd.Series(sample_cluster, name="cluster"), pd.Series(sample_rules, name="segment"))
    agreement = 0.0
    if cross.size:
        rows, cols = linear_sum_assignment(-cross.to_numpy())
        agreement = float(cross.to_numpy()[rows, cols].sum() / cross.to_numpy().sum())
    # A six-type public contract cannot be preserved when optimal k differs from six.
    # GMM becomes label-driving only for a strong, exactly six-cluster, one-to-one solution.
    authority = "gmm" if best["silhouette"] >= .25 and best["k"] == 6 and agreement >= .50 else "rules"
    if authority == "gmm":
        all_cluster = best_model.predict(prep.transform(frame[gmm_features]))
        mapping = {int(rows[i]): str(cross.columns[cols[i]]) for i in range(len(rows))}
        mapped = pd.Series(all_cluster, index=frame.index).map(mapping)
        # Preserve deterministic T5/T6 rules and use mapped labels for ordinary cases.
        ordinary = ~frame["segment"].isin(["T5", "T6"]) & mapped.notna()
        frame.loc[ordinary, "segment"] = mapped.loc[ordinary]
        frame["segment_name"] = frame["segment"].map(SEGMENT_NAMES)
        frame["operational_segment"] = frame["segment"] + np.where(frame["H_flag"].eq(1), "-H", "")
    counts = frame["segment"].value_counts()
    t3_rate = float(counts.get("T3", 0) / len(frame))
    small_segments = [code for code, count in counts.items() if code != "T6" and count / len(frame) < .05]
    if small_segments:
        warnings.warn(f"T6 제외 5% 미만 유형: {small_segments}")
    if t3_rate < .05:
        warnings.warn("T3 비중이 5% 미만입니다. 고용 불안정과 재무 악화의 강한 연동 가능성을 검토하십시오.")
    params = {
        "financial_cut": f_cut, "employment_cut": e_cut, "housing_q75": h_cut,
        "t5_count": int(t5.sum()), "t5_relaxed_count": int((frame["thin_filer"].eq(1) & frame["score_floor"].eq(1)).sum()),
        "gmm": {"diagnostics": diagnostics, "best_k": best["k"], "best_silhouette": best["silhouette"], "ari": ari, "agreement": agreement, "authority": authority, "sample_rows": len(fit_positions)},
        "segment_counts": {str(k): int(v) for k, v in counts.items()}, "t3_rate": t3_rate,
        "small_segments_below_5pct": small_segments,
    }
    return frame, params
