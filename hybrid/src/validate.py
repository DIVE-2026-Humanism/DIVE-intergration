"""검증 리포트 — model.md의 순환 검증을 외부 변수로 보강한다.

model.md §10.1은 앵커 변수로 점수 방향을 검증하는데, 그 변수들이 곧 방향을 정하는 데 쓰인
것이라 순환이다. 여기서는 앵커에 쓰이지 않은 외부 변수로 다시 검증한다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from analysis.src import config as AC

from . import config as C

ANCHOR_CHECK = {AC.COL_SCORE: "+", AC.COL_INCOME_Y: "+", AC.COL_INCOME_VERIFIED: "+",
                AC.COL_LOAN_CNT: "-", "consumption_ratio": "-", "dsr": "-",
                "total_delinq_cnt": "-", AC.COL_CASH_ADVANCE: "-"}
# 잠재모델 32개 입력과 앵커 어디에도 쓰이지 않은 변수만 "외부"로 인정한다.
# `pir`·`multi_debt`·`jeonse_income_multiple`·`has_policy_loan`·`income_percentile_busan`은
# 잠재 입력이거나 그 파생이므로 외부가 아니라 준순환으로 분류한다.
EXTERNAL_CHECK = ["is_owner", "self_employed", AC.COL_AGE, AC.COL_CAR, AC.COL_IS_APT,
                  "no_housing_record", "commute_mismatch"]
SEMI_CIRCULAR_CHECK = ["multi_debt", "pir", "jeonse_income_multiple", "has_policy_loan",
                       "income_percentile_busan"]
PROFILE_METRICS = [AC.COL_INCOME_Y, "income_to_median", "dsr", AC.COL_SCORE,
                   "consumption_ratio", "total_loan_balance", "job_turnover",
                   "stability_score"]
COLORS = {"E1": "#2a9d8f", "E2": "#8ab17d", "E3": "#e9c46a",
          "E4": "#f4a261", "E5": "#e76f51", "E6": "#9d0208"}


def eta_squared(df: pd.DataFrame, col: str, by: str = "etype") -> float:
    groups = [pd.to_numeric(df.loc[df[by] == k, col], errors="coerce").dropna().to_numpy()
              for k in df[by].dropna().unique()]
    groups = [g for g in groups if len(g) > 1]
    if len(groups) < 2:
        return float("nan")
    allv = np.concatenate(groups)
    grand = allv.mean()
    ss_t = ((allv - grand) ** 2).sum()
    return float(sum(len(g) * (g.mean() - grand) ** 2 for g in groups) / ss_t) if ss_t else float("nan")


def _table(df: pd.DataFrame, fmt: str = "{:,.3f}") -> list[str]:
    lines = ["| " + " | ".join(str(c) for c in df.columns) + " |",
             "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for v in r:
            if isinstance(v, (int, np.integer)):
                cells.append(f"{int(v):,}")
            elif isinstance(v, (float, np.floating)):
                cells.append("-" if pd.isna(v) else fmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def make_figures(df: pd.DataFrame, info: dict, figdir: Path, seed: int = C.SEED) -> None:
    figdir.mkdir(parents=True, exist_ok=True)
    lat = info["latent"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    evr = lat["pca_explained_variance_ratio"]
    axes[0].bar(range(1, len(evr) + 1), evr, color="#457b9d")
    axes[0].axvline(C.LATENT_DIMS + 0.5, color="red", ls="--", lw=1)
    axes[0].set_title(f"PCA scree (90% needs {lat['pca_components_for_90pct']}/{lat['n_features']})")
    axes[0].set_xlabel("component"); axes[0].set_ylabel("explained variance ratio")

    sizes = df["etype"].value_counts().reindex(C.ETYPE_ORDER).fillna(0)
    axes[1].bar(sizes.index, sizes.to_numpy(), color=[COLORS[e] for e in sizes.index])
    for i, v in enumerate(sizes.to_numpy()):
        axes[1].text(i, v, f"{int(v):,}", ha="center", va="bottom", fontsize=8)
    axes[1].set_title("Segment size (E1-E6)"); axes[1].set_ylabel("rows")
    axes[1].set_ylim(0, sizes.max() * 1.18)

    for e in C.ETYPE_ORDER:
        s = df.loc[df["etype"] == e, "stability_score"]
        if len(s) > 10:
            axes[2].hist(s, bins=50, histtype="step", density=True, label=e, color=COLORS[e])
    axes[2].set_title("Stability score by type"); axes[2].set_xlabel("score (0-100)")
    axes[2].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(figdir / "latent_overview.png", dpi=130); plt.close(fig)

    # 정책 사각지대
    fig, ax = plt.subplots(figsize=(7, 5))
    sample = df.sample(min(8000, len(df)), random_state=seed)
    b = sample["policy_blindspot"] == 1
    ax.scatter(sample.loc[~b, "income_to_median"], sample.loc[~b, "stability_score"],
               s=4, alpha=0.25, color="#adb5bd", label="others")
    ax.scatter(sample.loc[b, "income_to_median"], sample.loc[b, "stability_score"],
               s=5, alpha=0.6, color="#e63946", label="policy blind spot")
    ax.axvline(C.BLINDSPOT_INCOME_RATIO, color="black", ls="--", lw=1)
    ax.axhline(info["policy"]["score_cut"], color="black", ls="--", lw=1)
    ax.set_xlim(0, 3); ax.set_xlabel("income / national median standard")
    ax.set_ylabel("stability_score")
    ax.set_title(f"Policy blind spot: {info['policy']['blindspot_count']:,} rows "
                 f"({info['policy']['blindspot_share']:.1%})")
    ax.legend(markerscale=3, fontsize=8)
    fig.tight_layout(); fig.savefig(figdir / "policy_blindspot.png", dpi=130); plt.close(fig)

    # 문진 혼동행렬
    cm_info = info["survey"]["confusion_matrix"]
    cm = np.array(cm_info["matrix"], dtype=float)
    norm = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(cm_info["labels"])), cm_info["labels"])
    ax.set_yticks(range(len(cm_info["labels"])), cm_info["labels"])
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, f"{norm[i, j]:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if norm[i, j] > 0.5 else "black")
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title("Survey model (test, row-normalized)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout(); fig.savefig(figdir / "survey_confusion.png", dpi=130); plt.close(fig)


def write_report(df: pd.DataFrame, info: dict, outdir: Path) -> None:
    lat, pol, sur = info["latent"], info["policy"], info["survey"]
    L: list[str] = []
    L.append("# validation_report.md — hybrid (잠재 E1~E6 + 정책·문진 결합)\n")
    L.append("> 유형 라벨은 개인 신용 판정이 아니라 **정책 아웃리치 우선순위**다.\n")
    L.append("라벨 체계는 `model.md`(잠재 PCA+GMM)를 따르고, 정책 기준·문진 압축·외부 검증은 "
             "`method.md`/`analysis` 자산을 결합했다.\n")

    L.append("## ★ 정책 사각지대\n")
    L.append(f"> 소득은 기준 중위소득 100%를 넘어 **현행 소득 기준 지원 대상이 아닌데**, "
             f"종합점수는 하위 {C.BLINDSPOT_SCORE_QUANTILE:.0%}인 집단\n")
    L.append(f"# {pol['blindspot_count']:,}명 ({pol['blindspot_share']:.1%})\n")
    L.append(f"기준 중위소득 100% 초과 인구의 **{pol['blindspot_share_of_above_median']:.1%}**.\n")
    L.append("| 지표 | 사각지대 | 전체 | 차이 |")
    L.append("|---|---:|---:|---|")
    for label, fmt in [("종합점수", "{:.1f}"), ("현금서비스", "{:.1%}"), ("dsr", "{:.3f}"),
                       ("다중채무", "{:.1%}"), ("신용평점", "{:.0f}"), ("추정 연소득", "{:,.0f}")]:
        b, o = pol[f"blindspot_{label}"], pol[f"overall_{label}"]
        diff = f"{b - o:+,.0f}점" if label in ("신용평점", "종합점수") else f"{b / o:.1f}배"
        L.append(f"| {label} | {fmt.format(b)} | {fmt.format(o)} | {diff} |")
    L.append(f"\n- 판정 기준: {pol['median_income_source']}")
    L.append(f"- 소득 기준 정책 대상(중위 60% 이하)은 {pol['eligible_by_income']:,}명뿐이다.")
    L.append(f"- 유형별 분포: {pol['blindspot_by_etype']}\n")

    L.append("## 1. 잠재모델 (model.md §6~8 구현)\n")
    L.append(f"- 입력 {lat['n_features']}개 → 누적 90% 설명에 **{lat['pca_components_for_90pct']}개 성분** 필요")
    L.append(f"- 점수·유형 공통 잠재차원 {lat['latent_dims']}개, 점수 성분 {lat['score_components']}")
    L.append(f"- GMM 실루엣 **{lat['silhouette']:.4f}** · 평균 확신도 {lat['mean_confidence']:.4f} · "
             f"확신도 0.5 미만 {lat['low_confidence_share']:.2%}\n")
    L.append("> 실루엣이 낮은데 확신도가 높은 것은 모순이 아니다. GMM은 확률분포 내 배정이 확실할 수 있지만 "
             "군집 사이 거리는 가까울 수 있다. **자연 경계가 강하지 않다는 뜻이므로 "
             "\"데이터가 6개 집단을 발견했다\"고 말해서는 안 되고, \"정책 우선순위를 위해 6단계로 나눴다\"고 "
             "말해야 한다.**\n")
    prof = pd.DataFrame(lat["score_profile"]).T.reset_index().rename(columns={"index": "유형"})
    prof["명칭"] = prof["유형"].map(C.ETYPE_NAMES)
    prof["대분류"] = prof["유형"].map(C.ETYPE_MAJOR)
    L.extend(_table(prof[["유형", "명칭", "대분류", "mean", "median", "size"]], "{:,.2f}"))
    L.append(f"\n- 종합점수 단조 감소: **{'통과' if lat['score_monotonic'] else '실패'}**\n")

    L.append("## 2. 점수 방향 검증 — 순환 부분과 외부 부분을 분리\n")
    L.append("`model.md` §10.1의 13개 방향 검증 변수는 전부 §7.2 앵커 변수다. "
             "방향을 정하는 데 쓴 변수로 방향을 검증한 것이라 **순환**이다. "
             "여기서는 앵커에 쓰이지 않은 외부 변수로 다시 검증한다.\n")
    rows = []
    for v, sgn in ANCHOR_CHECK.items():
        r = stats.spearmanr(df["stability_score"], pd.to_numeric(df[v], errors="coerce"),
                            nan_policy="omit").statistic
        rows.append({"변수": v, "구분": "앵커(순환)", "기대": sgn, "spearman": float(r),
                     "판정": "통과" if (r > 0) == (sgn == "+") else "실패"})
    for group, label in [(EXTERNAL_CHECK, "**외부**"), (SEMI_CIRCULAR_CHECK, "준순환")]:
        for v in group:
            if v not in df.columns:
                continue
            r = stats.spearmanr(df["stability_score"], pd.to_numeric(df[v], errors="coerce"),
                                nan_policy="omit").statistic
            rows.append({"변수": v, "구분": label, "기대": "-", "spearman": float(r), "판정": "-"})
    L.extend(_table(pd.DataFrame(rows), "{:+.3f}"))
    L.append("")

    L.append("## 3. 외부 타당도 — 유형이 축 밖 현실을 설명하는가\n")
    rows = []
    for group, label in [(EXTERNAL_CHECK, "외부"), (SEMI_CIRCULAR_CHECK, "준순환")]:
        for v in group:
            if v not in df.columns:
                continue
            e = eta_squared(df, v)
            rows.append({"변수": v, "구분": label, "eta_squared": e,
                         "효과": "large" if e >= 0.14 else "medium" if e >= 0.06 else "small"})
    ext = pd.DataFrame(rows).sort_values(["구분", "eta_squared"], ascending=[True, False])
    L.extend(_table(ext, "{:.4f}"))
    L.append("\n> **외부** = 잠재모델 32개 입력과 앵커 어디에도 쓰이지 않은 변수. 여기서 나오는 차이만 "
             "순환이 아니다.\n> **준순환** = 잠재 입력이거나 그 파생(예: `multi_debt`는 `총대출건수`에서, "
             "`pir`는 입력 그 자체). 값이 커도 타당성 근거로 쓰면 안 된다.\n")

    L.append("## 4. 유형 프로파일\n")
    p = df.groupby("etype")[PROFILE_METRICS].mean().reindex(C.ETYPE_ORDER).reset_index()
    p["명칭"] = p["etype"].map(C.ETYPE_NAMES)
    L.extend(_table(p, "{:,.3f}"))
    L.append("")

    L.append("## 5. 정책 축 교차표 (행 비율)\n")
    for col, title in [("income_grade", "기준 중위소득 등급"), ("employment_type", "고용형태")]:
        ct = pd.crosstab(df["etype"], df[col], normalize="index").reindex(C.ETYPE_ORDER).dropna(how="all")
        ct = ct.reset_index()
        ct.columns = [str(c) for c in ct.columns]
        L.append(f"### E유형 × {title}\n")
        L.extend(_table(ct, "{:.1%}"))
        L.append("")

    L.append("## 6. 문진 축소 모델 — 42변수 라벨을 6문항으로\n")
    L.append(f"- 문항 {sur['n_questions']}개: `{C.QUESTION_FEATURES}`")
    L.append(f"- DecisionTree(max_depth={sur['chosen_depth']}) · test accuracy "
             f"**{sur['test_accuracy']:.3f}** · macro F1 **{sur['test_macro_f1']:.3f}**")
    L.append(f"- 무작위 기준 {sur['random_baseline']:.3f} 대비 "
             f"**{sur['test_accuracy'] / sur['random_baseline']:.1f}배**")
    L.append(f"- CV macro F1 {sur['cv_macro_f1_mean']:.3f}±{sur['cv_macro_f1_std']:.3f}")
    c = sur["confidence"]
    L.append(f"- 확신도 평균 {c['mean']:.3f} · 0.5 미만 {c['share_below_0.5']:.1%} "
             "→ 추가 질문 트리거 대상")
    L.append("- 연령·성별·거주지는 실측상 기여가 0이라 문항에서 제외했다.\n")
    rep = pd.DataFrame(sur["report"]).T.reset_index().rename(columns={"index": "class"})
    rep = rep[rep["class"].isin(C.ETYPE_ORDER)].copy()
    rep["support"] = rep["support"].astype(int)
    L.extend(_table(rep))
    L.append("")

    L.append("## 7. 시각화\n")
    for n in ["latent_overview.png", "policy_blindspot.png", "survey_confusion.png"]:
        L.append(f"- `figures/{n}`")
    L.append("")
    (outdir / "validation_report.md").write_text("\n".join(L), encoding="utf-8")
