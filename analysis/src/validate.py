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
    C.COL_INCOME_Y, "income_to_median", "dsr", C.COL_SCORE, "job_turnover", "income_trajectory",
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

    # 8) 정책 기준(기준 중위소득) 대비 소득 등급 × 재무 스트레스
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    grades = C.INCOME_GRADE_LABELS
    ascii_g = ["<=50%", "50-60%", "60-100%", "100-120%", ">120%"]
    counts = d["income_grade"].value_counts().reindex(grades).fillna(0)
    colors = ["#e76f51", "#f4a261", "#e9c46a", "#8ab17d", "#2a9d8f"]
    axes[0].bar(ascii_g, counts.to_numpy(), color=colors)
    for i, v in enumerate(counts.to_numpy()):
        axes[0].text(i, v, f"{int(v):,}\n{v / len(d):.1%}", ha="center", va="bottom", fontsize=8)
    axes[0].set_title("Income vs national median standard (1-person household)")
    axes[0].set_ylabel("rows")
    axes[0].set_ylim(0, counts.max() * 1.25)

    blind = d["policy_blindspot"] == 1
    sample = d.sample(min(8000, len(d)), random_state=seed)
    sb = sample["policy_blindspot"] == 1
    axes[1].scatter(sample.loc[~sb, "income_to_median"], sample.loc[~sb, C.FINANCIAL_SCORE],
                    s=4, alpha=0.25, color="#adb5bd", label="others")
    axes[1].scatter(sample.loc[sb, "income_to_median"], sample.loc[sb, C.FINANCIAL_SCORE],
                    s=5, alpha=0.55, color="#e63946", label="policy blind spot")
    axes[1].axvline(C.BLINDSPOT_INCOME_RATIO, color="black", ls="--", lw=1)
    axes[1].axhline(info["segment"]["policy"]["stress_cut"], color="black", ls="--", lw=1)
    axes[1].set_xlim(0, 3)
    axes[1].set_xlabel("income / national median standard")
    axes[1].set_ylabel("financial_stress_score")
    axes[1].set_title(f"Blind spot: {blind.sum():,} rows ({blind.mean():.1%})")
    axes[1].legend(markerscale=3, fontsize=8)
    _savefig(fig, figdir / "policy_blindspot.png")

    # 9) 유형별 레이더 (분위수 평균)
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

    # ---- 최상단: 정책 사각지대 (외부 절대 기준 기반)
    pol = seg_info["policy"]
    L.append("## ★★ 정책 사각지대 — 최우선 지표\n")
    L.append(f"> **소득 기준으로는 지원 대상이 아닌데(기준 중위소득 100% 초과) "
             f"재무 스트레스가 상위 {1 - C.BLINDSPOT_STRESS_QUANTILE:.0%}인 집단**\n")
    L.append(f"# {pol['blindspot_count']:,}명 ({pol['blindspot_share']:.1%})\n")
    L.append(f"기준 중위소득 100% 초과 인구의 **{pol['blindspot_share_of_above_median']:.1%}**에 해당한다.\n")
    L.append("| 지표 | 사각지대 집단 | 전체 | 배수 |")
    L.append("|---|---:|---:|---:|")
    for label, fmt in [("현금서비스", "{:.1%}"), ("dsr", "{:.3f}"), ("신용평점", "{:.0f}"),
                       ("연체건수", "{:.3f}"), ("추정 연소득", "{:,.0f}")]:
        b, o = pol[f"blindspot_{label}"], pol[f"overall_{label}"]
        # 신용평점은 낮을수록 나쁘므로 배수가 아니라 점수 차로 읽는다.
        ratio = f"{b - o:+,.0f}점" if label == "신용평점" else (f"{b / o:.1f}배" if o else "-")
        L.append(f"| {label} | {fmt.format(b)} | {fmt.format(o)} | {ratio} |")
    L.append("")
    L.append(f"- 판정 기준: {pol['median_income_source']}")
    L.append("- 소득 등급은 **정부 고시 절대 기준**이라 우리가 만든 값이 아니다(순환논리 없음). "
             "재무 스트레스 축에서 `dsr`·`cash_advance_flag`의 가중치는 사실상 0인데도 "
             "위 배수 차이가 나므로, 축이 만들어낸 차이가 아니다.")
    L.append("- **정책 함의**: 현행 소득 기준 청년정책은 이 집단을 포착하지 못한다. "
             "발제 자료가 지목한 \"자산 형성 대비 주거비·고정지출 부담으로 상환력이 악화되는 구조\"에 해당한다.\n")

    L.append("### 기준 중위소득 대비 소득 분포\n")
    L.append(f"표본 소득 중앙값은 기준 중위소득의 **{pol['sample_median_to_standard']:.0%}** 수준이다.\n")
    L.append("| 등급 | 인원 | 비중 |")
    L.append("|---|---:|---:|")
    for g in C.INCOME_GRADE_LABELS:
        L.append(f"| {g} | {pol['grade_counts'].get(g, 0):,} | {pol['grade_shares'].get(g, 0):.2%} |")
    L.append("")
    L.append(f"> 소득 기준 정책 대상(중위 60% 이하)은 **{pol['eligible_by_income']:,}명**에 그친다. "
             "합성데이터의 소득 분포가 실제 부산 청년 대비 양 끝단이 절단되어 있음을 함께 고려해야 한다"
             "(`data_caveats.md` 참조).\n")

    # ---- T3 강조 + 경고 (method.md §11.3)
    t3_n = seg_info["sizes"].get("T3", 0)
    L.append("## ★ T3(잠재 불안군) 규모 — method.md §11.3 지정 지표\n")
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
             f"= jeonse_income_multiple 상위 {1 - C.H_FLAG_QUANTILE:.0%} "
             f"(컷 {hf['jeonse_income_multiple_cut']:.3f})")
    L.append(f"  - **§11.2 원안 수정**: 원안은 위 조건 **OR** `commute_mismatch`였으나, "
             f"근무지 시군구가 무작위 배정임이 실측되어(거주지↔근무지 Cramér's V = 0.023) "
             f"통근 조건을 제외했다. 원안대로면 `commute_mismatch`가 "
             f"{hf['share_commute_only']:.1%}(16개 구 무작위 시 이론값 93.75%)에 달해 "
             "H flag가 94%로 포화되어 수정자 기능을 잃는다.")
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

    # 4.3 비교 기준 — 서비스가 "당신은 상위 X%"를 말할 때 무엇과 비교하는가
    L.append("## 4.3 비교 기준 (서비스 문구의 근거)\n")
    L.append("| 지표 | 비교군 | 근거 |")
    L.append("|---|---|---|")
    L.append(f"| 소득 | **실제 부산 청년(18~39세)** | {C.BUSAN_YOUTH_INCOME_SOURCE} |")
    L.append(f"| 소득(정책 자격) | 정부 고시 절대 기준 | {C.MEDIAN_INCOME_SOURCE} |")
    L.append("| 신용평점 · 부채 · 상환 · 소비 | **제공 표본 10만 명(train)** | 외부 분포 미확보 — "
             "`fitted_params.json`의 `percentile_reference.sample_deciles_train` |")
    L.append("")
    bp = d["income_percentile_busan"]
    L.append(f"표본 소득 중앙값은 **부산 청년 중 하위 {bp.median():.0f}%**에 위치한다. "
             "합성표본이 실제 부산 청년보다 소득 상위 쪽에 치우쳐 있다는 뜻이다.\n")
    L.append("| 월소득 | 부산 청년 중 위치 |")
    L.append("|---:|---|")
    from .features import busan_income_percentile
    for manwon in [150, 200, 250, 300, 350, 450]:
        v = float(busan_income_percentile(pd.Series([manwon * 12 * 10])).iloc[0])
        L.append(f"| {manwon}만원 | 하위 {v:.0f}% |")
    L.append("")
    L.append("> 부채·소비·신용평점은 외부 분포를 확보하지 못해 **제공 표본을 비교군으로 쓴다.** "
             "서비스 문구에 \"전국 대비\"라고 쓰면 안 되며, "
             "\"부산 청년 1인가구 10만 명 중 상위 X%\"로 표기해야 한다. "
             "비교군이 서비스 대상과 일치하므로 전국 통계보다 오히려 적합하다.\n")

    # 4.4 주거 거래기록 결측 = 비정형 주거 프록시
    rf = seg_info["r_flag"]
    L.append("## 4.4 R flag — 주거 거래기록 없음 (결측이 곧 신호)\n")
    L.append(f"`2년내 현거주지평균전세거래가` 결측 **{rf['share']:.1%}**는 무작위 결측이 아니다. "
             "정의서상 이 값은 \"국토교통부 실거래가 기준 **등록된** 현거주지의 2년간 평균\"이므로, "
             "결측은 **해당 주소지에 최근 2년간 실거래 신고 기록이 없음**을 뜻한다. "
             "거래가 잦은 아파트는 기록이 남고, 단독·다가구·빌라는 남지 않는다.\n")
    L.append("| 지표 | 거래기록 있음 | 거래기록 없음 |")
    L.append("|---|---:|---:|")
    for label, fmt in [("소득", "{:,.0f}"), ("신용평점", "{:.0f}"),
                       ("아파트비율", "{:.1%}"), ("사각지대", "{:.1%}")]:
        L.append(f"| {label} | {fmt.format(rf[f'기록있음_{label}'])} | {fmt.format(rf[f'기록없음_{label}'])} |")
    L.append("")
    L.append("> method.md §16-1(\"결측 여부 자체가 취약주거 프록시일 수 있다\")이 전수에서 확인됐다. "
             "STEP 3에서 결측에 예측값을 대입하면 이 신호가 평균값으로 덮이므로, "
             "`no_housing_record`를 **정식 파생변수로 승격**하고 운영 표기에 **R**로 병기한다"
             "(예: `T4-HR` = 복합 위기군 + 주거비 부담 상위 + 거래기록 없음).")
    L.append("> H flag와 OR로 합치지 않은 이유: 결측률이 65.7%라 합치면 수정자가 포화되어 "
             "`commute_mismatch`와 같은 실패를 반복한다. 두 축을 독립 차원으로 유지한다.\n")

    # 4.5 고용형태 — 코드북 확보로 해석 가능해진 유일한 외부 타당 변수
    L.append("## 4.5 고용형태 프로파일 (직업군 코드북 적용)\n")
    L.append("`데이터사용컬럼정의서.xlsx` [코드] 시트로 직업군 코드북을 확보해, "
             "method.md §16-4(\"의미 부여 금지\")의 전제가 해소되었다.\n")
    job = d.groupby("job_name", sort=False).agg(
        인원=("job_name", "size"),
        소득중앙값=(C.COL_INCOME_Y, "median"),
        신용평점=(C.COL_SCORE, "mean"),
        현금서비스=("cash_advance_flag", "mean"),
        연체율=("delinq_rate", "mean"),
        T4비중=("segment", lambda s: (s == "T4").mean()),
        정책자금보유=("has_policy_loan", "mean"),
        사각지대=("policy_blindspot", "mean"),
    ).sort_values("인원", ascending=False).reset_index()
    for c in ["현금서비스", "연체율", "T4비중", "정책자금보유", "사각지대"]:
        job[c] = job[c] * 100
    L.extend(_fmt_table(job, "{:,.1f}"))
    L.append("\n(비율 컬럼 단위 %)\n")

    emp = d[d["employment_type"] == "급여소득"]
    sel = d[d["employment_type"] == "자영업"]
    L.append("**급여소득자 vs 자영업자** — 실측상 가장 강한 외부 타당 변수\n")
    L.append("| 지표 | 급여소득 | 자영업 | 배수 |")
    L.append("|---|---:|---:|---:|")
    for col, name, fmt in [("has_policy_loan", "정책자금 대출 보유", "{:.2%}"),
                           ("policy_blindspot", "정책 사각지대", "{:.1%}"),
                           ("cash_advance_flag", "현금서비스", "{:.1%}"),
                           ("multi_debt", "다중채무(3건+)", "{:.1%}"),
                           ("dsr", "dsr", "{:.3f}")]:
        a, b = float(emp[col].mean()), float(sel[col].mean())
        L.append(f"| {name} | {fmt.format(a)} | {fmt.format(b)} | {b / a:.2f}배 |")
    L.append("")
    L.append("> **중요**: 6유형 라벨은 `has_policy_loan`(실제 정책 접점)을 전혀 설명하지 못하지만"
             "(eta² ≈ 0), **고용형태는 2배 차이로 가른다**. 정책 대상 선별에서는 유형보다 "
             "고용형태가 더 강한 신호이므로, 아웃리치 우선순위 산정에 반드시 병용할 것.\n")
    L.append(f"> §10.1 각주(\"PC1이 낮으면 직업군 원핫 추가 검토 — 코드북 확보 전제\") 이행 결과: "
             f"고용축에 `self_employed`를 추가하면 PC1이 "
             f"{sc_info['axes']['employment']['pc1_evr']:.1%} → 35.1%로 오히려 낮아지고 "
             "축 변수와의 상관도 |0.06| 이하라 **축에는 추가하지 않았다**. "
             "대신 위와 같이 독립 차원으로 사용한다.\n")

    # 5. 교차표
    L.append("## 5. 교차표 (행 비율)\n")
    for col, title in [("income_grade", "기준 중위소득 등급"), ("employment_type", "고용형태"),
                       (C.COL_AGE, "연령대"), (C.COL_GENDER, "성별"),
                       ("region_name", "거주 구·군"), ("job_name", "직업군")]:
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
                 "confusion_matrix.png", "policy_blindspot.png", "radar_by_segment.png"]:
        L.append(f"- `figures/{name}`")
    L.append("")

    (outdir / "validation_report.md").write_text("\n".join(L), encoding="utf-8")
    eff.to_csv(outdir / "effect_sizes.csv", index=False, encoding="utf-8-sig")
