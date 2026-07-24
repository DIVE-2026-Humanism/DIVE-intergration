"""ai-server(https://ai.beceleb.org) relay 클라이언트.

진단·6유형분류·정책매칭·LLM설명은 전부 ai-server가 처리한다. 이 모듈은
그 응답을 그대로 가져오는 얇은 relay다 — 여기서 필드를 재가공하거나
보정하지 않는다 (AGENTS.md: "모델 출력을 앱에서 보정·반올림해 의미를
바꾸지 않는다").

네트워크 에러·502·503은 API명세_v0.1.md §5 규칙대로 1회만 재시도한다.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.schemas.common import AppError

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.ai_server_base_url,
            timeout=settings.ai_server_timeout_seconds,
        )
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    client = get_client()
    last_error: Exception | None = None

    for attempt in (1, 2):
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            last_error = exc
            if attempt == 2:
                raise AppError(
                    "AI_UPSTREAM_UNREACHABLE", "AI 서버 연결 장애", 502
                ) from exc
            continue

        if response.status_code in (502, 503) and attempt == 1:
            continue

        return response

    # 이론상 도달하지 않지만, 정적 분석·안전망 목적으로 남긴다.
    raise AppError("AI_UPSTREAM_UNREACHABLE", "AI 서버 연결 장애", 502) from last_error


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 422:
        raise AppError("INVALID_REQUEST", "요청 형식이 올바르지 않습니다.", 422)
    if response.status_code >= 500:
        code = f"AI_UPSTREAM_{response.status_code}"
        message = "AI 서버 연결 장애" if response.status_code == 502 else "AI 서버 준비 실패"
        raise AppError(code, message, response.status_code)
    response.raise_for_status()


async def get_health() -> dict:
    response = await _request_with_retry("GET", "/health/live")
    _raise_for_status(response)
    return response.json()


async def get_meta() -> dict:
    response = await _request_with_retry("GET", "/v1/meta")
    _raise_for_status(response)
    return response.json()


async def diagnose(payload: dict) -> dict:
    response = await _request_with_retry("POST", "/v1/diagnose", json=payload)
    _raise_for_status(response)
    return response.json()
