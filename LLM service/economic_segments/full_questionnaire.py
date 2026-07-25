from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from .config import SEGMENT_NAMES


QUESTION_FIELDS = [
    "파산, 개인회생 신청 여부", "Thin Filer 여부", "총대출건수", "신용평점",
    "추정 연소득", "2년전 추정 연소득 금액", "증빙연소득",
    "총 대출 상환금액 (최근 12개월)", "최근 12개월 신용카드소비금액",
    "최근 12개월 체크카드소비금액", "최근 12개월 현금서비스이용금액",
    "대출연체건수", "카드연체건수", "대출연체금액", "카드연체금액",
    "2년내 직장명이력건수", "신용대출-총대출잔액",
    "주택담보대출-총대출잔액", "정책자금대출-총대출잔액",
    "거주지 시군구 코드", "근무지 시군구 코드",
]


def predict_full_questionnaire(df: pd.DataFrame, financial_cut: float, employment_cut: float) -> pd.Series:
    """High-fidelity, explainable classifier once axis-producing questions are available."""
    labels = pd.Series(index=df.index, dtype="string")
    labels.loc[df["파산, 개인회생 신청 여부"].eq(1)] = "T6"
    t5 = (
        labels.isna() & df["thin_filer"].eq(1) & df["총대출건수"].eq(0)
        & df["score_floor"].eq(1)
    )
    labels.loc[t5] = "T5"
    remaining = labels.isna()
    bad_f = df["financial_stress_score"].ge(financial_cut)
    bad_e = df["employment_instability_score"].ge(employment_cut)
    labels.loc[remaining & ~bad_f & ~bad_e] = "T1"
    labels.loc[remaining & bad_f & ~bad_e] = "T2"
    labels.loc[remaining & ~bad_f & bad_e] = "T3"
    labels.loc[remaining & bad_f & bad_e] = "T4"
    return labels


def evaluate_full_questionnaire(
    df: pd.DataFrame, split: pd.Series, segment_params: dict, outdir: Path
) -> dict:
    pred = predict_full_questionnaire(
        df, segment_params["financial_cut"], segment_params["employment_cut"]
    )
    test = split.eq("test")
    truth = df.loc[test, "segment"]
    test_pred = pred.loc[test]
    classes = [f"T{i}" for i in range(1, 7)]
    metrics = {
        "question_count": len(QUESTION_FIELDS),
        "test_macro_f1": float(f1_score(truth, test_pred, average="macro")),
        "test_accuracy": float(accuracy_score(truth, test_pred)),
        "classification_report": classification_report(
            truth, test_pred, labels=classes, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(truth, test_pred, labels=classes).tolist(),
        "classes": classes,
        "mismatches": int((truth != test_pred).sum()),
    }
    artifact = {
        "question_fields": QUESTION_FIELDS,
        "financial_cut": segment_params["financial_cut"],
        "employment_cut": segment_params["employment_cut"],
        "segment_names": SEGMENT_NAMES,
        "precedence": ["T6", "T5", "T1-T4 quadrant"],
    }
    joblib.dump(artifact, outdir / "full_questionnaire_classifier.pkl")
    rules = [
        "T6: 파산·개인회생 신청 여부 == 1",
        "T5: (아직 미분류) AND Thin Filer == 1 AND 총대출건수 == 0 AND 신용평점 하한(150)",
        f"재무 취약: financial_stress_score >= {segment_params['financial_cut']:.12g}",
        f"고용 불안: employment_instability_score >= {segment_params['employment_cut']:.12g}",
        "T1: 재무 안정 AND 고용 안정",
        "T2: 재무 취약 AND 고용 안정",
        "T3: 재무 안정 AND 고용 불안",
        "T4: 재무 취약 AND 고용 불안",
    ]
    (outdir / "full_questionnaire_rules.txt").write_text("\n".join(rules), encoding="utf-8")
    return metrics
