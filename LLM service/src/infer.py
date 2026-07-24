from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool

from .features import MODEL_FEATURES
from .io_load import ROOT
from .labeling import LABEL_NAMES
from .train import prepare_full


DATA_WARNINGS = {
    "MISSING_KEY": "핵심 금융정보 일부가 없어 모델 결과 해석에 주의가 필요합니다.",
    "THIN": "금융거래 이력이 부족해 신용정보가 충분하지 않습니다.",
    "MIXED": "취약 신호와 안정 신호가 함께 관측되어 모델 결과 해석에 주의가 필요합니다.",
    "DEBT_UNOBS": "대출건수는 있지만 제공된 대출잔액 합계가 0이므로 실제 잔액을 확인해야 합니다.",
    "NO_MATCH": "규칙상 뚜렷한 유형 신호가 부족하여 학습된 모델 결과로 분류했습니다.",
}


def _percentile_text(percentile: float) -> str:
    if percentile >= 0.8:
        return "상위 20% 구간"
    if percentile >= 0.5:
        return "중앙값 이상 구간"
    if percentile <= 0.2:
        return "하위 20% 구간"
    return "중간 구간"


def _explanation(feature: str, row: pd.Series, percentile: float) -> str | None:
    value = row.get(feature)
    if pd.isna(value):
        return None
    position = _percentile_text(percentile)
    if feature == "REL_DEBT":
        return f"제공된 3개 대출범주 잔액 합계가 동일 연령 채무자 평균의 {value:.2f}배({position})"
    if feature == "DSR_PROXY":
        return f"최근 12개월 상환액이 추정연소득의 {value:.1%}({position})"
    if feature == "REL_INC":
        return f"추정연소득이 동일 연령 평균의 {value:.2f}배({position})"
    if feature == "INC_CHG":
        return f"2년 전 대비 추정연소득 변화가 {value:+.1%}({position})"
    if feature == "CARD_CONSUME_RATIO":
        return f"신용·체크카드 소비 합계가 추정연소득의 {value:.1%}({position})"
    if feature == "DEBT_SUM":
        return f"제공된 3개 대출범주 잔액 합계가 {value:,.0f}천원({position})"
    if feature == "DELQ_LEVEL":
        names = {0: "연체 없음", 1: "경미 연체", 2: "중간 연체", 3: "중대 연체"}
        return f"관측 연체 상태가 {names.get(int(value), '확인 필요')} 단계"
    if feature == "신용평점":
        return f"신용평점이 {value:.0f}점({position})"
    if feature == "총대출건수":
        return f"관측 총대출건수가 {value:.0f}건({position})"
    if feature == "최근 12개월 현금서비스이용금액":
        return f"최근 12개월 현금서비스 이용금액이 {value:,.0f}천원({position})"
    if feature == "BUFFER":
        return "자가·주담대 보유자 순자산이 자가군 중앙값 이상" if value == 1 else "자가·주담대 보유자 순자산이 자가군 중앙값 미만"
    if feature == "추정 연소득":
        return f"추정연소득이 {value:,.0f}천원({position})"
    return None


def prediction_record(
    code: str,
    reasons: list[str],
    *,
    data_warning_code: str | None = None,
) -> dict[str, Any]:
    """규칙 레이블과 무관하게 운영 추론 결과를 항상 6유형으로 만든다."""
    if code not in LABEL_NAMES:
        raise ValueError(f"지원하지 않는 모델 클래스입니다: {code}")
    warning = DATA_WARNINGS.get(str(data_warning_code)) if data_warning_code else None
    return {
        "판정": "모델분류",
        "대분류": "경제적 취약 청년" if code.startswith("V") else "경제적 안정 청년",
        "유형": LABEL_NAMES[code],
        "핵심근거": reasons,
        "신뢰주의": warning is not None,
        "데이터주의사항": warning,
    }


def infer_pipeline(raw: pd.DataFrame, config: dict[str, Any]) -> Path:
    artifacts = ROOT / config["project"]["artifacts_dir"]
    model_path = artifacts / "model.cbm"
    if not model_path.exists():
        raise FileNotFoundError(f"Trained model missing: {model_path}; run --stage train first")
    model = CatBoostClassifier()
    model.load_model(str(model_path))
    _, features, _, labels = prepare_full(raw, config)
    x = features[MODEL_FEATURES]
    predicted = np.asarray(model.predict(x)).reshape(-1).astype(str)
    shap_values = np.asarray(model.get_feature_importance(Pool(x), type="ShapValues"))
    if shap_values.ndim != 3:
        raise RuntimeError(f"Unexpected multiclass SHAP shape: {shap_values.shape}")
    classes = [str(value) for value in model.classes_]
    class_index = {value: index for index, value in enumerate(classes)}
    percentile_ranks = {feature: features[feature].rank(pct=True, method="average") for feature in MODEL_FEATURES}
    output_path = artifacts / "predictions.jsonl"
    with output_path.open("w", encoding="utf-8") as handle:
        for position, (index, row) in enumerate(features.iterrows()):
            code = predicted[position]
            contributions = shap_values[position, class_index[code], :-1]
            ordered = np.argsort(np.abs(contributions))[::-1]
            reasons: list[str] = []
            for feature_index in ordered:
                feature = MODEL_FEATURES[int(feature_index)]
                sentence = _explanation(feature, row, float(percentile_ranks[feature].loc[index]) if pd.notna(percentile_ranks[feature].loc[index]) else 0.5)
                if sentence and sentence not in reasons:
                    reasons.append(sentence)
                if len(reasons) == 3:
                    break
            warning_code = labels.loc[index, "HOLDOUT_REASON"]
            record = prediction_record(
                code,
                reasons,
                data_warning_code=None if pd.isna(warning_code) else str(warning_code),
            )
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return output_path
