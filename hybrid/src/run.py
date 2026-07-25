"""hybrid 오케스트레이션.

STEP 0~4는 `analysis`를 재사용하고(정합성·로딩·분할·전세대체·파생변수),
STEP 5부터 잠재모델(E1~E6) · 정책 연결 · 문진 축소 모델을 얹는다.

실행 (저장소 루트에서):
    python -m hybrid.src.run --input "important data/(합성데이터)종합해커톤.csv" --outdir hybrid/outputs/
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from analysis.src import (
    config as AC,
    consistency,
    features,
    impute,
    load as load_mod,
    split as split_mod,
)

from . import config as C, diagnose, latent, policy, validate


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def _log(step: str, msg: str = "") -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {step:<10} {msg}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="hybrid — 잠재 E1~E6 + 정책 등급 + 문진 축소")
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", default="hybrid/outputs/")
    ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--sample", type=int, default=0)
    args = ap.parse_args(argv)

    seed = args.seed
    random.seed(seed)
    np.random.seed(seed)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    info: dict = {"seed": seed, "input": str(args.input)}

    # ---------------------------------------------------------------- 상류 (analysis 재사용)
    _log("STEP 0-1", "정합성 검증 · 로딩 · 열 제거")
    raw = load_mod.read_raw(args.input)
    if args.sample:
        raw = raw.sample(min(args.sample, len(raw)), random_state=seed).reset_index(drop=True)
        raw.index.name = "row_id"
        _log("STEP 0-1", f"⚠ 샘플 모드 {len(raw):,}행")
    cons = consistency.run_checks(raw)
    consistency.write_report(cons, outdir, n_rows=len(raw))
    df, load_info = load_mod.load(raw, cons.excluded_columns)
    load_info["n_rows"] = len(df)
    load_mod.write_caveats(load_info, outdir, cons.provisional_rates)
    info["load"] = {"n_rows": len(df), "n_columns_after": load_info["n_columns_after"],
                    "dropped": load_info["dropped_columns"]}
    _log("STEP 0-1", f"{len(AC.RAW_COLUMNS)}열 → {load_info['n_columns_after']}열 · "
                     f"위반 {int(cons.table['violations'].sum()):,}건")

    _log("STEP 2-4", "분할 · 전세가 대체 · 파생변수")
    df = split_mod.assign_split(df, seed=seed)
    df, imp_info = impute.impute_jeonse(df, outdir, seed=seed)
    df = features.build_features(df)
    features.summarize(df).to_csv(outdir / "features_summary.csv", index=False, encoding="utf-8-sig")
    info["impute"] = imp_info
    info["split_counts"] = {k: int(v) for k, v in df["split"].value_counts().items()}

    # ---------------------------------------------------------------- 잠재모델 (model.md)
    _log("STEP 5", "잠재 PCA 점수 + GMM 6유형")
    df, lat_info = latent.fit_latent(df, outdir, seed=seed)
    info["latent"] = lat_info
    _log("STEP 5", f"PCA 90% {lat_info['pca_components_for_90pct']}/{lat_info['n_features']}개 · "
                   f"실루엣 {lat_info['silhouette']:.4f} · 확신도 {lat_info['mean_confidence']:.3f}")
    _log("STEP 5", "규모 " + " ".join(f"{k}:{v:,}" for k, v in lat_info["sizes"].items()))

    # ---------------------------------------------------------------- 정책 연결 (analysis)
    _log("STEP 6", "기준 중위소득 등급 · 정책 사각지대")
    df, pol_info = policy.apply_policy(df)
    info["policy"] = pol_info
    print(f"\n★ 정책 사각지대(중위 100% 초과 & 종합점수 하위 25%) = "
          f"{pol_info['blindspot_count']:,}명 ({pol_info['blindspot_share']:.1%})\n", flush=True)

    # ---------------------------------------------------------------- 문진 축소 (analysis 개선)
    _log("STEP 7", "문진 축소 모델")
    df, sur_info = diagnose.train_questionnaire(df, outdir, seed=seed)
    info["survey"] = sur_info
    _log("STEP 7", f"{sur_info['n_questions']}문항 · accuracy {sur_info['test_accuracy']:.3f} · "
                   f"macro F1 {sur_info['test_macro_f1']:.3f} "
                   f"(무작위 {sur_info['random_baseline']:.3f})")

    # ---------------------------------------------------------------- 검증 · 산출
    _log("STEP 8", "검증 리포트 · 시각화")
    validate.make_figures(df, info, outdir / "figures", seed=seed)
    validate.write_report(df, info, outdir)

    keep = (["split", "etype", "etype_name", "major_class", "stability_score",
             "type_confidence", "survey_pred", "survey_confidence", "gmm_cluster",
             "income_grade", "income_to_median", "income_percentile_busan",
             "policy_eligible_by_income", "policy_blindspot", "R_flag",
             "employment_type", "job_name", "region_name"]
            + [f"proba_{e}" for e in C.ETYPE_ORDER]
            + features.DERIVED_ALL
            + [AC.COL_AGE, AC.COL_GENDER, AC.COL_INCOME_Y, AC.COL_SCORE])
    df[[c for c in keep if c in df.columns]].to_csv(
        outdir / "segments.csv", index_label="row_id", encoding="utf-8-sig")

    # 백엔드 전달용 진단 payload 예시 (정밀 = KCB 42변수 / 라이트 = 문진 7문항)
    ref = diagnose.build_percentile_reference(df)
    binning = json.loads((outdir / "binning.json").read_text(encoding="utf-8"))
    Q = diagnose.build_questionnaire(df, binning)
    survey_model = joblib.load(outdir / "survey_model.pkl")["model"]
    samples = (df[df["split"] == "test"]
               .groupby("etype", group_keys=False).head(1).sort_values("etype"))
    payloads = []
    for idx, r in samples.iterrows():
        path = diagnose.explain_survey_path(survey_model, Q.loc[[idx]])
        payloads.append(diagnose.build_payload(r, "precise", percentile_ref=ref, survey_path=path))
    (outdir / "diagnosis_samples.json").write_text(
        json.dumps(_jsonable(payloads), ensure_ascii=False, indent=2), encoding="utf-8")

    fitted = {
        "seed": seed,
        "label_system": {"codes": C.ETYPE_ORDER, "names": C.ETYPE_NAMES, "major": C.ETYPE_MAJOR},
        "latent": {k: lat_info[k] for k in
                   ("pca_components_for_90pct", "latent_dims", "score_components",
                    "score_weights", "cluster_to_etype", "silhouette")},
        "policy": {"median_income_monthly_krw": AC.MEDIAN_INCOME_MONTHLY_KRW,
                   "grade_edges": AC.INCOME_GRADE_EDGES, "grade_labels": AC.INCOME_GRADE_LABELS,
                   "blindspot_score_cut": pol_info["score_cut"]},
        "survey": {"features": C.QUESTION_FEATURES, "depth": sur_info["chosen_depth"],
                   "test_accuracy": sur_info["test_accuracy"],
                   "test_macro_f1": sur_info["test_macro_f1"],
                   "binning": json.loads((outdir / "binning.json").read_text(encoding="utf-8"))},
        "percentile_reference_train": ref,
        "busan_income_reference": {"edges": AC.BUSAN_YOUTH_INCOME_BAND_EDGES,
                                   "shares": AC.BUSAN_YOUTH_INCOME_BAND_SHARES},
    }
    (outdir / "fitted_params.json").write_text(
        json.dumps(_jsonable(fitted), ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "run_metrics.json").write_text(
        json.dumps(_jsonable(info), ensure_ascii=False, indent=2), encoding="utf-8")

    _log("DONE", f"산출물 → {outdir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
