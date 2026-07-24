from __future__ import annotations

import json

from src.infer import prediction_record


def test_rule_holdout_is_still_returned_as_model_classification() -> None:
    result = prediction_record(
        "S2",
        ["상환부담이 동일 연령대보다 낮음"],
        data_warning_code="DEBT_UNOBS",
    )
    assert result["판정"] == "모델분류"
    assert result["유형"] == "S2 부채·자산 균형 관리형"
    assert result["신뢰주의"] is True
    assert "대출잔액" in result["데이터주의사항"]
    assert "유보" not in json.dumps(result, ensure_ascii=False)


def test_regular_model_classification_has_no_data_warning() -> None:
    result = prediction_record("V3", [], data_warning_code=None)
    assert result["유형"] == "V3 소득·생활 취약형"
    assert result["신뢰주의"] is False
    assert result["데이터주의사항"] is None
