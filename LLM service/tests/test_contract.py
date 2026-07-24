from __future__ import annotations

import pandas as pd
import pytest

from src.io_load import SchemaContractError, load_config, validate_schema
from src.api import app
from src.service import DiagnoseResponse


def test_schema_contract_fails_loudly_on_missing_column() -> None:
    config = load_config()
    frame = pd.DataFrame(columns=config["columns"]["required"][:-1])
    with pytest.raises(SchemaContractError, match="Missing required columns"):
        validate_schema(frame, config["columns"]["required"])


def test_current_kcb_contract_has_43_required_columns() -> None:
    columns = load_config()["columns"]
    required = columns["required"]
    assert len(required) == 43
    assert len(required) == len(set(required))
    assert required[-1] == "추정가구원수"


def test_http_response_contract_is_published_in_openapi() -> None:
    openapi = app.openapi()
    operation = openapi["paths"]["/v1/diagnose"]["post"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("/DiagnoseResponse")
    assert "ModelResult" in openapi["components"]["schemas"]
    assert len(openapi["components"]["schemas"]["KCBRecord"]["required"]) == 43
    assert "증빙연소득" in openapi["components"]["schemas"]["KCBRecord"]["properties"]
    assert "나이" in openapi["components"]["schemas"]["UserInputs"]["required"]


def test_unavailable_precise_response_contract_is_explicit() -> None:
    response = DiagnoseResponse.model_validate(
        {
            "계약버전": "1.2", "진단모드": "precise", "진단상태": "부분완료",
            "모델결과": None, "대분류": None, "유형": None,
            "세부유형코드": None, "유형확률": None, "유형점수": None, "점수설명": None,
            "안정점수": None, "불안정점수": None, "신뢰주의": None,
            "분류상태": "사용불가", "분류오류코드": "MODEL_ARTIFACTS_MISSING",
            "분류오류": "실제 데이터 학습 필요", "소비피드백": {},
            "지원가능정책": [],
            "추천정책": [], "추천상태": "자격일치정책없음", "추천방식": "없음",
            "추천오류": None,
        }
    )
    assert response.진단상태 == "부분완료"
    assert response.모델결과 is None
