from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

BASE_NUMERIC = {
    "income_band": "추정 연소득", "housing_cost_band": "2년내 현거주지평균전세거래가",
    "debt_band": "신용대출-총대출잔액",
}
FEATURES = ["age_band", "gender", "region", "income_band", "housing_cost_band", "debt_band", "job_turnover", "distress_flag"]


def _edges(series: pd.Series) -> list[float]:
    values = np.unique(series.dropna().quantile([0, .2, .4, .6, .8, 1]).to_numpy(dtype=float))
    if len(values) < 2:
        values = np.array([-np.inf, np.inf])
    values[0], values[-1] = -np.inf, np.inf
    return values.tolist()


def _questions(df: pd.DataFrame, bins: dict) -> pd.DataFrame:
    q = pd.DataFrame(index=df.index)
    q["age_band"] = df["연령대"].astype("Int64").astype(str)
    q["gender"] = df["성별"].astype("Int64").astype(str)
    q["region"] = df["거주지 시군구 코드"].astype("Int64").astype(str)
    for output, source in BASE_NUMERIC.items():
        q[output] = pd.cut(df[source], bins=bins[output], labels=False, include_lowest=True).astype("Int64").astype(str)
    count_band = df["총대출건수"].fillna(0).clip(upper=3).astype("Int64").astype(str)
    q["debt_band"] = q["debt_band"] + "_count" + count_band
    q["job_turnover"] = df["job_turnover"].fillna(0).clip(upper=4).astype("Int64")
    q["distress_flag"] = (df["cash_advance_flag"].eq(1) | df["total_delinq_cnt"].gt(0)).astype("int8")
    return q


def train_reduced(df: pd.DataFrame, split: pd.Series, outdir: Path, seed: int) -> tuple[dict, np.ndarray]:
    train = split.eq("train")
    test = split.eq("test")
    bins = {name: _edges(df.loc[train, source]) for name, source in BASE_NUMERIC.items()}
    q = _questions(df, bins)
    categorical = FEATURES[:6]
    numeric = FEATURES[6:]
    prep = ColumnTransformer([
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("ohe", OneHotEncoder(handle_unknown="ignore"))]), categorical),
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
    ])
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    tree_results = {}
    for depth in (4, 5):
        candidate = Pipeline([("prep", prep), ("model", DecisionTreeClassifier(max_depth=depth, min_samples_leaf=30, class_weight="balanced", random_state=seed))])
        tree_results[depth] = float(cross_val_score(candidate, q.loc[train, FEATURES], df.loc[train, "segment"], cv=cv, scoring="f1_macro", n_jobs=-1).mean())
    depth = max(tree_results, key=tree_results.get)
    tree = Pipeline([("prep", prep), ("model", DecisionTreeClassifier(max_depth=depth, min_samples_leaf=30, class_weight="balanced", random_state=seed))])
    logistic = Pipeline([("prep", prep), ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed))])
    log_cv = float(cross_val_score(logistic, q.loc[train, FEATURES], df.loc[train, "segment"], cv=cv, scoring="f1_macro", n_jobs=-1).mean())
    tree.fit(q.loc[train, FEATURES], df.loc[train, "segment"])
    logistic.fit(q.loc[train, FEATURES], df.loc[train, "segment"])
    pred = tree.predict(q.loc[test, FEATURES])
    proba = tree.predict_proba(q.loc[test, FEATURES])
    confidence = proba.max(axis=1)
    metrics = {
        "selected": "decision_tree", "depth": depth, "tree_cv_macro_f1": tree_results,
        "logistic_cv_macro_f1": log_cv, "test_macro_f1": float(f1_score(df.loc[test, "segment"], pred, average="macro")),
        "test_accuracy": float(accuracy_score(df.loc[test, "segment"], pred)),
        "classification_report": classification_report(df.loc[test, "segment"], pred, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(df.loc[test, "segment"], pred, labels=[f"T{i}" for i in range(1, 7)]).tolist(),
        "classes": [f"T{i}" for i in range(1, 7)], "low_confidence_below_0_5": float(np.mean(confidence < .5)),
        "confidence_quantiles": {str(k): float(v) for k, v in pd.Series(confidence).quantile([0, .1, .25, .5, .75, .9, 1]).items()},
    }
    joblib.dump({"features": FEATURES, "bins": bins, "pipeline": tree}, outdir / "classifier.pkl")
    (outdir / "binning.json").write_text(json.dumps(bins, ensure_ascii=False, indent=2), encoding="utf-8")
    names = tree.named_steps["prep"].get_feature_names_out().tolist()
    (outdir / "decision_rules.txt").write_text(export_text(tree.named_steps["model"], feature_names=names), encoding="utf-8")
    return metrics, confidence
