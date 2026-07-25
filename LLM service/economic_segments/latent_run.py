from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .consistency import check_consistency
from .config import REQUIRED_COLUMNS
from .features import build_features
from .impute import fit_imputer
from .latent_model import LatentEconomicModel, RawLatentEconomicInference, TYPE_DESCRIPTIONS
from .load import load_csv
from .split import split_labels


def _json_default(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    raise TypeError(type(value).__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="비지도 잠재 경제점수·6유형 추론모델")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)
    np.random.seed(args.seed)

    raw, load_meta = load_csv(args.input)
    frame, excluded, _ = check_consistency(raw, args.outdir)
    split = split_labels(frame, args.seed)
    frame, imputer_metrics = fit_imputer(frame, split, args.outdir, args.seed)
    frame = build_features(frame, args.outdir)

    model = LatentEconomicModel(seed=args.seed).fit(frame.loc[split.eq("train")])
    predictions = model.predict(frame)
    predictions.insert(0, "split", split.to_numpy())
    predictions.insert(0, "row_id", frame["row_id"].to_numpy())
    predictions.to_csv(args.outdir / "latent_scores_and_types.csv", index=False, encoding="utf-8-sig")
    jeonse_artifact = joblib.load(args.outdir / "imputer_jeonse.pkl")
    inference = RawLatentEconomicInference(model, jeonse_artifact, excluded)
    joblib.dump(inference, args.outdir / "latent_economic_model.pkl")

    profile_source = pd.concat([predictions, frame[["추정 연소득", "신용평점", "dsr", "total_delinq_cnt", "income_trajectory", "job_turnover"]]], axis=1)
    profile = profile_source.groupby(["economic_type", "economic_type_name"]).agg(
        count=("row_id", "size"), score_mean=("composite_stability_score", "mean"),
        score_median=("composite_stability_score", "median"), confidence_mean=("type_confidence", "mean"),
        income_median=("추정 연소득", "median"), credit_score_median=("신용평점", "median"),
        dsr_median=("dsr", "median"), delinquency_mean=("total_delinq_cnt", "mean"),
        income_trajectory_median=("income_trajectory", "median"), job_turnover_mean=("job_turnover", "mean"),
    ).reset_index()
    profile.to_csv(args.outdir / "latent_type_profile.csv", index=False, encoding="utf-8-sig")

    characteristic_features = [
        "추정 연소득", "증빙연소득", "신용평점", "dsr", "total_loan_balance",
        "총대출건수", "total_delinq_cnt", "delinq_severity", "cash_advance_flag",
        "thin_filer", "파산, 개인회생 신청 여부", "job_turnover",
        "income_trajectory", "consumption_ratio", "jeonse_income_multiple",
        "pir", "is_owner", "has_mortgage",
    ]
    characteristic_source = pd.concat(
        [predictions[["economic_type", "economic_type_name"]], frame[characteristic_features]], axis=1
    )
    characteristic_means = characteristic_source.groupby("economic_type")[characteristic_features].mean()
    overall_mean = frame[characteristic_features].mean()
    overall_std = frame[characteristic_features].std().replace(0, np.nan)
    characteristic_z = (characteristic_means - overall_mean) / overall_std
    characteristic_rows = []
    for economic_type in sorted(characteristic_means.index):
        ordered = characteristic_z.loc[economic_type].dropna().sort_values()
        characteristic_rows.append({
            "economic_type": economic_type,
            "economic_type_name": predictions.loc[predictions.economic_type.eq(economic_type), "economic_type_name"].iloc[0],
            "description": TYPE_DESCRIPTIONS[economic_type],
            "top_high_features": "; ".join(f"{name}({value:+.2f}σ)" for name, value in ordered.tail(5).sort_values(ascending=False).items()),
            "top_low_features": "; ".join(f"{name}({value:+.2f}σ)" for name, value in ordered.head(5).items()),
        })
    characteristics = pd.DataFrame(characteristic_rows)
    characteristics.to_csv(args.outdir / "latent_type_characteristics.csv", index=False, encoding="utf-8-sig")
    characteristic_means.to_csv(args.outdir / "latent_type_feature_means.csv", encoding="utf-8-sig")
    characteristic_z.to_csv(args.outdir / "latent_type_feature_zscores.csv", encoding="utf-8-sig")

    ordered_profile = profile.sort_values("economic_type")
    score_correlations = characteristic_source.assign(
        composite_stability_score=predictions["composite_stability_score"]
    )[["composite_stability_score"] + characteristic_features].corr(method="spearman")["composite_stability_score"].drop("composite_stability_score")
    expected_positive = ["추정 연소득", "증빙연소득", "신용평점", "income_trajectory"]
    expected_negative = [
        "dsr", "total_loan_balance", "총대출건수", "total_delinq_cnt",
        "delinq_severity", "cash_advance_flag", "consumption_ratio", "thin_filer",
        "파산, 개인회생 신청 여부",
    ]
    direction_checks = {
        feature: bool(score_correlations[feature] > 0) for feature in expected_positive
    } | {
        feature: bool(score_correlations[feature] < 0) for feature in expected_negative
    }
    score_logic = {
        "e1_to_e6_mean_monotonic_decreasing": bool(ordered_profile.score_mean.is_monotonic_decreasing),
        "e1_to_e6_median_monotonic_decreasing": bool(ordered_profile.score_median.is_monotonic_decreasing),
        "spearman_correlations": score_correlations.to_dict(),
        "expected_direction_checks": direction_checks,
        "all_expected_directions_pass": bool(all(direction_checks.values())),
    }

    test = split.eq("test")
    train_rates = predictions.loc[split.eq("train"), "economic_type"].value_counts(normalize=True)
    test_rates = predictions.loc[test, "economic_type"].value_counts(normalize=True)
    types = sorted(set(train_rates.index) | set(test_rates.index))
    psi = float(sum((test_rates.get(t, 1e-9) - train_rates.get(t, 1e-9)) * np.log(test_rates.get(t, 1e-9) / train_rates.get(t, 1e-9)) for t in types))
    metrics = {
        "method": "PCA latent stability score + six-component GMM",
        "label_source": "none (unsupervised)", "seed": args.seed,
        "rows": len(frame), "source_column_count": len(REQUIRED_COLUMNS),
        "excluded_columns": excluded, "model": model.diagnostics(),
        "imputer": imputer_metrics,
        "test_mean_confidence": float(predictions.loc[test, "type_confidence"].mean()),
        "test_low_confidence_below_0_5": float(predictions.loc[test, "type_confidence"].lt(.5).mean()),
        "train_test_type_psi": psi,
        "score_logic": score_logic,
        "type_counts": predictions.economic_type.value_counts().sort_index().to_dict(),
        "load": load_meta,
    }
    (args.outdir / "latent_model_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    lines = [
        "# 비지도 잠재 경제점수·유형 모델", "",
        "> 외부 정답 레이블을 만들거나 임의 공식을 지도학습 타깃으로 사용하지 않습니다.", "",
        f"- 입력 원본 컬럼: {metrics['source_column_count']}개(제공 파일은 요청의 46개가 아니라 42개)",
        f"- 모델 입력: 검증된 원본·파생변수 {metrics['model']['input_feature_count']}개",
        f"- PCA 설명분산: {metrics['model']['pca_explained_variance']:.2%}",
        f"- GMM train 실루엣: {metrics['model']['train_silhouette']:.3f}",
        f"- test 평균 유형 확신도: {metrics['test_mean_confidence']:.3f}",
        f"- test 저확신(<0.5): {metrics['test_low_confidence_below_0_5']:.2%}",
        f"- train/test 유형 PSI: {psi:.4f}", "", "## 유형 프로파일", "",
        profile.to_markdown(index=False, floatfmt=".3f"), "",
        "## 군집별 핵심 특성", "", characteristics.to_markdown(index=False), "",
        "## 점수 논리 검증", "",
        f"- E1→E6 평균점수 단조 감소: {score_logic['e1_to_e6_mean_monotonic_decreasing']}",
        f"- E1→E6 중앙값 단조 감소: {score_logic['e1_to_e6_median_monotonic_decreasing']}",
        f"- 기대 방향 전체 통과: {score_logic['all_expected_directions_pass']}", "",
        "## 해석", "",
        "- 종합점수는 train 잠재 안정성 축의 분위수이며 0은 상대적 취약, 100은 상대적 안정입니다.",
        "- E1~E6은 GMM이 학습한 군집을 군집 평균 안정성 순서로 정렬한 유형입니다.",
        "- 이 점수는 부산 청년 표본 내 상대점수이며 미래 부도나 정책 효과의 정답 확률이 아닙니다.",
    ]
    (args.outdir / "latent_model_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": "complete", "metrics": metrics, "outdir": str(args.outdir)}, ensure_ascii=False, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
