from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import f_oneway

from .config import SEGMENT_NAMES

plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

PROFILE_FEATURES = [
    "추정 연소득", "dsr", "신용평점", "job_turnover", "income_trajectory",
    "consumption_ratio", "jeonse_income_multiple", "credit_score_residual", "total_delinq_cnt",
]


def _eta_squared(frame: pd.DataFrame, feature: str) -> tuple[float, float]:
    valid = frame[["segment", feature]].dropna()
    groups = [g[feature].to_numpy() for _, g in valid.groupby("segment") if len(g) > 1]
    if len(groups) < 2:
        return np.nan, np.nan
    _, p = f_oneway(*groups)
    grand = valid[feature].mean()
    between = sum(len(g) * (g[feature].mean() - grand) ** 2 for _, g in valid.groupby("segment"))
    total = ((valid[feature] - grand) ** 2).sum()
    return float(p), float(between / total) if total else 0.0


def _figures(frame: pd.DataFrame, params: dict, reduced: dict, outdir: Path, seed: int) -> None:
    figures = outdir / "figures"
    figures.mkdir(exist_ok=True)
    sns.set_theme(style="whitegrid", rc={"font.family": "NanumGothic", "axes.unicode_minus": False})
    rng = np.random.default_rng(seed)
    sample = frame.iloc[rng.choice(len(frame), min(20_000, len(frame)), replace=False)]

    plt.figure(figsize=(9, 7))
    sns.scatterplot(data=sample, x="financial_stress_score", y="employment_instability_score", hue="segment", alpha=.35, s=12, palette="tab10")
    plt.axvline(params["segment"]["financial_cut"], color="black", ls="--")
    plt.axhline(params["segment"]["employment_cut"], color="black", ls="--")
    plt.tight_layout(); plt.savefig(figures / "segment_scatter.png", dpi=160); plt.close()

    counts = frame["segment"].value_counts().sort_index()
    counts.plot.bar(figsize=(8, 5), color=sns.color_palette("tab10", len(counts)))
    plt.ylabel("rows"); plt.tight_layout(); plt.savefig(figures / "segment_size.png", dpi=160); plt.close()

    corr_features = [c for c in PROFILE_FEATURES + ["financial_stress_score", "employment_instability_score"] if c in frame]
    plt.figure(figsize=(11, 9)); sns.heatmap(frame[corr_features].corr(), cmap="vlag", center=0)
    plt.tight_layout(); plt.savefig(figures / "correlation_heatmap.png", dpi=160); plt.close()

    plt.figure(figsize=(8, 5))
    for label, key in [("financial", "financial_axis"), ("employment", "employment_axis")]:
        evr = params["scores"][key]["explained_variance_ratio"]
        plt.plot(range(1, len(evr) + 1), evr, marker="o", label=label)
    plt.axhline(.4, color="grey", ls="--"); plt.legend(); plt.ylabel("explained variance ratio")
    plt.tight_layout(); plt.savefig(figures / "pca_scree.png", dpi=160); plt.close()

    diagnostics = pd.DataFrame(params["segment"]["gmm"]["diagnostics"])
    fig, left = plt.subplots(figsize=(8, 5)); right = left.twinx()
    left.plot(diagnostics.k, diagnostics.bic, marker="o", label="BIC")
    right.plot(diagnostics.k, diagnostics.silhouette, color="orange", marker="s", label="silhouette")
    left.set_xlabel("k"); left.set_ylabel("BIC"); right.set_ylabel("silhouette")
    fig.tight_layout(); fig.savefig(figures / "gmm_selection.png", dpi=160); plt.close(fig)

    plt.figure(figsize=(9, 5)); sns.histplot(data=sample, x="credit_score_residual", hue="segment", element="step", stat="density", common_norm=False, bins=50)
    plt.tight_layout(); plt.savefig(figures / "residual_dist.png", dpi=160); plt.close()

    cm = np.asarray(reduced["confusion_matrix"])
    plt.figure(figsize=(7, 6)); sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=reduced["classes"], yticklabels=reduced["classes"])
    plt.xlabel("predicted"); plt.ylabel("actual"); plt.tight_layout(); plt.savefig(figures / "confusion_matrix.png", dpi=160); plt.close()

    radar_features = ["financial_stress_score", "employment_instability_score", "dsr", "consumption_ratio", "jeonse_income_multiple"]
    radar = frame.groupby("segment")[radar_features].median().rank(pct=True) * 100
    angles = np.linspace(0, 2 * np.pi, len(radar_features), endpoint=False).tolist(); angles += angles[:1]
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})
    for segment_name, row in radar.iterrows():
        values = row.tolist() + [row.iloc[0]]
        ax.plot(angles, values, label=segment_name); ax.fill(angles, values, alpha=.05)
    ax.set_xticks(angles[:-1], radar_features); ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    fig.tight_layout(); fig.savefig(figures / "radar_by_segment.png", dpi=160); plt.close(fig)


def validate(frame: pd.DataFrame, load_meta: dict, excluded: list[str], consistency: pd.DataFrame, params: dict, model_metrics: dict, outdir: Path, seed: int) -> None:
    aggregations = frame.groupby("segment")[PROFILE_FEATURES].agg(["mean", "median"])
    aggregations.columns = [f"{a}_{b}" for a, b in aggregations.columns]
    aggregations.insert(0, "segment_name", aggregations.index.map(SEGMENT_NAMES))
    aggregations.to_csv(outdir / "segment_profile.csv", encoding="utf-8-sig")
    effects = []
    for feature in PROFILE_FEATURES:
        p, eta = _eta_squared(frame, feature)
        effects.append({"feature": feature, "p_value": p, "eta_squared": eta})
    effect_frame = pd.DataFrame(effects).sort_values("eta_squared", ascending=False)
    effect_frame.to_csv(outdir / "effect_sizes.csv", index=False, encoding="utf-8-sig")
    for column in ["연령대", "성별", "거주지 시군구 코드", "직업군"]:
        pd.crosstab(frame["segment"], frame[column], normalize="index").to_csv(outdir / f"crosstab_{column.replace('/', '_')}.csv", encoding="utf-8-sig")
    sensitivity = pd.crosstab(frame.loc[frame["연령대"].ge(25), "segment"], columns="rate", normalize="columns")
    sensitivity.to_csv(outdir / "sensitivity_age25plus.csv", encoding="utf-8-sig")
    _figures(frame, params, model_metrics["reduced"], outdir, seed)

    counts = frame["segment"].value_counts().sort_index()
    t3_rate = params["segment"]["t3_rate"]
    gmm = params["segment"]["gmm"]
    warning = ""
    if t3_rate < .05:
        warning = "\n> **WARNING:** T3 비중이 5% 미만입니다. 합성데이터가 고용 불안정과 재무 악화를 강하게 연동했을 가능성이 있습니다.\n"
    lines = [
        "# 6유형 경제 계층 검증 리포트", "",
        "> 이 유형은 개인 신용 판정이나 낙인이 아니라 정책 아웃리치 우선순위를 위한 분석 라벨입니다.", "",
        f"## 핵심: T3 잠재 불안군 {counts.get('T3', 0):,}명 ({t3_rate:.2%})", warning,
        "## 데이터 개요", "", f"- 행: {len(frame):,}", f"- 입력: `{load_meta['path']}`", f"- 인코딩: {load_meta['encoding']}",
        f"- 제거 열: {', '.join(excluded)}", "- 금액 단위: 천원 추정(월소득×12/연소득 분포를 fitted_params.json에 기록)",
        "- `추정가구원수` 부재로 배포 데이터가 1인가구 필터링 완료된 것으로 가정", "",
        "## 유형 규모", "", "|유형|명칭|건수|비중|", "|---|---|---:|---:|",
    ]
    lines += [f"|{code}|{SEGMENT_NAMES[code]}|{count:,}|{count / len(frame):.2%}|" for code, count in counts.items()]
    lines += [
        "", "## 진단 분기", "",
        f"- 재무축 PC1: {params['scores']['financial_axis']['pc1_explained_variance']:.3f}, {params['scores']['financial_axis']['weight_method']} 가중",
        f"- 고용축 PC1: {params['scores']['employment_axis']['pc1_explained_variance']:.3f}, {params['scores']['employment_axis']['weight_method']} 가중",
        f"- GMM 최적 k={gmm['best_k']}, 실루엣={gmm['best_silhouette']:.3f}, ARI={gmm['ari']:.3f}, 규칙 일치율={gmm['agreement']:.2%}",
        f"- 최종 주도권: {gmm['authority']}",
        "- 군집 구조가 강해도 6유형 계약과 일대일 대응하지 않으면 규칙 라벨을 유지", "",
        "## 희소 유형 점검", "",
        f"- T6 제외 5% 미만 유형: {', '.join(params['segment']['small_segments_below_5pct']) or '없음'}",
        f"- T5 엄격 정의: {params['segment']['t5_count']:,}명",
        (f"- T5가 100명 미만이므로 `총대출건수 == 0`을 완화한 대안 정의: {params['segment']['t5_relaxed_count']:,}명"
         if params['segment']['t5_count'] < 100 else "- T5가 100명 이상이어서 완화 정의가 필요하지 않음"),
        "- 최종 라벨에는 설명 가능성과 사전 정의 보존을 위해 엄격 정의를 유지", "",
        "## 학습 모델 성능", "",
        f"- 전세가 대체: {model_metrics['imputer']['selected']}, RF MAE={model_metrics['imputer']['model_mae']:.2f}, 기준 MAE={model_metrics['imputer']['baseline_mae']:.2f}, R²={model_metrics['imputer']['r2']:.3f}",
        f"- 신용점수 잔차: {model_metrics['residual']['selected']}, test RMSE={model_metrics['residual']['test']['rmse']:.2f}, R²={model_metrics['residual']['test']['r2']:.3f}",
        f"- 8문항 트리: test macro F1={model_metrics['reduced']['test_macro_f1']:.3f}, accuracy={model_metrics['reduced']['test_accuracy']:.3f}",
        f"- 42개 금융변수 기반 라벨을 8문항으로 {model_metrics['reduced']['test_accuracy']:.1%} 재현", 
        f"- 확신도 0.5 미만: {model_metrics['reduced']['low_confidence_below_0_5']:.2%}",
        f"- 확장 문진({model_metrics['full_questionnaire']['question_count']}개 입력): test macro F1={model_metrics['full_questionnaire']['test_macro_f1']:.3f}, accuracy={model_metrics['full_questionnaire']['test_accuracy']:.3f}",
        f"- 이상탐지: {model_metrics['anomaly']['anomaly_count']:,}건, 이상치 중 T4={model_metrics['anomaly']['t4_share_among_anomalies']:.2%}", "",
        "## 효과크기", "", effect_frame.to_markdown(index=False, floatfmt=".4f"), "",
        "## 한계", "", "- 합성데이터 결과는 실제 부산 청년 모집단 성능을 보장하지 않습니다.",
        "- 직업군 코드 의미를 부여하지 않았으며 축소 모델에서 범주형 원핫으로만 사용 가능한 구조입니다.",
        "- 15·20 연령대 재학생 혼입을 분리할 학력 컬럼이 없어 25세 이상 민감도 표를 별도 저장했습니다.",
    ]
    (outdir / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")
