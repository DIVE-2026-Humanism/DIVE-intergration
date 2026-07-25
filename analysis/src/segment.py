"""STEP 7 — 6유형 배정 (method.md §11).

순서 엄수: T6(파산·회생) → T5(신용 무이력) → 잔여 2×2 주 분류 → H flag.
GMM은 §11.4 진단 분기로 주도권을 결정한다(기본값: 규칙 주도, GMM은 검증 근거).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture

from . import config as C


def _rule_assign(df: pd.DataFrame, cuts: dict[str, float]) -> pd.Series:
    seg = pd.Series(pd.NA, index=df.index, dtype="object")

    # (1) 특수 유형 사전 분리 — 결정적 규칙, T6 먼저
    t6 = df[C.COL_BANKRUPT].fillna(0) == 1
    seg[t6] = "T6"

    t5 = (
        (df["thin_filer"] == 1)
        & (df[C.COL_LOAN_CNT].fillna(0) == 0)
        & (df["score_floor"] == 1)
        & seg.isna()
    )
    seg[t5] = "T5"

    # (2) 주 분류 — 잔여에 2×2 (train 중앙값 컷)
    rest = seg.isna()
    fin_high = df[C.FINANCIAL_SCORE] >= cuts["financial"]
    emp_high = df[C.EMPLOYMENT_SCORE] >= cuts["employment"]
    seg[rest & ~fin_high & ~emp_high] = "T1"
    seg[rest & fin_high & ~emp_high] = "T2"
    seg[rest & ~fin_high & emp_high] = "T3"
    seg[rest & fin_high & emp_high] = "T4"
    return seg


def _gmm_diagnostics(df: pd.DataFrame, axis_columns: dict[str, list[str]],
                     rule_labels: pd.Series, seed: int) -> dict:
    cols = axis_columns["financial"] + axis_columns["employment"]
    X = df[cols].to_numpy(dtype=float)
    train_mask = (df["split"] == "train").to_numpy()

    pca = PCA(n_components=3, random_state=seed)
    pca.fit(X[train_mask])
    Z = pca.transform(X)

    rng = np.random.default_rng(seed)
    tr_idx = np.flatnonzero(train_mask)
    fit_idx = rng.choice(tr_idx, size=min(C.GMM_FIT_SAMPLE, tr_idx.size), replace=False)
    sil_idx = rng.choice(fit_idx, size=min(C.GMM_SILHOUETTE_SAMPLE, fit_idx.size), replace=False)

    curve = []
    models: dict[int, GaussianMixture] = {}
    for k in C.GMM_K_RANGE:
        gm = GaussianMixture(n_components=k, covariance_type="full", random_state=seed, n_init=2)
        gm.fit(Z[fit_idx])
        labels = gm.predict(Z[sil_idx])
        sil = float(silhouette_score(Z[sil_idx], labels)) if len(np.unique(labels)) > 1 else float("nan")
        curve.append({"k": int(k), "bic": float(gm.bic(Z[fit_idx])), "silhouette": sil})
        models[k] = gm

    best = min(curve, key=lambda r: r["bic"])
    best_k = int(best["k"])
    best_sil = float(best["silhouette"])
    gmm = models[best_k]
    cluster = pd.Series(gmm.predict(Z), index=df.index, name="gmm_cluster")

    common = rule_labels.notna()
    ari = float(adjusted_rand_score(rule_labels[common].astype(str), cluster[common]))
    crosstab = pd.crosstab(rule_labels[common], cluster[common])
    agreement = float(crosstab.max(axis=0).sum() / crosstab.to_numpy().sum())

    bics = [r["bic"] for r in curve]
    sils = [r["silhouette"] for r in curve]

    return {
        "pca_explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_],
        "curve": curve,
        "best_k_by_bic": best_k,
        "best_k_silhouette": best_sil,
        # BIC가 k 구간 내내 단조 감소하면 최적 k는 탐색 상한에 붙은 것이라 불안정하다.
        "bic_monotonic_decreasing": bool(all(b1 > b2 for b1, b2 in zip(bics, bics[1:]))),
        "silhouette_range": [float(min(sils)), float(max(sils))],
        "ari_vs_rules": ari,
        "agreement_rate": agreement,
        "gmm_led": best_sil >= C.GMM_SILHOUETTE_THRESHOLD,
        "crosstab": crosstab,
        "cluster": cluster,
    }


def segment(df: pd.DataFrame, axis_columns: dict[str, list[str]],
            seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    train = out[out["split"] == "train"]

    cuts = {
        "financial": float(train[C.FINANCIAL_SCORE].quantile(C.SEGMENT_CUT_QUANTILE)),
        "employment": float(train[C.EMPLOYMENT_SCORE].quantile(C.SEGMENT_CUT_QUANTILE)),
    }
    rule_seg = _rule_assign(out, cuts)
    out["segment_rule"] = rule_seg

    info: dict = {"cuts": cuts}

    # T5 규모 점검 — 100건 미만이면 완화 정의를 병기
    t5_n = int((rule_seg == "T5").sum())
    alt_t5 = int(((out["thin_filer"] == 1) & (out[C.COL_LOAN_CNT].fillna(0) == 0)
                  & (rule_seg != "T6")).sum())
    info["t5"] = {
        "count": t5_n,
        "alt_definition": "Thin Filer == 1 AND 총대출건수 == 0 (score_floor 조건 완화)",
        "alt_count": alt_t5,
        "alt_reported": t5_n < C.T5_MIN_COUNT,
    }

    # ★ GMM 진단 분기
    gmm = _gmm_diagnostics(out, axis_columns, rule_seg, seed)
    out["gmm_cluster"] = gmm["cluster"]
    info["gmm"] = {k: v for k, v in gmm.items() if k not in ("crosstab", "cluster")}
    info["gmm_crosstab"] = gmm["crosstab"]

    if gmm["gmm_led"]:
        # 군집을 최종 라벨로 삼고 규칙은 사후 근사 — 특수 유형(T5·T6)은 결정적 규칙 유지
        special = rule_seg.isin(["T5", "T6"])
        mapping = (
            pd.crosstab(out.loc[~special, "gmm_cluster"], rule_seg[~special])
            .idxmax(axis=1)
            .to_dict()
        )
        covered = sorted(set(mapping.values()))
        info["gmm_cluster_to_segment"] = {int(k): v for k, v in mapping.items()}
        info["gmm_mapped_types"] = covered

        # 안전장치: 군집이 단일 축으로만 갈려 2×2 설계를 표현하지 못하면(주 유형 2개 이하)
        # GMM 라벨을 채택할 수 없다. 이 경우 규칙 주도로 폴백하고 그 사실을 리포트에 남긴다.
        if len(covered) >= 3:
            final = rule_seg.copy()
            final[~special] = out.loc[~special, "gmm_cluster"].map(mapping)
            info["label_source"] = "gmm"
            info["gmm_fallback_reason"] = None
        else:
            final = rule_seg
            info["label_source"] = "rule_fallback"
            info["gmm_fallback_reason"] = (
                f"실루엣 {gmm['best_k_silhouette']:.3f} ≥ {C.GMM_SILHOUETTE_THRESHOLD}로 GMM 주도 조건은 "
                f"충족했으나, k={gmm['best_k_by_bic']} 군집이 주 유형 {covered}만 표현해 "
                "2×2 설계(T1~T4)를 담지 못한다. 군집은 재무 축 한 방향으로만 갈렸다. "
                "GMM 라벨을 채택하면 T2·T3가 소멸하므로 규칙 주도로 폴백했다."
            )
    else:
        final = rule_seg
        info["label_source"] = "rule"
        info["gmm_fallback_reason"] = None

    out["segment"] = final
    out["segment_name"] = out["segment"].map(C.SEGMENT_NAMES)

    # 11.2 주거 부담 수정자 (H flag)
    h_cut = float(train["jeonse_income_multiple"].quantile(C.H_FLAG_QUANTILE))
    h_jeonse = out["jeonse_income_multiple"] >= h_cut
    h_commute = out["commute_mismatch"] == 1
    out["H_flag"] = (h_jeonse | h_commute).astype("int8")
    out["segment_ops"] = out["segment"] + np.where(out["H_flag"] == 1, "-H", "")
    info["h_flag"] = {
        "jeonse_income_multiple_cut": h_cut,
        "share": float(out["H_flag"].mean()),
        "share_jeonse_only": float(h_jeonse.mean()),
        "share_commute_only": float(h_commute.mean()),
    }

    # 11.3 크기 점검
    sizes = out["segment"].value_counts().reindex(C.SEGMENT_ORDER).fillna(0).astype(int)
    shares = sizes / len(out)
    info["sizes"] = {k: int(v) for k, v in sizes.items()}
    info["shares"] = {k: float(v) for k, v in shares.items()}
    info["unassigned"] = int(out["segment"].isna().sum())

    warnings_list: list[str] = []
    for seg_id in C.SEGMENT_ORDER:
        # T5·T6는 결정적 규칙으로 분리되는 특수 유형이라 규모 경고 대상이 아니다.
        if seg_id in C.SPECIAL_SEGMENTS:
            continue
        if shares.get(seg_id, 0) < C.MIN_SEGMENT_SHARE:
            warnings_list.append(
                f"[WARNING] {seg_id}({C.SEGMENT_NAMES[seg_id]}) 비중이 "
                f"{shares.get(seg_id, 0):.2%}로 {C.MIN_SEGMENT_SHARE:.0%} 미만입니다."
            )
    if shares.get("T3", 0) < C.MIN_SEGMENT_SHARE:
        warnings_list.append(
            "[WARNING] T3(잠재 불안군) 비중이 임계 이하입니다.\n"
            "합성데이터가 고용 불안정과 재무 악화를 강하게 연동시켜 생성되었을 가능성이 있습니다.\n"
            "'사각지대' 서사 대신 '고용 불안정 → 재무 악화 직결' 서사로 전환을 검토하십시오."
        )
    info["warnings"] = warnings_list
    info["t3_share"] = float(shares.get("T3", 0))
    return out, info
