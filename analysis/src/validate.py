"""STEP 10 — 검증 리포트 (method.md §14).

`validation_report.md` · `segment_profile.csv` · `outputs/figures/*.png` 생성.
효과크기(eta squared)로 해석한다 — n=10만에서는 p값이 전부 유의하다(§16-8).
그림 라벨은 ASCII로 쓴다(한글 폰트 미보장 환경 대비). 리포트 본문은 한국어다.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from . import config as C
from .features import DERIVED_NUMERIC, DERIVED_ALL
from .reduced_model import OBSERVABLE_IN_QUESTIONNAIRE

PROFILE_METRICS = [
    C.COL_INCOME_Y, "dsr", C.COL_SCORE, "job_turnover", "income_trajectory",
    "consumption_ratio", "jeonse_income_multiple", "credit_score_residual",
    "delinq_rate", C.FINANCIAL_SCORE, C.EMPLOYMENT_SCORE,
]

SEGMENT_COLORS = {
    "T1": "#2a9d8f", "T2": "#e9c46a", "T3": "#457b9d",
    "T4": "#e76f51", "T5": "#8d99ae", "T6": "#6a4c93",
}


def _with_delinq_rate(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["delinq_rate"] = (out["total_delinq_cnt"].fillna(0) > 0).astype(float)
    return out


def segment_profile(df: pd.DataFrame) -> pd.DataFrame:
    d = _with_delinq_rate(df)
    rows = []
    for seg in C.SEGMENT_ORDER:
        sub = d[d["segment"] == seg]
        if sub.empty:
            continue
        row = {
            "segment": seg,
            "segment_name": C.SEGMENT_NAMES[seg],
            "n": len(sub),
            "share": len(sub) / len(d),
            "H_flag_share": float(sub["H_flag"].mean()),
        }
        for m in PROFILE_METRICS:
            s = pd.to_numeric(sub[m], errors="coerce")
            row[f"{m}__mean"] = float(s.mean())
            row[f"{m}__median"] = float(s.median())
        rows.append(row)
    return pd.DataFrame(rows)


def effect_sizes(df: pd.DataFrame) -> pd.DataFrame:
    """일원배치 ANOVA + eta squared. p값이 아니라 효과크기로 읽는다."""
    d = _with_delinq_rate(df)
    rows = []
    for m in PROFILE_METRICS:
        groups = [
            pd.to_numeric(d.loc[d["segment"] == seg, m], errors="coerce").dropna().to_numpy()
            for seg in C.SEGMENT_ORDER
        ]
        groups = [g for g in groups if len(g) > 1]
        if len(groups) < 2:
            continue
        f, p = stats.f_oneway(*groups)
        allv = np.concatenate(groups)
        grand = allv.mean()
        ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
        ss_total = ((allv - grand) ** 2).sum()
        eta2 = float(ss_between / ss_total) if ss_total > 0 else float("nan")
        rows.append({
            "metric": m, "F": float(f), "p": float(p), "eta_squared": eta2,
            "effect": "large" if eta2 >= 0.14 else "medium" if eta2 >= 0.06 else "small",
        })
    return pd.DataFrame(rows).sort_values("eta_squared", ascending=False)


# ---------------------------------------------------------------- 시각화
def _savefig(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def make_figures(df: pd.DataFrame, info: dict, figdir: Path, seed: int = C.SEED) -> None:
    figdir.mkdir(parents=True, exist_ok=True)
    d = _with_delinq_rate(df)
    rng = np.random.default_rng(seed)

    # 1) 2축 산점도 + 사분면 경계
    sample = d.sample(min(8000, len(d)), random_state=seed)
    fig, ax = plt.subplots(figsize=(7, 6))
    for seg, sub in sample.groupby("segment"):
        ax.scatter(sub[C.FINANCIAL_SCORE], sub[C.EMPLOYMENT_SCORE], s=5, alpha=0.45,
                   label=seg, color=SEGMENT_COLORS.get(seg, "#999999"))
    cuts = info["segment"]["cuts"]
    ax.axvline(cuts["financial"], color="black", lw=1, ls="--")
    ax.axhline(cuts["employment"], color="black", lw=1, ls="--")
    ax.set_xlabel("financial_stress_score (higher = worse)")
    ax.set_ylabel("employment_instability_score (higher = worse)")
    ax.set_title("Segment scatter (train-median cuts)")
    ax.legend(markerscale=3, fontsize=8)
    _savefig(fig, figdir / "segment_scatter.png")

    # 2) 유형별 규모
    sizes = d["segment"].value_counts().reindex(C.SEGMENT_ORDER).fillna(0)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(sizes.index, sizes.to_numpy(),
           color=[SEGMENT_COLORS.get(s, "#999999") for s in sizes.index])
    for i, v in enumerate(sizes.to_numpy()):
        ax.text(i, v, f"{int(v):,}\n{v / len(d):.1%}", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("rows")
    ax.set_title("Segment size")
    ax.set_ylim(0, sizes.max() * 1.2)
    _savefig(fig, figdir / "segment_size.png")

    # 3) 상관행렬 (원본 수치 + 파생)
    raw_cols = [c for c in C.RAW_COLUMNS if c in d.columns and c not in C.CATEGORICAL_COLUMNS]
    corr_cols = raw_cols + [c for c in DERIVED_NUMERIC if c in d.columns] + ["credit_score_residual"]
    corr = d[corr_cols].apply(pd.to_numeric, errors="coerce").corr()
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(corr_cols)))
    ax.set_yticks(range(len(corr_cols)))
    labels = [f"c{i}" for i in range(len(corr_cols))]
    ax.set_xticklabels(labels, fontsize=6, rotation=90)
    ax.set_yticklabels(labels, fontsize=6)
    ax.set_title("Correlation matrix (see correlation_matrix.csv for names)")
    fig.colorbar(im, ax=ax, shrink=0.7)
    _savefig(fig, figdir / "correlation_heatmap.png")
    corr.to_csv(figdir.parent / "correlation_matrix.csv", encoding="utf-8-sig")

    # 4) 축별 설명분산비율
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, (axis_name, meta) in zip(axes, info["scores"]["axes"].items()):
        evr = meta["explained_variance_ratio"]
        ax.bar(range(1, len(evr) + 1), evr, color="#457b9d")
        ax.axhline(C.PC1_WEIGHT_THRESHOLD, color="red", ls="--", lw=1)
        ax.set_title(f"{axis_name} axis  PC1={meta['pc1_evr']:.1%} → {meta['weight_mode']}")
        ax.set_xlabel("component")
        ax.set_ylabel("explained variance ratio")
    _savefig(fig, figdir / "pca_scree.png")

    # 5) GMM BIC / 실루엣 곡선
    curve = pd.DataFrame(info["segment"]["gmm"]["curve"])
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(curve["k"], curve["bic"], "o-", color="#264653", label="BIC")
    ax1.set_xlabel("k")
    ax1.set_ylabel("BIC")
    ax2 = ax1.twinx()
    ax2.plot(curve["k"], curve["silhouette"], "s--", color="#e76f51", label="silhouette")
    ax2.axhline(C.GMM_SILHOUETTE_THRESHOLD, color="red", ls=":", lw=1)
    ax2.set_ylabel("silhouette")
    ax1.set_title("GMM model selection (PCA 3D)")
    fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.88), fontsize=8)
    _savefig(fig, figdir / "gmm_selection.png")

    # 6) 신용평점 잔차 분포 (유형별)
    fig, ax = plt.subplots(figsize=(7, 4))
    for seg in C.SEGMENT_ORDER:
        s = pd.to_numeric(d.loc[d["segment"] == seg, "credit_score_residual"], errors="coerce").dropna()
        if len(s) < 10:
            continue
        ax.hist(s, bins=60, histtype="step", density=True, label=seg,
                color=SEGMENT_COLORS.get(seg, "#999999"))
    ax.axvline(0, color="black", lw=1)
    ax.set_xlabel("credit score residual (actual - predicted)")
    ax.set_ylabel("density")
    ax.set_title("Credit score residual by segment")
    ax.legend(fontsize=8)
    _savefig(fig, figdir / "residual_dist.png")

    # 7) 축소 분류기 혼동행렬
    cm_info = info["reduced"]["confusion_matrix"]
    cm = np.array(cm_info["matrix"], dtype=float)
    cm_norm = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(cm_info["labels"])), cm_info["labels"])
    ax.set_yticks(range(len(cm_info["labels"])), cm_info["labels"])
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, f"{cm_norm[i, j]:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if cm_norm[i, j] > 0.5 else "black")
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title("Reduced 8-question classifier (test, row-normalized)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    _savefig(fig, figdir / "confusion_matrix.png")

    # 8) 유형별 레이더 (분위수 평균)
    radar_metrics = ["dsr", "consumption_ratio", "delinq_rate", "job_turnover",
                     "jeonse_income_multiple", "total_loan_balance"]
    ranked = d[radar_metrics].apply(lambda s: pd.to_numeric(s, errors="coerce").rank(pct=True))
    ranked["segment"] = d["segment"]
    means = ranked.groupby("segment").mean().reindex(C.SEGMENT_ORDER).dropna(how="all")
    angles = np.linspace(0, 2 * np.pi, len(radar_metrics), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6.5, 6.5), subplot_kw={"polar": True})
    for seg, row in means.iterrows():
        vals = row[radar_metrics].tolist()
        vals += vals[:1]
        ax.plot(angles, vals, label=seg, color=SEGMENT_COLORS.get(seg, "#999999"))
        ax.fill(angles, vals, alpha=0.08, color=SEGMENT_COLORS.get(seg, "#999999"))
    ax.set_xticks(angles[:-1], radar_metrics, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_title("Segment profile (percentile mean)")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=8)
    _savefig(fig, figdir / "radar_by_segment.png")


# ---------------------------------------------------------------- 리포트
def _fmt_table(df: pd.DataFrame, floatfmt: str = "{:,.3f}") -> list[str]:
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "|".join(["---"] * len(df.columns)) + "|"
    lines = [header, sep]
    for _, r in df.iterrows():
        cells = []
        for v in r:
            if isinstance(v, (int, np.integer)):
                cells.append(f"{int(v):,}")
            elif isinstance(v, (float, np.floating)):
                cells.append("-" if pd.isna(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def write_report(df: pd.DataFrame, info: dict, outdir: Path) -> None:
    d = _with_delinq_rate(df)
    profile = segment_profile(df)
    profile.to_csv(outdir / "segment_profile.csv", index=False, encoding="utf-8-sig")
    eff = effect_sizes(df)

    seg_info = info["segment"]
    sc_info = info["scores"]
    L: list[str] = []
    L.append("# validation_report.md — 부산 청년 1인가구 경제 계층 6유형 분류\n")
    L.append("> **유형 라벨은 개인 신용 판정이 아니라 정책 아웃리치 우선순위다.** "
             "개인에 대한 낙인으로 사용해서는 안 된다.\n")

    # ---- 최상단: T3 강조 + 경고
    t3_n = seg_info["sizes"].get("T3", 0)
    L.append("## ★ T3(잠재 불안군) 규모 — 최우선 확인 지표\n")
    L.append(f"**T3 = {t3_n:,}명 ({seg_info['t3_share']:.2%})** "
             f"— 재무는 안정으로 보이나 고용이 불안한 사각지대 후보.\n")
    if seg_info["warnings"]:
        L.append("```")
        L.extend(seg_info["warnings"])
        L.append("```\n")
    else:
        L.append("모든 유형이 5% 이상으로 배정되었다(T6 제외 기준 경고 없음).\n")

    # 1. 데이터 개요
    load_info = info["load"]
    L.append("## 1. 데이터 개요\n")
    L.append(f"- 입력: **{info['n_rows']:,}행 × {len(C.RAW_COLUMNS)}열** → "
             f"제거 후 **{load_info['n_columns_after']}열**")
    L.append(f"- 분할: train {info['split_counts']['train']:,} / "
             f"valid {info['split_counts']['valid']:,} / test {info['split_counts']['test']:,} "
             "(stratify = 연령대 × 성별)")
    L.append(f"- 시드: {info['seed']} · 센티널 `{C.SENTINEL}` → NaN + `__missing` 플래그 보존\n")
    L.append("### 제거된 열과 사유\n")
    L.append("| 열 | 사유 |")
    L.append("|---|---|")
    for col in load_info["dropped_columns"]:
        reason = C.EXCLUSION_REASONS.get(col)
        if reason is None:
            rate = info["consistency"]["provisional_rates"].get(col, float("nan"))
            reason = f"§4.4 보류 열 — 판정 검사 위반율 {rate:.2%} > {C.PROVISIONAL_VIOLATION_THRESHOLD:.0%}"
        L.append(f"| `{col}` | {reason} |")
    unit = load_info["income_unit_check"]
    L.append("")
    L.append(f"**단위 가정**: `추정월소득×12 ÷ 추정 연소득` 중앙값 "
             f"{unit['월소득×12 / 연소득 중앙값']:.3f} (±20% 이내 {unit['±20% 이내 비율']:.1%}) "
             "→ 금액은 천원 단위로 가정.\n")

    # 2. 유형별 규모
    L.append("## 2. 유형별 규모\n")
    size_tbl = pd.DataFrame({
        "유형": C.SEGMENT_ORDER,
        "명칭": [C.SEGMENT_NAMES[s] for s in C.SEGMENT_ORDER],
        "건수": [seg_info["sizes"].get(s, 0) for s in C.SEGMENT_ORDER],
        "비중": [seg_info["shares"].get(s, 0.0) for s in C.SEGMENT_ORDER],
        "H flag 비중": [
            float(d.loc[d["segment"] == s, "H_flag"].mean()) if (d["segment"] == s).any() else np.nan
            for s in C.SEGMENT_ORDER
        ],
    })
    L.extend(_fmt_table(size_tbl, "{:.2%}"))
    L.append("")
    L.append(f"- 미분류 행: **{seg_info['unassigned']}건**")
    label_source_text = {
        "gmm": "GMM 주도 (군집을 최종 라벨로 채택, 규칙은 사후 근사)",
        "rule": "규칙 주도 (군집 구조 미확인 → GMM은 검증 근거로만 사용)",
        "rule_fallback": "규칙 주도 — **GMM 주도 조건 충족했으나 폴백** (아래 §6 참조)",
    }[seg_info["label_source"]]
    L.append(f"- 라벨 주도권: **{label_source_text}**")
    L.append(f"- T5 정의 적용 결과 {seg_info['t5']['count']:,}건" +
             (f" — 100건 미만이므로 완화 정의({seg_info['t5']['alt_definition']}) "
              f"{seg_info['t5']['alt_count']:,}건을 병기한다."
              if seg_info["t5"]["alt_reported"] else ""))
    hf = seg_info["h_flag"]
    L.append(f"- H flag(주거 부담 수정자) 전체 비중 {hf['share']:.2%} "
             f"= jeonse_income_multiple 상위 25%({hf['share_jeonse_only']:.2%}, "
             f"컷 {hf['jeonse_income_multiple_cut']:.3f}) **OR** "
             f"commute_mismatch({hf['share_commute_only']:.2%})")
    if hf["share_commute_only"] >= 0.50:
        L.append("  - ⚠ `commute_mismatch`가 과반이라 H flag가 사실상 포화된다. "
                 "부산 내 구·군 간 통근이 일반적이므로, 운영 12구분을 쓰려면 "
                 "H 정의를 주거비 단독 기준으로 좁히거나 통근 조건을 "
                 "'거주지 ≠ 근무지 AND 주거비 상위 50%'로 조합할 것을 권한다(발제팀 합의 필요).")
    L.append("")

    # 3. 세그먼트 프로파일
    L.append("## 3. 세그먼트 프로파일 (평균)\n")
    prof_view = profile[["segment", "segment_name", "n"] +
                        [f"{m}__mean" for m in PROFILE_METRICS]].copy()
    prof_view.columns = ["유형", "명칭", "n"] + PROFILE_METRICS
    L.extend(_fmt_table(prof_view))
    L.append("\n전체 표(평균·중앙값)는 `segment_profile.csv` 참조.\n")

    # 4. 효과크기
    L.append("## 4. 유형 간 차이 검정 — ANOVA + eta squared\n")
    L.append("n=10만에서는 p값이 사실상 전부 유의하므로 **효과크기(eta²)로 해석한다.**\n")
    eff_view = eff.copy()
    eff_view["p"] = eff_view["p"].map(lambda v: "<1e-300" if v == 0 else f"{v:.3g}")
    L.extend(_fmt_table(eff_view))
    L.append("")

    # 5. 교차표
    L.append("## 5. 교차표 (행 비율)\n")
    for col, title in [(C.COL_AGE, "연령대"), (C.COL_GENDER, "성별"),
                       (C.COL_REGION_HOME, "거주 구·군"), (C.COL_JOB, "직업군")]:
        ct = pd.crosstab(d["segment"], d[col], normalize="index").reindex(C.SEGMENT_ORDER).dropna(how="all")
        ct = ct.reset_index().rename(columns={"segment": "유형"})
        ct.columns = [str(c) for c in ct.columns]
        L.append(f"### 유형 × {title}\n")
        L.extend(_fmt_table(ct, "{:.1%}"))
        L.append("")

    # 6. 진단 분기 결과
    L.append("## 6. 진단 분기 결과\n")
    L.append("### 축별 PC1과 가중치 (§10.2)\n")
    L.append("| 축 | 변수 수 | PC1 설명분산비율 | 임계 | 채택 가중 |")
    L.append("|---|---:|---:|---:|---|")
    for axis_name, meta in sc_info["axes"].items():
        L.append(f"| {axis_name} ({meta['score_column']}) | {len(meta['variables'])} | "
                 f"{meta['pc1_evr']:.1%} | {C.PC1_WEIGHT_THRESHOLD:.0%} | "
                 f"{'PCA 제1주성분 로딩' if meta['weight_mode'] == 'pca_pc1_loading' else '균등가중'} |")
    L.append("")
    for axis_name, meta in sc_info["axes"].items():
        w = ", ".join(f"{k.replace('__pct', '')} {v:.3f}" for k, v in meta["weights"].items())
        L.append(f"- **{axis_name}** 가중치: {w}")
    L.append("")

    gmm = seg_info["gmm"]
    L.append("### GMM 군집 구조 검증 (§11.4)\n")
    L.append(f"- PCA 3차원 설명분산비율: "
             f"{', '.join(f'{v:.1%}' for v in gmm['pca_explained_variance_ratio'])}")
    L.append(f"- BIC 최적 k = **{gmm['best_k_by_bic']}**, 해당 k의 실루엣 = **{gmm['best_k_silhouette']:.3f}** "
             f"(임계 {C.GMM_SILHOUETTE_THRESHOLD})")
    L.append(f"- 규칙 라벨과의 ARI = {gmm['ari_vs_rules']:.3f}, 일치율 = {gmm['agreement_rate']:.1%}")
    L.append(f"- 실루엣 범위(k=2~8) {gmm['silhouette_range'][0]:.3f} ~ {gmm['silhouette_range'][1]:.3f}"
             + (" · BIC가 k 구간 내내 **단조 감소**해 최적 k가 탐색 상한에 붙었다(k 선택 불안정)."
                if gmm["bic_monotonic_decreasing"] else "") + "\n")
    L.extend(_fmt_table(pd.DataFrame(gmm["curve"])))
    L.append("")
    if seg_info["label_source"] == "rule_fallback":
        L.append(f"> **GMM 주도 판정 후 폴백.** {seg_info['gmm_fallback_reason']}")
        L.append(f"> 군집 → 유형 다수결 매핑 결과: `{seg_info['gmm_cluster_to_segment']}`")
        L.append("> 실루엣이 임계를 간신히 넘었고(k 전 구간 "
                 f"{gmm['silhouette_range'][0]:.2f}~{gmm['silhouette_range'][1]:.2f}로 평탄) "
                 "군집이 재무 축 한 방향으로만 갈렸다는 사실 자체가 결과다 — "
                 "**\"비지도 적용 가능성을 정량 검증하고, 채택 시 2×2 설계가 붕괴함을 근거와 함께 제시했다\"**로 "
                 "발표에 쓸 것. 임계값 조정이 필요하면 `config.GMM_SILHOUETTE_THRESHOLD`에서 바꾼다.\n")
    elif gmm["gmm_led"]:
        L.append(f"> 데이터가 자연 형성한 군집과 규칙 분류가 {gmm['agreement_rate']:.0%} 일치한다. "
                 "군집을 최종 라벨로 채택하고 규칙은 사후 근사로 사용했다.\n")
    else:
        L.append(f"> 군집 구조가 통계적으로 확인되지 않아(실루엣 {gmm['best_k_silhouette']:.2f}) "
                 "도메인 규칙 기반으로 설계했다. 비지도 적용 가능성을 먼저 검증하고 "
                 "불가 판정을 정량 근거와 함께 제시한 것이 이 파이프라인의 설계 근거다.\n")
    L.append("**규칙 라벨 × GMM 군집 교차표**\n")
    ct = info["segment"]["gmm_crosstab"] if "gmm_crosstab" in info["segment"] else None
    if ct is None:
        ct = info.get("gmm_crosstab")
    if ct is not None:
        ct2 = ct.reset_index()
        ct2.columns = [str(c) for c in ct2.columns]
        L.extend(_fmt_table(ct2))
        L.append("")

    # 7. 학습 모델 성능
    L.append("## 7. 학습 모델 성능 (4종)\n")
    imp = info["impute"]
    L.append("### ① 전세가 결측 대체 (STEP 3)\n")
    L.append(f"- 관측 {imp['n_observed']:,}건({imp['observed_rate']:.1%}), 대체 {imp['imputed_rows']:,}건")
    L.append(f"- RandomForest MAE {imp['model_mae']:,.1f} / R² {imp['model_r2']:.3f}")
    L.append(f"- 구·군 중앙값 베이스라인 MAE {imp['baseline_mae']:,.1f} / R² {imp['baseline_r2']:.3f}")
    L.append(f"- **채택: {imp['chosen']}**\n")

    res = info["residual"]
    L.append("### ② 신용평점 잔차 (STEP 5) ★\n")
    for name, m in res["candidates"].items():
        L.append(f"- {name}: valid RMSE {m['valid_rmse']:.2f} / R² {m['valid_r2']:.3f}")
    L.append(f"- **채택: {res['chosen']}** — test RMSE {res['test_rmse']:.2f} / R² {res['test_r2']:.3f}")
    L.append(f"- 학습 사용 행 {res['train_rows_used']:,} "
             f"(신용평점 150 하한 절단 {res['score_floor_rows_excluded']:,}행 제외)")
    rs = res["residual_summary"]
    L.append(f"- 잔차 분포: 평균 {rs['mean']:.2f} / 표준편차 {rs['std']:.2f} / "
             f"p05 {rs['p05']:.1f} / p95 {rs['p95']:.1f}\n")

    red = info["reduced"]
    L.append("### ③ 8문항 축소 분류기 (STEP 8) ★ 필수\n")
    sp = red["special_handling"]
    L.append(f"**T5·T6는 모델 타깃에서 분리했다.** 두 유형은 §11.1 결정적 규칙으로만 배정되고 "
             "사용자가 문진에서 직접 답할 수 있는 사실이므로, 모델 앞단 **스크리닝 2문항**으로 처리한다. "
             f"해당 {sp['rows_screened']:,}행({sp['screened_share']:.2%})은 규칙으로 100% 배정되고, "
             f"모델은 주 4유형 {sp['model_target_classes']}만 학습·평가한다"
             f"(학습 {sp['model_train_rows']:,}행).\n")
    for seg_id, q in sp["screening_questions"].items():
        L.append(f"- **{seg_id}** — {q}")
    L.append("")
    dt, lr = red["decision_tree"], red["logistic_regression"]
    L.append(f"- DecisionTree(max_depth={red['chosen_depth']}): test accuracy {dt['test_accuracy']:.3f} / "
             f"macro F1 {dt['test_macro_f1']:.3f} / CV macro F1 "
             f"{dt['cv_macro_f1_mean']:.3f}±{dt['cv_macro_f1_std']:.3f}")
    L.append(f"- LogisticRegression(비교군): test accuracy {lr['test_accuracy']:.3f} / "
             f"macro F1 {lr['test_macro_f1']:.3f} / CV macro F1 "
             f"{lr['cv_macro_f1_mean']:.3f}±{lr['cv_macro_f1_std']:.3f}")
    conf = red["confidence"]
    L.append(f"- 확신도(predict_proba 최대값): 평균 {conf['mean']:.3f} / 중앙값 {conf['median']:.3f} / "
             f"0.5 미만 {conf['share_below_0.5']:.1%} / 0.7 미만 {conf['share_below_0.7']:.1%} "
             "→ 확신도 낮은 구간은 추가 질문 트리거 대상")
    L.append(f"- **핵심 지표: {red['reproduction_sentence']}**\n")

    # 재현율의 상한을 정하는 것은 "축 가중치가 어디에 실렸는가"다.
    L.append("**재현율 해석 — 축 가중치의 관측 가능성**\n")
    L.append("| 축 | 8문항으로 관측 불가한 변수 가중치 합 | 상위 가중 변수 |")
    L.append("|---|---:|---|")
    for axis_name, meta in sc_info["axes"].items():
        weights = {k.replace("__pct", ""): v for k, v in meta["weights"].items()}
        unobs = sum(v for k, v in weights.items() if k not in OBSERVABLE_IN_QUESTIONNAIRE)
        top = sorted(weights.items(), key=lambda kv: -kv[1])[:2]
        L.append(f"| {axis_name} | {unobs:.1%} | " +
                 ", ".join(f"`{k}` {v:.1%}" for k, v in top) + " |")
    L.append("")
    L.append("> 라벨을 만든 축 가중치가 `신용평점`·`consumption_ratio`처럼 **사용자가 답할 수 없는 변수**에 "
             "몰릴수록 8문항 재현율의 상한은 낮아진다. 재현율을 올리려면 모델을 바꾸는 게 아니라 "
             "① 문진 항목을 축 상위 가중 변수에 맞추거나(예: 카드 소비 규모 질문 추가), "
             "② 축 가중치를 균등가중으로 고정(`config.PC1_WEIGHT_THRESHOLD` 상향)해야 한다.")
    L.append("> 지표는 주 4유형(T1~T4) 기준이다. T5·T6를 타깃에 넣으면 "
             "`class_weight='balanced'`(§12.2)가 700행 규모의 극소 클래스에 트리 용량을 몰아주어 "
             "macro F1이 오히려 떨어진다 — 분리 처리의 직접 근거다.\n")
    L.append("**클래스별 성능 (DecisionTree, test)**\n")
    rep = pd.DataFrame(dt["report"]).T.reset_index().rename(columns={"index": "class"})
    rep = rep[rep["class"].isin(C.SEGMENT_ORDER)].copy()
    rep["support"] = rep["support"].astype(int)
    L.extend(_fmt_table(rep))
    L.append("")

    an = info["anomaly"]
    L.append("### ④ 이상탐지 (STEP 9)\n")
    L.append(f"- IsolationForest(contamination={an['contamination']}) → 이상치 {an['n_anomalies']:,}건 "
             f"({an['anomaly_rate']:.2%})")
    L.append(f"- 이상치 중 T4 비중 {an['share_of_anomalies_in_T4']:.1%} / "
             f"T4 중 이상치로 탐지된 비중 {an['share_of_T4_flagged']:.1%}")
    L.append(f"- 해석: {an['interpretation']}\n")

    # 8. 상관행렬
    L.append("## 8. 상관행렬 요약\n")
    corr_cols = [c for c in DERIVED_NUMERIC if c in d.columns] + ["credit_score_residual",
                                                                  C.COL_SCORE, C.COL_INCOME_Y]
    corr = d[corr_cols].apply(pd.to_numeric, errors="coerce").corr()
    pairs = (
        corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        .stack().reset_index()
    )
    pairs.columns = ["var1", "var2", "corr"]
    pairs["abs"] = pairs["corr"].abs()
    top = pairs.sort_values("abs", ascending=False).head(12)[["var1", "var2", "corr"]]
    L.append("**절대상관 상위 12쌍**\n")
    L.extend(_fmt_table(top))
    L.append("")
    L.append(f"- 파생변수 평균 |상관| = {pairs['abs'].mean():.3f} "
             "(전체 상관행렬은 `correlation_matrix.csv`)")
    top_eta = eff.head(3)["metric"].tolist()
    L.append(f"- 유형 분리 기여 상위 지표(eta² 기준): {', '.join(top_eta)}\n")

    # 9. 민감도 / 한계
    L.append("## 9. 민감도 분석 · 한계\n")
    young = d[d[C.COL_AGE] <= 20]
    adult = d[d[C.COL_AGE] >= 25]
    L.append(f"- 연령대 15·20 구간 {len(young):,}명에 재학생이 혼입되어 있고 학력 컬럼이 없어 분리 불가.")
    if len(adult):
        adult_share = adult["segment"].value_counts(normalize=True).reindex(C.SEGMENT_ORDER).fillna(0)
        L.append("- **25세 이상 한정 유형 분포**: " +
                 ", ".join(f"{s} {adult_share[s]:.1%}" for s in C.SEGMENT_ORDER))
    L.append("- 모든 임계값은 분위수 기준이며 train에서만 산출해 `fitted_params.json`에 저장했다.")
    L.append("- 부스팅 계열(LightGBM·XGBoost·CatBoost·HistGradientBoosting)은 사용하지 않았다.\n")

    L.append("## 10. 시각화\n")
    for name in ["segment_scatter.png", "segment_size.png", "correlation_heatmap.png",
                 "pca_scree.png", "gmm_selection.png", "residual_dist.png",
                 "confusion_matrix.png", "radar_by_segment.png"]:
        L.append(f"- `figures/{name}`")
    L.append("")

    (outdir / "validation_report.md").write_text("\n".join(L), encoding="utf-8")
    eff.to_csv(outdir / "effect_sizes.csv", index=False, encoding="utf-8-sig")
