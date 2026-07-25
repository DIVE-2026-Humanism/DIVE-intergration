"""잠재 경제상태 모델 — model.md §5.4~§8 구현.

PCA로 잠재 경제요인을 학습하고, 같은 잠재공간에서 종합점수(0~100)와 GMM 6유형을 산출한다.
사람이 만든 점수 공식을 지도학습 타깃으로 쓰지 않는다(가짜 정답 금지).
모든 통계량은 train에서만 적합한다.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from . import config as C


def _design(df: pd.DataFrame) -> pd.DataFrame:
    cols = C.LATENT_RAW_FEATURES + C.LATENT_DERIVED_FEATURES
    return df[cols].apply(pd.to_numeric, errors="coerce")


def fit_latent(df: pd.DataFrame, outdir: Path, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    X = _design(out)
    train = (out["split"] == "train").to_numpy()

    # §5.4 결측 대체(train 중앙값) → 표준화(train 평균·표준편차)
    imputer = SimpleImputer(strategy="median").fit(X[train])
    scaler = StandardScaler().fit(imputer.transform(X[train]))
    Z = pd.DataFrame(scaler.transform(imputer.transform(X)), index=out.index, columns=X.columns)

    # §6 PCA — 누적 설명분산 90% 이상 자동 선택, 점수·GMM은 앞 8개 공통 사용
    pca = PCA(svd_solver="full", random_state=seed).fit(Z[train])
    cum = np.cumsum(pca.explained_variance_ratio_)
    n_components = int(np.searchsorted(cum, C.PCA_VARIANCE_TARGET) + 1)
    latent = pca.transform(Z)[:, : C.LATENT_DIMS]

    # §7.2 안정성 앵커 — 방향만 도메인 지식으로 정하고 가중치는 데이터에서 학습
    pos, neg = Z[C.ANCHOR_POSITIVE], Z[C.ANCHOR_NEGATIVE]
    anchor = (pos.sum(axis=1) - neg.sum(axis=1)) / (len(C.ANCHOR_POSITIVE) + len(C.ANCHOR_NEGATIVE))

    # §7.3 앵커와 절대상관 상위 성분 선택, 가중치는 상관계수를 절댓값 합 1로 정규화
    corrs = np.array([
        float(np.corrcoef(latent[train, i], anchor[train])[0, 1]) for i in range(C.LATENT_DIMS)
    ])
    picked = np.argsort(-np.abs(corrs))[: C.SCORE_COMPONENTS]
    weights = corrs[picked] / np.abs(corrs[picked]).sum()
    raw_stability = latent[:, picked] @ weights

    # §7.4 train 분위수로 0~100 보정
    grid = np.maximum.accumulate(
        np.percentile(raw_stability[train], np.linspace(0, 100, C.SCORE_GRID))
    )
    score = np.interp(raw_stability, grid, np.linspace(0, 100, C.SCORE_GRID))
    out["stability_score"] = score

    # §8 GMM — 잠재공간 재표준화 후 6군집
    latent_scaler = StandardScaler().fit(latent[train])
    L = latent_scaler.transform(latent)
    gmm = GaussianMixture(
        n_components=C.GMM_COMPONENTS, covariance_type=C.GMM_COVARIANCE,
        n_init=C.GMM_N_INIT, reg_covar=C.GMM_REG_COVAR, random_state=seed,
    ).fit(L[train])
    cluster = gmm.predict(L)
    proba = gmm.predict_proba(L)

    # §8.3 군집 평균 종합점수 순으로 E1~E6 부여 (군집번호 자체엔 의미가 없다)
    order = (
        pd.Series(score).groupby(cluster).mean().sort_values(ascending=False).index.tolist()
    )
    mapping = {int(c): C.ETYPE_ORDER[i] for i, c in enumerate(order)}
    out["gmm_cluster"] = cluster
    out["etype"] = pd.Series(cluster, index=out.index).map(mapping)
    out["etype_name"] = out["etype"].map(C.ETYPE_NAMES)
    out["major_class"] = out["etype"].map(C.ETYPE_MAJOR)
    out["type_confidence"] = proba.max(axis=1)
    for i, code in enumerate(C.ETYPE_ORDER):
        src = order[i]
        out[f"proba_{code}"] = proba[:, src]

    rng = np.random.default_rng(seed)
    idx = rng.choice(np.flatnonzero(train), min(10_000, int(train.sum())), replace=False)
    info = {
        "n_features": X.shape[1],
        "pca_components_for_90pct": n_components,
        "pca_explained_variance_ratio": [float(v) for v in pca.explained_variance_ratio_[:12]],
        "latent_dims": C.LATENT_DIMS,
        "score_components": sorted(int(i) for i in picked),
        "score_weights": {int(i): float(w) for i, w in zip(picked, weights)},
        "anchor_correlations": {int(i): float(c) for i, c in enumerate(corrs)},
        "cluster_to_etype": {int(k): v for k, v in mapping.items()},
        "silhouette": float(silhouette_score(L[idx], cluster[idx])),
        "mean_confidence": float(proba.max(axis=1).mean()),
        "low_confidence_share": float((proba.max(axis=1) < 0.5).mean()),
        "sizes": {k: int(v) for k, v in out["etype"].value_counts().reindex(C.ETYPE_ORDER).fillna(0).items()},
    }
    prof = out.groupby("etype")["stability_score"].agg(["mean", "median", "size"]).reindex(C.ETYPE_ORDER)
    info["score_profile"] = {k: {c: float(v[c]) for c in ("mean", "median", "size")}
                             for k, v in prof.iterrows()}
    info["score_monotonic"] = bool(prof["mean"].is_monotonic_decreasing)

    joblib.dump(
        {"imputer": imputer, "scaler": scaler, "pca": pca, "picked": picked,
         "weights": weights, "score_grid": grid, "latent_scaler": latent_scaler,
         "gmm": gmm, "cluster_to_etype": mapping,
         "features": C.LATENT_RAW_FEATURES + C.LATENT_DERIVED_FEATURES},
        outdir / "latent_model.pkl",
    )
    return out, info
