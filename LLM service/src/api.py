from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .classify_service import classification_capability
from .io_load import load_config
from .llm_recommend import resolve_local_llm
from .policy_db.ingest import database_is_ready, ingest
from .rule_engine import GU_CODE, JOB_MAP, SCHOOL_MAP, SBIZ
from .service import DiagnosePayload, DiagnoseResponse, diagnose


def _enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _ollama_ready(config: dict[str, Any]) -> bool:
    try:
        base_url, model, section = resolve_local_llm(config)
        with urllib.request.urlopen(
            f"{base_url}/api/tags",
            timeout=min(5, int(section.get("timeout_seconds", 5))),
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        names = {
            str(item.get("name") or item.get("model") or "")
            for item in payload.get("models", [])
            if isinstance(item, dict)
        }
        return model in names
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError):
        return False


@asynccontextmanager
async def lifespan(_: FastAPI):
    if _enabled("DIVE_AUTO_INGEST", True):
        ingest(load_config())
    yield


app = FastAPI(
    title="DIVE TypePredict AI API",
    version="0.4.0",
    lifespan=lifespan,
)

cors_origins = [item.strip() for item in os.getenv("DIVE_CORS_ORIGINS", "*").split(",") if item.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "DIVE TypePredict AI API", "docs": "/docs"}


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness(response: Response) -> dict[str, Any]:
    config = load_config()
    llm_enabled = _enabled("DIVE_LLM_ENABLED", bool(config.get("local_llm", {}).get("enabled", True)))
    components = {
        "postgresql": database_is_ready(config),
        "ollama_model": _ollama_ready(config) if llm_enabled else None,
        "classification_model": classification_capability(config)["available"],
    }
    # PostgreSQL은 정책 조회의 필수 의존성이다. LLM과 분류기는 명시적 fallback이 있어
    # 준비되지 않아도 라이트 진단 서비스 자체는 받을 수 있다.
    service_ready = components["postgresql"]
    fully_ready = all(value is not False for value in components.values())
    if not service_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if fully_ready else "degraded" if service_ready else "not_ready",
        "components": components,
        "capabilities": {
            "light_diagnosis": service_ready,
            "light_rule_policy_list": service_ready,
            "precise_classification": service_ready and components["classification_model"],
            "llm_recommendation": service_ready and components["ollama_model"] is True,
            "rule_fallback_recommendation": service_ready,
            "precise_llm_recommendation": service_ready and components["ollama_model"] is True,
            "precise_rule_fallback": service_ready,
        },
    }


@app.get("/v1/meta")
def integration_metadata() -> dict[str, Any]:
    """프론트·백엔드가 별도 문서 없이 입력 계약을 확인하는 공개 메타데이터."""
    config = load_config()
    return {
        "api_version": app.version,
        "contract_version": "1.2",
        "diagnose_endpoint": "/v1/diagnose",
        "user_input_options": {
            "성별": ["남", "여"],
            "결혼여부": ["기혼", "미혼"],
            "직업군": list(JOB_MAP),
            "학력": list(SCHOOL_MAP),
            "특화": [item for item in SBIZ if item != "여성"],
            "사는곳": list(GU_CODE),
            "나이": "필수, 만 나이 0~120",
            "연소득": "필수, 원 단위 0 이상",
        },
        "precise_input": {
            "required_kcb_columns": config["columns"]["required"],
            "additional_columns_allowed": True,
            "age_rule": "user_inputs.나이를 KCB 연령대로 변환해 사용",
            "household_rule": "모든 가구원수를 정밀진단하며 추정가구원수=1이면 맞춤 피드백 제공",
        },
        "sample_light_request": {
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
        },
    }
@app.post("/v1/diagnose", response_model=DiagnoseResponse)
def diagnose_endpoint(payload: DiagnosePayload) -> dict[str, Any]:
    try:
        return diagnose(payload.model_dump())
    except (psycopg.Error, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
