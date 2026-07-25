"""오케스트레이션 (method.md §17).

실행:
    python -m src.run --input data/kcb.csv --outdir outputs/ [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import (
    anomaly,
    config as C,
    consistency,
    features,
    impute,
    load as load_mod,
    reduced_model,
    residual,
    scores,
    segment as segment_mod,
    split as split_mod,
    validate,
)


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return json.loads(obj.to_json(orient="split"))
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def _log(step: str, msg: str = "") -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {step:<9} {msg}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="부산 청년 1인가구 경제 계층 6유형 분류 파이프라인")
    ap.add_argument("--input", required=True, help="KCB 마이크로데이터 CSV 경로")
    ap.add_argument("--outdir", default="outputs/", help="산출물 디렉터리")
    ap.add_argument("--seed", type=int, default=C.SEED, help="난수 시드 (기본 42)")
    ap.add_argument("--sample", type=int, default=0,
                    help="스모크 테스트용 행 샘플 수 (0=전수). 리포트에 표기됨")
    args = ap.parse_args(argv)

    seed = args.seed
    random.seed(seed)
    np.random.seed(seed)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    figdir = outdir / "figures"

    info: dict = {"seed": seed, "input": str(args.input)}

    # ---------------------------------------------------------------- STEP 0
    _log("STEP 0", "정합성 26종 검증")
    raw = load_mod.read_raw(args.input)
    if args.sample:
        raw = raw.sample(min(args.sample, len(raw)), random_state=seed).reset_index(drop=True)
        raw.index.name = "row_id"
        _log("STEP 0", f"⚠ 샘플 모드: {len(raw):,}행만 사용")
    cons = consistency.run_checks(raw)
    consistency.write_report(cons, outdir, n_rows=len(raw))
    info["consistency"] = {
        "table": cons.table.to_dict(orient="records"),
        "provisional_rates": cons.provisional_rates,
        "provisional_added": cons.provisional_added,
    }
    _log("STEP 0", f"위반 합계 {int(cons.table['violations'].sum()):,}건 · "
                   f"제거 열 {len(cons.excluded_columns)}개"
                   + (f" (보류 자동 추가: {cons.provisional_added})" if cons.provisional_added else ""))

    # ---------------------------------------------------------------- STEP 1
    _log("STEP 1", "로딩 · 센티널 · 열 제거")
    df, load_info = load_mod.load(raw, cons.excluded_columns)
    load_info["n_rows"] = len(df)
    info["load"] = load_info
    info["n_rows"] = len(df)
    load_mod.write_caveats(load_info, outdir, cons.provisional_rates)
    _log("STEP 1", f"{len(C.RAW_COLUMNS)}열 → {load_info['n_columns_after']}열")

    # ---------------------------------------------------------------- STEP 2
    _log("STEP 2", "train 70 / valid 15 / test 15")
    df = split_mod.assign_split(df, seed=seed)
    counts = df["split"].value_counts()
    info["split_counts"] = {k: int(counts.get(k, 0)) for k in ("train", "valid", "test")}

    # ---------------------------------------------------------------- STEP 3
    _log("STEP 3", "[학습①] 전세가 결측 대체")
    df, imp_info = impute.impute_jeonse(df, outdir, seed=seed)
    info["impute"] = imp_info
    _log("STEP 3", f"채택 {imp_info['chosen']} "
                   f"(model MAE {imp_info['model_mae']:,.0f} vs base {imp_info['baseline_mae']:,.0f})")

    # ---------------------------------------------------------------- STEP 4
    _log("STEP 4", "파생변수")
    df = features.build_features(df)
    fsum = features.summarize(df)
    fsum.to_csv(outdir / "features_summary.csv", index=False, encoding="utf-8-sig")

    # ---------------------------------------------------------------- STEP 5
    _log("STEP 5", "[학습②] 신용평점 잔차")
    df, res_info = residual.fit_residual(df, outdir, seed=seed)
    info["residual"] = res_info
    _log("STEP 5", f"채택 {res_info['chosen']} · test R² {res_info['test_r2']:.3f}")

    # ---------------------------------------------------------------- STEP 6
    _log("STEP 6", "축 스코어 (PCA 진단 분기)")
    df, sc_info = scores.build_scores(df, seed=seed)
    info["scores"] = sc_info
    for axis_name, meta in sc_info["axes"].items():
        _log("STEP 6", f"{axis_name} PC1 {meta['pc1_evr']:.1%} → {meta['weight_mode']}")

    # ---------------------------------------------------------------- STEP 7
    _log("STEP 7", "6유형 배정 (GMM 진단 분기)")
    df, seg_info = segment_mod.segment(df, sc_info["axis_columns"], seed=seed)
    info["segment"] = seg_info
    _log("STEP 7", f"라벨 주도권 {seg_info['label_source']} · "
                   f"실루엣 {seg_info['gmm']['best_k_silhouette']:.3f} "
                   f"(best k={seg_info['gmm']['best_k_by_bic']})")
    _log("STEP 7", "규모 " + " ".join(f"{k}:{v:,}" for k, v in seg_info["sizes"].items()))
    print(f"\n★ T3(잠재 불안군) = {seg_info['sizes'].get('T3', 0):,}명 "
          f"({seg_info['t3_share']:.2%})\n", flush=True)
    for w in seg_info["warnings"]:
        print(w, file=sys.stderr, flush=True)

    # ---------------------------------------------------------------- STEP 8
    _log("STEP 8", "[학습③] 8문항 축소 분류기")
    df, red_info = reduced_model.train_reduced(df, outdir, seed=seed)
    info["reduced"] = red_info
    _log("STEP 8", red_info["reproduction_sentence"])

    # ---------------------------------------------------------------- STEP 9
    _log("STEP 9", "[학습④] 이상탐지")
    df, an_info = anomaly.detect_anomaly(df, outdir, seed=seed)
    info["anomaly"] = an_info
    _log("STEP 9", f"이상치 {an_info['n_anomalies']:,}건 · T4 중복 "
                   f"{an_info['share_of_anomalies_in_T4']:.1%}")

    # ---------------------------------------------------------------- STEP 10
    _log("STEP 10", "검증 리포트 · 시각화")
    validate.make_figures(df, info, figdir, seed=seed)
    validate.write_report(df, info, outdir)

    # segments.csv
    seg_cols = (
        ["split", "segment", "segment_name", "segment_ops", "segment_rule", "H_flag",
         C.FINANCIAL_SCORE, C.EMPLOYMENT_SCORE, "credit_score_residual",
         "reduced_pred", "reduced_confidence", "reduced_source", "anomaly", "gmm_cluster",
         "jeonse_imputed"]
        + features.DERIVED_ALL
        + [C.COL_AGE, C.COL_GENDER, C.COL_REGION_HOME, C.COL_JOB, C.COL_INCOME_Y, C.COL_SCORE]
    )
    df[[c for c in seg_cols if c in df.columns]].to_csv(
        outdir / "segments.csv", index_label="row_id", encoding="utf-8-sig"
    )

    # fitted_params.json — train 기준 통계량 (누수 방지 핵심)
    fitted = {
        "seed": seed,
        "split_ratio": C.SPLIT_RATIO,
        "excluded_columns": cons.excluded_columns,
        "provisional_violation_rates": cons.provisional_rates,
        "jeonse_imputer": {
            "chosen": imp_info["chosen"],
            "region_median": imp_info["region_median"],
            "global_median": imp_info["global_median"],
            "metrics": {k: imp_info[k] for k in
                        ("model_mae", "model_r2", "baseline_mae", "baseline_r2")},
        },
        "quantile_grids": sc_info["quantile_grids"],
        "axis_weights": {k: v["weights"] for k, v in sc_info["axes"].items()},
        "axis_pc1_evr": {k: v["pc1_evr"] for k, v in sc_info["axes"].items()},
        "axis_weight_mode": {k: v["weight_mode"] for k, v in sc_info["axes"].items()},
        "segment_cuts": seg_info["cuts"],
        "h_flag_cut": seg_info["h_flag"]["jeonse_income_multiple_cut"],
        "gmm": {k: seg_info["gmm"][k] for k in
                ("best_k_by_bic", "best_k_silhouette", "gmm_led", "ari_vs_rules", "agreement_rate")},
        "label_source": seg_info["label_source"],
        "binning": json.loads((outdir / "binning.json").read_text(encoding="utf-8")),
        "reduced_model": {
            "chosen_depth": red_info["chosen_depth"],
            "test_accuracy": red_info["decision_tree"]["test_accuracy"],
            "test_macro_f1": red_info["decision_tree"]["test_macro_f1"],
        },
    }
    (outdir / "fitted_params.json").write_text(
        json.dumps(_jsonable(fitted), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "run_metrics.json").write_text(
        json.dumps(_jsonable({k: v for k, v in info.items() if k != "segment"}
                             | {"segment": {k: v for k, v in seg_info.items()
                                            if k != "gmm_crosstab"}}),
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _log("DONE", f"산출물 → {outdir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
