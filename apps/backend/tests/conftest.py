import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ai_client


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_ai_server(monkeypatch):
    """ai_client가 쓰는 AsyncClient를 MockTransport 기반으로 바꿔치기한다.

    실제 ai.beceleb.org 호출 없이 relay 로직(재시도·에러 정규화·payload 구성)만 검증한다.
    """

    def _install(handler) -> httpx.AsyncClient:
        transport = httpx.MockTransport(handler)
        mock_client = httpx.AsyncClient(
            base_url=ai_client.settings.ai_server_base_url,
            transport=transport,
        )
        monkeypatch.setattr(ai_client, "_client", mock_client)
        return mock_client

    return _install
