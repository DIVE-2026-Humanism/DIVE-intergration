from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path
from typing import Any

import numpy as np
from .anomaly import detect_anomalies
from .consistency import check_consistency
from .features import build_features
from .full_questionnaire import evaluate_full_questionnaire
from .impute import fit_imputer
from .load import load_csv
from .reduced_model import train_reduced
from .residual import fit_residual
from .scores import build_scores
from .segment import segment
from .split import split_labels
from .validate import validate


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="부산 청년 1인가구 경제 계층 6유형 파이프라인")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    random.seed(args.seed); np.random.seed(args.seed)
    logging.info("STEP 0-1 load and consistency")
    raw, load_meta = load_csv(args.input)
    frame, excluded, consistency = check_consistency(raw, args.outdir)
    logging.info("STEP 2 split")
    splits = split_labels(frame, args.seed)
    logging.info("STEP 3 jeonse imputation")
    frame, imputer_metrics = fit_imputer(frame, splits, args.outdir, args.seed)
    logging.info("STEP 4 features")
    frame = build_features(frame, args.outdir)
    logging.info("STEP 5 credit residual")
    frame, residual_metrics = fit_residual(frame, splits, args.outdir, args.seed)
    logging.info("STEP 6 scores")
    frame, score_params = build_scores(frame, splits)
    logging.info("STEP 7 segmentation and GMM diagnostics")
    frame, segment_params = segment(frame, splits, args.seed)
    logging.info("STEP 8 reduced classifier")
    reduced_metrics, _ = train_reduced(frame, splits, args.outdir, args.seed)
    full_metrics = evaluate_full_questionnaire(frame, splits, segment_params, args.outdir)
    logging.info("STEP 9 anomaly detection")
    frame, anomaly_metrics = detect_anomalies(frame, splits, args.outdir, args.seed)

    params = {
        "seed": args.seed, "split_counts": splits.value_counts().to_dict(),
        "load": load_meta, "excluded_columns": excluded,
        "scores": score_params, "segment": segment_params,
    }
    metrics = {"imputer": imputer_metrics, "residual": residual_metrics, "reduced": reduced_metrics, "full_questionnaire": full_metrics, "anomaly": anomaly_metrics}
    (args.outdir / "fitted_params.json").write_text(json.dumps(_jsonable(params), ensure_ascii=False, indent=2), encoding="utf-8")
    (args.outdir / "model_metrics.json").write_text(json.dumps(_jsonable(metrics), ensure_ascii=False, indent=2), encoding="utf-8")
    caveats = [
        "# 데이터 한계", "", "- 추정가구원수 컬럼이 없어 이미 1인가구로 필터링된 데이터로 간주했습니다.",
        "- KCB 직업군 코드북이 없어 코드에 의미를 부여하지 않았습니다.",
        "- 금액은 분포상 천원 단위로 추정합니다.", "- 행정동이 아닌 시군구 단위만 분석할 수 있습니다.",
        "- 합성데이터의 논리 불일치와 실제 모집단 대표성 한계가 있습니다.",
    ]
    (args.outdir / "data_caveats.md").write_text("\n".join(caveats), encoding="utf-8")
    output_columns = [
        "row_id", "segment", "segment_name", "operational_segment", "H_flag",
        "financial_stress_score", "employment_instability_score", "anomaly",
        "추정 연소득", "dsr", "신용평점", "job_turnover", "income_trajectory",
        "consumption_ratio", "jeonse_income_multiple", "credit_score_residual", "total_delinq_cnt",
    ]
    segments = frame[output_columns].copy()
    segments.insert(1, "split", splits.to_numpy())
    segments.to_csv(args.outdir / "segments.csv", index=False, encoding="utf-8-sig")
    logging.info("STEP 10 validation and figures")
    validate(frame, load_meta, excluded, consistency, params, metrics, args.outdir, args.seed)
    manifest = {"status": "complete", "rows": len(frame), "unassigned": int(frame["segment"].isna().sum()), "outputs": sorted(p.name for p in args.outdir.iterdir())}
    (args.outdir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "segment_counts": segment_params["segment_counts"], "outdir": str(args.outdir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
