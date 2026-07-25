"""문진 축소 모델 + 진단 payload — analysis 자산을 E1~E6 라벨에 적용한다.

실제 사용자는 42개 금융변수를 들고 오지 않는다. 잠재모델이 만든 E1~E6 라벨을
사용자가 답할 수 있는 6문항으로 재현하고, 판정 근거를 규칙으로 출력한다.
연령·성별·거주지는 실측상 기여가 0이라 문진에서 제외했다.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier, export_text

from analysis.src import config as AC

from . import config as C


def _edges(series: pd.Series, train: pd.Series, bins: int) -> list[float]:
    qs = np.linspace(0, 1, bins + 1)[1:-1]
    return [float(v) for v in np.unique(np.quantile(pd.to_numeric(train, errors="coerce").dropna(), qs))]


def build_binning(df: pd.DataFrame) -> dict:
    """구간 경계는 train에서만 산출해 실서비스에서 재사용한다."""
    tr = df[df["split"] == "train"]
    return {
        "income_band": {"source": AC.COL_INCOME_Y,
                        "edges": _edges(df[AC.COL_INCOME_Y], tr[AC.COL_INCOME_Y], C.BAND_COUNT)},
        "consumption_band": {"source": "consumption_ratio",
                             "edges": _edges(df["consumption_ratio"], tr["consumption_ratio"], C.BAND_COUNT)},
        "repay_band": {"source": "dsr",
                       "edges": _edges(df["dsr"], tr["dsr"], C.BAND_COUNT)},
        "debt_band": {"source": "total_loan_balance",
                      "edges": _edges(df["total_loan_balance"], tr["total_loan_balance"], C.BAND_COUNT)},
    }


def build_questionnaire(df: pd.DataFrame, binning: dict) -> pd.DataFrame:
    Q = pd.DataFrame(index=df.index)
    Q["employment_type"] = df["employment_type"].astype(str)
    for band, src in [("income_band", AC.COL_INCOME_Y), ("consumption_band", "consumption_ratio"),
                      ("repay_band", "dsr"), ("debt_band", "total_loan_balance")]:
        edges = binning[band]["edges"]
        v = pd.to_numeric(df[src], errors="coerce").fillna(0).to_numpy(dtype=float)
        Q[band] = np.digitize(v, edges).astype("int8") if edges else 0
    Q["job_turnover"] = pd.to_numeric(df["job_turnover"], errors="coerce").fillna(0).astype("int16")
    Q["distress_flag"] = (
        (df["cash_advance_flag"] == 1) | (df["total_delinq_cnt"].fillna(0) > 0)
    ).astype("int8")
    return Q[C.QUESTION_FEATURES]


def _pipeline(depth: int, seed: int) -> Pipeline:
    return Pipeline([
        ("prep", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), C.QUESTION_CATEGORICAL),
            ("num", "passthrough", C.QUESTION_NUMERIC),
        ])),
        ("model", DecisionTreeClassifier(max_depth=depth, class_weight="balanced", random_state=seed)),
    ])


def train_questionnaire(df: pd.DataFrame, outdir: Path, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    binning = build_binning(out)
    X = build_questionnaire(out, binning)
    y = out["etype"].astype(str)
    tr, va, te = (out["split"] == s for s in ("train", "valid", "test"))

    depth_scores = {}
    for depth in C.TREE_MAX_DEPTHS:
        pipe = _pipeline(depth, seed).fit(X[tr], y[tr])
        depth_scores[depth] = float(f1_score(y[va], pipe.predict(X[va]), average="macro"))
    best_depth = max(depth_scores, key=depth_scores.get)
    tree = _pipeline(best_depth, seed).fit(X[tr], y[tr])

    cv = StratifiedKFold(n_splits=C.CV_FOLDS, shuffle=True, random_state=seed)
    cv_f1 = cross_val_score(_pipeline(best_depth, seed), X[tr], y[tr], cv=cv,
                            scoring="f1_macro", n_jobs=-1)

    pred = tree.predict(X[te])
    proba_all = tree.predict_proba(X)
    labels = list(tree.named_steps["model"].classes_)
    metrics = {
        "depth_search_valid_macro_f1": {int(k): v for k, v in depth_scores.items()},
        "chosen_depth": int(best_depth),
        "n_questions": len(C.QUESTION_FEATURES),
        "test_accuracy": float(accuracy_score(y[te], pred)),
        "test_macro_f1": float(f1_score(y[te], pred, average="macro")),
        "random_baseline": 1.0 / len(labels),
        "cv_macro_f1_mean": float(cv_f1.mean()),
        "cv_macro_f1_std": float(cv_f1.std()),
        "report": classification_report(y[te], pred, output_dict=True, zero_division=0),
        "confusion_matrix": {"labels": labels,
                             "matrix": confusion_matrix(y[te], pred, labels=labels).tolist()},
    }
    conf = pd.Series(proba_all.max(axis=1), index=out.index)
    out["survey_pred"] = tree.predict(X)
    out["survey_confidence"] = conf
    metrics["confidence"] = {
        "mean": float(conf.mean()), "median": float(conf.median()),
        "share_below_0.5": float((conf < 0.5).mean()),
        "share_below_0.7": float((conf < 0.7).mean()),
    }
    metrics["agreement_with_latent"] = float((out["survey_pred"] == out["etype"]).mean())

    joblib.dump({"model": tree, "features": C.QUESTION_FEATURES, "binning": binning,
                 "classes": labels, "screening": C.SCREENING_FLAGS}, outdir / "survey_model.pkl")
    (outdir / "binning.json").write_text(json.dumps(binning, ensure_ascii=False, indent=2), encoding="utf-8")

    names = tree.named_steps["prep"].get_feature_names_out().tolist()
    rules = export_text(tree.named_steps["model"], feature_names=names, max_depth=best_depth)
    (outdir / "decision_rules.txt").write_text(
        f"# 문진 축소 모델 판정 규칙 (DecisionTree, max_depth={best_depth})\n"
        f"# 라벨: {', '.join(f'{k}={v}' for k, v in C.ETYPE_NAMES.items())}\n"
        f"# 문항 {len(C.QUESTION_FEATURES)}개: {C.QUESTION_FEATURES}\n"
        f"# 클래스 순서: {labels}\n\n{rules}", encoding="utf-8")
    return out, metrics


# ---------------------------------------------------------------- 백엔드 전달용 진단 payload
# 지표별 해석 방향 — True면 값이 클수록 나쁨(백분위가 높을수록 위험)
INDICATORS: dict[str, tuple[str, bool]] = {
    AC.COL_SCORE: ("신용평점", False),
    "consumption_ratio": ("소비/소득", True),
    "dsr": ("상환부담", True),
    "total_loan_balance": ("총대출잔액", True),
    AC.COL_INCOME_Y: ("추정 연소득", False),
}


def build_percentile_reference(df: pd.DataFrame) -> dict[str, list[float]]:
    """train 기준 백분위 격자 — '표본 10만 명 중 상위 X%' 문구의 근거."""
    tr = df[df["split"] == "train"]
    grid = np.linspace(0, 100, 101)
    return {
        col: [float(v) for v in np.percentile(pd.to_numeric(tr[col], errors="coerce").dropna(), grid)]
        for col in INDICATORS
    }


def _percentile(value: float, knots: list[float]) -> float:
    if value is None or pd.isna(value):
        return float("nan")
    return float(np.interp(value, np.maximum.accumulate(np.asarray(knots, dtype=float)),
                           np.linspace(0, 100, 101)))


def explain_survey_path(model, X_row: pd.DataFrame) -> list[str]:
    """DecisionTree 판정 경로를 사람이 읽을 수 있는 조건 목록으로 변환한다."""
    prep, tree = model.named_steps["prep"], model.named_steps["model"]
    names = prep.get_feature_names_out()
    Xt = prep.transform(X_row)
    node_idx = model.named_steps["model"].decision_path(Xt).indices
    feat, thr = tree.tree_.feature, tree.tree_.threshold
    steps = []
    for node in node_idx:
        if feat[node] < 0:      # leaf
            continue
        name = str(names[feat[node]]).split("__", 1)[-1]
        went_left = Xt[0, feat[node]] <= thr[node]
        steps.append(f"{name} {'≤' if went_left else '>'} {thr[node]:.2f}")
    return steps


def build_payload(row: pd.Series, source: str = "precise",
                  percentile_ref: dict[str, list[float]] | None = None,
                  survey_path: list[str] | None = None) -> dict:
    """유형 + 그 유형이 도출된 근거 점수를 백엔드가 받아쓸 형태로 조립한다."""
    reasons: list[str] = []
    if row.get("policy_blindspot") == 1:
        reasons.append("소득은 기준 중위소득 100%를 넘지만 종합점수가 하위 25%")
    if row.get("R_flag") == 1:
        reasons.append("현 거주지에 2년내 실거래 기록 없음(비정형 주거 추정)")
    if row.get("cash_advance_flag") == 1:
        reasons.append("최근 12개월 현금서비스 이용")
    if pd.notna(row.get("total_delinq_cnt")) and row.get("total_delinq_cnt", 0) > 0:
        reasons.append("최근 연체 이력 존재")
    if row.get("self_employed") == 1:
        reasons.append("자영업 — 동일 소득대비 재무 부담이 큰 집단")

    conf = float(row.get("type_confidence", np.nan))
    guidance = next(txt for lo, txt in C.CONFIDENCE_BANDS if conf >= lo) if pd.notna(conf) else "확신도 없음"

    # 지표별 표본 백분위 — "왜 이 점수인가"의 근거
    indicators = []
    if percentile_ref:
        for col, (label, higher_is_worse) in INDICATORS.items():
            if col not in row:
                continue
            value = pd.to_numeric(pd.Series([row[col]]), errors="coerce").iloc[0]
            pct = _percentile(value, percentile_ref[col])
            if pd.isna(pct):
                continue
            risk_pct = pct if higher_is_worse else 100 - pct
            indicators.append({
                "name": label,
                "value": round(float(value), 4),
                "percentile": round(pct, 1),
                "position": f"{'상위' if pct >= 50 else '하위'} {min(pct, 100 - pct):.0f}%",
                "risk_percentile": round(risk_pct, 1),
                "flagged": bool(risk_pct >= 75),
            })
        indicators.sort(key=lambda x: -x["risk_percentile"])
        for ind in indicators:
            if ind["flagged"]:
                reasons.append(f"{ind['name']} {ind['position']} — 표본 대비 위험 구간")

    return {
        "source": source,
        "etype": row["etype"],
        "etype_name": row.get("etype_name"),
        "major_class": row.get("major_class"),
        "stability_score": round(float(row["stability_score"]), 1),
        "type_confidence": round(conf, 4) if pd.notna(conf) else None,
        "confidence_guidance": guidance,
        "income": {
            "grade": str(row.get("income_grade")),
            "ratio_to_median": round(float(row.get("income_to_median", np.nan)), 3),
            "percentile_busan_youth": round(float(row.get("income_percentile_busan", np.nan)), 1),
            "policy_eligible": bool(row.get("policy_eligible_by_income", 0)),
        },
        "employment_type": row.get("employment_type"),
        "flags": {
            "policy_blindspot": bool(row.get("policy_blindspot", 0)),
            "no_housing_record": bool(row.get("R_flag", 0)),
            "cash_advance": bool(row.get("cash_advance_flag", 0)),
            "multi_debt": bool(row.get("multi_debt", 0)),
        },
        "indicators": indicators,
        "survey_decision_path": survey_path,
        "reasons": reasons,
    }
