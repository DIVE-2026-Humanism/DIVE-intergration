from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import app


def payload() -> dict:
    return {
        "mode": "light",
        "user_inputs": {
            "성별": "여",
            "결혼여부": "미혼",
            "연소득": 30_000_000,
            "직업군": "재직자",
            "학력": "대학 졸업",
            "특화": [],
            "사는곳": "중구",
            "나이": 27,
        },
    }


def response_payload() -> dict:
    return {
        "계약버전": "1.2",
        "진단모드": "light",
        "진단상태": "완료",
        "모델결과": None,
        "대분류": None,
        "유형": None,
        "세부유형코드": None,
        "유형확률": None,
        "유형점수": None,
        "점수설명": None,
        "안정점수": None,
        "불안정점수": None,
        "신뢰주의": None,
        "분류상태": "미사용",
        "분류오류코드": None,
        "분류오류": None,
        "소비피드백": {},
        "지원가능정책": [],
        "추천정책": [],
        "추천상태": "미사용",
        "추천방식": "없음",
        "추천오류": None,
    }


def test_diagnose_api_accepts_contract(monkeypatch) -> None:
    monkeypatch.setenv("DIVE_AUTO_INGEST", "false")
    monkeypatch.setattr("src.api.diagnose", lambda request: response_payload())
    with TestClient(app) as client:
        response = client.post("/v1/diagnose", json=payload())
    assert response.status_code == 200
    assert response.json()["계약버전"] == "1.2"


def test_diagnose_rejects_missing_age(monkeypatch) -> None:
    monkeypatch.setenv("DIVE_AUTO_INGEST", "false")
    request = payload()
    request["user_inputs"].pop("나이")
    with TestClient(app) as client:
        response = client.post("/v1/diagnose", json=request)
    assert response.status_code == 422


def test_default_cors_allows_frontend_post(monkeypatch) -> None:
    monkeypatch.setenv("DIVE_AUTO_INGEST", "false")
    with TestClient(app) as client:
        response = client.options(
            "/v1/diagnose",
            headers={
                "Origin": "https://frontend.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "Content-Type" in response.headers["access-control-allow-headers"]


def test_integration_metadata_publishes_options_and_kcb_contract(monkeypatch) -> None:
    monkeypatch.setenv("DIVE_AUTO_INGEST", "false")
    with TestClient(app) as client:
        response = client.get("/v1/meta")
    assert response.status_code == 200
    result = response.json()
    assert result["contract_version"] == "1.2"
    assert result["sample_light_request"]["mode"] == "light"
    assert "추정가구원수" in result["precise_input"]["required_kcb_columns"]
    assert result["user_input_options"]["나이"].startswith("필수")


def test_readiness_checks_postgres_and_ollama(monkeypatch) -> None:
    monkeypatch.setenv("DIVE_AUTO_INGEST", "false")
    monkeypatch.setattr("src.api.database_is_ready", lambda config: True)
    monkeypatch.setattr("src.api._ollama_ready", lambda config: True)
    monkeypatch.setattr("src.api.classification_capability", lambda config: {"available": True})
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["components"] == {
        "postgresql": True,
        "ollama_model": True,
        "classification_model": True,
    }
    assert response.json()["capabilities"]["light_rule_policy_list"] is True
    assert response.json()["capabilities"]["precise_llm_recommendation"] is True


def test_readiness_is_degraded_but_usable_with_fallbacks(monkeypatch) -> None:
    monkeypatch.setenv("DIVE_AUTO_INGEST", "false")
    monkeypatch.setattr("src.api.database_is_ready", lambda config: True)
    monkeypatch.setattr("src.api._ollama_ready", lambda config: False)
    monkeypatch.setattr("src.api.classification_capability", lambda config: {"available": False})
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["capabilities"]["precise_classification"] is False
    assert response.json()["capabilities"]["rule_fallback_recommendation"] is True


def test_readiness_fails_when_postgresql_is_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("DIVE_AUTO_INGEST", "false")
    monkeypatch.setattr("src.api.database_is_ready", lambda config: False)
    monkeypatch.setattr("src.api._ollama_ready", lambda config: False)
    monkeypatch.setattr("src.api.classification_capability", lambda config: {"available": False})
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
