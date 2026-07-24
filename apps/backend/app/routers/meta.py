"""폼 입력 옵션 relay.

ai-server `/v1/meta`가 단일 진실이다. 직업군 코드북 등이 미확정이라
프론트에 하드코딩된 enum을 내려주지 않는다 — 그대로 프록시한다.
"""

from fastapi import APIRouter

from app.services import ai_client

router = APIRouter(tags=["meta"])


@router.get("/meta")
async def get_meta() -> dict:
    return await ai_client.get_meta()
