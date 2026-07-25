"""STEP 8 — [학습③] 8문항 축소 분류기 (method.md §12).

실제 사용자는 42개 금융변수를 들고 오지 않는다. 42변수로 만든 라벨을
사용자가 답할 수 있는 8문항으로 얼마나 복원하는가를 재는 압축 과제다.
구간 경계는 train에서만 산출해 `binning.json`에 저장하고 실서비스에서 재사용한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

from . import config as C

# 8문항으로 사용자가 답할 수 있는(=축 변수 중 관측 가능한) 항목.
# 나머지 축 변수는 KCB 배치에서만 얻을 수 있어 축소 모델의 성능 상한을 결정한다.
OBSERVABLE_IN_QUESTIONNAIRE = {"job_turnover", "cash_advance_flag", "total_delinq_cnt"}

CATEGORICAL = ["age_band", "gender", "region"]
ORDINAL = ["income_band", "housing_cost_band", "debt_band", "job_turnover", "distress_flag"]
FEATURES = CATEGORICAL + ORDINAL


def _quantile_edges(s: pd.Series, bins: int) -> list[float]:
    qs = np.linspace(0, 1, bins + 1)[1:-1]
    edges = [float(v) for v in np.unique(np.quantile(s.dropna(), qs))]
    return edges


def _apply_edges(s: pd.Series, edges: list[float]) -> pd.Series:
    if not edges:
        return pd.Series(np.zeros(len(s)), index=s.index, dtype="int8")
    return pd.Series(np.digitize(s.to_numpy(dtype=float), edges), index=s.index).astype("int8")


def build_binning(df: pd.DataFrame) -> dict:
    """train 행만으로 구간 경계 산출 (§12.1)."""
    train = df[df["split"] == "train"]
    borrower = train[train[C.COL_LOAN_CNT].fillna(0) > 0]
    return {
        "income_band": {
            "source": C.COL_INCOME_Y,
            "edges": _quantile_edges(train[C.COL_INCOME_Y], C.INCOME_BANDS),
        },
        "housing_cost_band": {
            "source": "jeonse_value",
            "edges": _quantile_edges(train["jeonse_value"], C.HOUSING_BANDS),
        },
        "debt_band": {
            "source": f"{C.COL_LOAN_CNT} + {C.COL_CREDIT_BAL}",
            "rule": "총대출건수 == 0 → band 0, 그 외 신용대출 잔액 분위수로 band 1..n",
            "edges": _quantile_edges(borrower[C.COL_CREDIT_BAL], C.DEBT_BANDS),
        },
    }


def build_questionnaire(df: pd.DataFrame, binning: dict) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    X["age_band"] = df[C.COL_AGE].astype("Int64").astype(str)
    X["gender"] = df[C.COL_GENDER].astype("Int64").astype(str)
    X["region"] = df[C.COL_REGION_HOME].astype("Int64").astype(str)
    X["income_band"] = _apply_edges(df[C.COL_INCOME_Y], binning["income_band"]["edges"])
    X["housing_cost_band"] = _apply_edges(df["jeonse_value"], binning["housing_cost_band"]["edges"])

    debt = _apply_edges(df[C.COL_CREDIT_BAL].fillna(0), binning["debt_band"]["edges"]) + 1
    debt[df[C.COL_LOAN_CNT].fillna(0) == 0] = 0
    X["debt_band"] = debt.astype("int8")

    X["job_turnover"] = pd.to_numeric(df["job_turnover"], errors="coerce").fillna(0).astype("int16")
    X["distress_flag"] = (
        (df["cash_advance_flag"] == 1) | (df["total_delinq_cnt"].fillna(0) > 0)
    ).astype("int8")
    return X[FEATURES]


def _tree_pipeline(depth: int, seed: int) -> Pipeline:
    return Pipeline([
        ("prep", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
            ("num", "passthrough", ORDINAL),
        ])),
        ("model", DecisionTreeClassifier(
            max_depth=depth, class_weight="balanced", random_state=seed
        )),
    ])


def _logreg_pipeline(seed: int) -> Pipeline:
    return Pipeline([
        ("prep", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
            ("num", StandardScaler(), ORDINAL),
        ])),
        ("model", LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=seed
        )),
    ])


def train_reduced(df: pd.DataFrame, outdir: Path, seed: int = C.SEED) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    binning = build_binning(out)
    X = build_questionnaire(out, binning)
    y = out["segment"].astype(str)

    # T5·T6는 사전 스크리닝 2문항으로 결정적 배정된다 → 모델은 주 4유형만 학습·평가한다.
    is_main = out["segment"].isin(C.MAIN_SEGMENTS)
    tr, va, te = (
        (out["split"] == s) & is_main for s in ("train", "valid", "test")
    )

    # 주 모델: DecisionTree — valid macro F1로 깊이 선택
    depth_scores = {}
    for depth in C.TREE_MAX_DEPTHS:
        pipe = _tree_pipeline(depth, seed)
        pipe.fit(X[tr], y[tr])
        depth_scores[depth] = float(f1_score(y[va], pipe.predict(X[va]), average="macro"))
    best_depth = max(depth_scores, key=depth_scores.get)

    tree = _tree_pipeline(best_depth, seed)
    tree.fit(X[tr], y[tr])
    logreg = _logreg_pipeline(seed)
    logreg.fit(X[tr], y[tr])

    cv = StratifiedKFold(n_splits=C.CV_FOLDS, shuffle=True, random_state=seed)
    cv_tree = cross_val_score(
        _tree_pipeline(best_depth, seed), X[tr], y[tr], cv=cv, scoring="f1_macro", n_jobs=-1
    )
    cv_log = cross_val_score(
        _logreg_pipeline(seed), X[tr], y[tr], cv=cv, scoring="f1_macro", n_jobs=-1
    )

    def evaluate(model) -> dict:
        pred = model.predict(X[te])
        return {
            "test_accuracy": float(accuracy_score(y[te], pred)),
            "test_macro_f1": float(f1_score(y[te], pred, average="macro")),
            "report": classification_report(y[te], pred, output_dict=True, zero_division=0),
        }

    metrics = {
        "depth_search_valid_macro_f1": {int(k): v for k, v in depth_scores.items()},
        "chosen_depth": int(best_depth),
        "decision_tree": evaluate(tree) | {
            "cv_macro_f1_mean": float(cv_tree.mean()),
            "cv_macro_f1_std": float(cv_tree.std()),
        },
        "logistic_regression": evaluate(logreg) | {
            "cv_macro_f1_mean": float(cv_log.mean()),
            "cv_macro_f1_std": float(cv_log.std()),
        },
    }

    labels = list(C.MAIN_SEGMENTS)
    cm = confusion_matrix(y[te], tree.predict(X[te]), labels=labels)
    metrics["confusion_matrix"] = {"labels": labels, "matrix": cm.tolist()}

    # 서비스 예측 = 스크리닝(T5·T6, 확신도 1.0) + 모델(T1~T4)
    proba = tree.predict_proba(X)
    conf = pd.Series(proba.max(axis=1), index=out.index)
    pred = pd.Series(tree.predict(X), index=out.index)
    special = ~is_main
    pred[special] = out.loc[special, "segment"]
    conf[special] = 1.0
    out["reduced_pred"] = pred
    out["reduced_confidence"] = conf
    out["reduced_source"] = np.where(special, "screening", "model")

    metrics["special_handling"] = {
        "segments": C.SPECIAL_SEGMENTS,
        "screening_questions": C.SCREENING_QUESTIONS,
        "rows_screened": int(special.sum()),
        "screened_share": float(special.mean()),
        "model_target_classes": labels,
        "model_train_rows": int(tr.sum()),
    }

    # 확신도 분포는 모델이 실제로 판정한 구간(T1~T4)만 대상으로 본다.
    conf = conf[is_main]
    metrics["confidence"] = {
        "mean": float(conf.mean()),
        "p10": float(conf.quantile(0.10)),
        "median": float(conf.median()),
        "share_below_0.5": float((conf < 0.5).mean()),
        "share_below_0.7": float((conf < 0.7).mean()),
    }
    metrics["reproduction_sentence"] = (
        f"42개 금융변수 기반 라벨을 스크리닝 2문항 + 8문항으로 재현 — "
        f"T5·T6는 결정적 규칙으로 100%, 주 4유형(T1~T4)은 "
        f"{metrics['decision_tree']['test_accuracy']:.1%} "
        f"(macro F1 {metrics['decision_tree']['test_macro_f1']:.3f})"
    )

    # 산출물
    joblib.dump(
        {
            "model": tree,
            "features": FEATURES,
            "binning": binning,
            "target_classes": labels,
            "screening": C.SCREENING_QUESTIONS,  # 모델 호출 전 결정적 배정
        },
        outdir / "classifier.pkl",
    )
    (outdir / "binning.json").write_text(
        json.dumps(binning, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    feat_names = tree.named_steps["prep"].get_feature_names_out().tolist()
    rules = export_text(tree.named_steps["model"], feature_names=feat_names, max_depth=best_depth)
    screening_lines = "\n".join(f"#   {k}: {v}" for k, v in C.SCREENING_QUESTIONS.items())
    (outdir / "decision_rules.txt").write_text(
        f"# 축소 분류기 판정 규칙 (DecisionTree, max_depth={best_depth})\n"
        f"# 라벨: {', '.join(f'{k}={v}' for k, v in C.SEGMENT_NAMES.items())}\n"
        "#\n"
        "# [1단계] 사전 스크리닝 — 아래에 해당하면 아래 트리를 타지 않고 즉시 배정한다.\n"
        f"{screening_lines}\n"
        "#\n"
        f"# [2단계] 8문항 트리 — 대상 클래스 {labels}\n"
        f"# 클래스 순서: {list(tree.named_steps['model'].classes_)}\n\n{rules}",
        encoding="utf-8",
    )
    return out, metrics
