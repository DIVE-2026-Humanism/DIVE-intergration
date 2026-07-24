import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import diagnosis, meta
from app.schemas.common import AppError
from app.services import ai_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await ai_client.aclose()


app = FastAPI(
    title=settings.app_name,
    description="부산 청년 1인가구 경제안정성 진단 · 정책 추천 API (ai-server relay)",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "field": exc.field,
                "trace_id": uuid.uuid4().hex[:12],
            }
        },
    )


@app.exception_handler(RequestValidationError)
def validation_handler(request: Request, exc: RequestValidationError):
    """FastAPI 기본 422 형식을 공통 에러 포맷으로 통일. (API명세_v0.1.md §5: 입력값 오류 = 422)"""
    first = exc.errors()[0] if exc.errors() else {}
    loc = first.get("loc", [])
    field = str(loc[-1]) if loc else None
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": first.get("msg", "요청 형식이 올바르지 않습니다."),
                "field": field,
                "trace_id": uuid.uuid4().hex[:12],
            }
        },
    )


@app.get("/api/health", tags=["meta"])
async def health():
    try:
        await ai_client.get_health()
        ai_status = "ok"
    except AppError:
        ai_status = "unreachable"
    return {"backend": "ok", "ai_server": ai_status}


for r in (diagnosis.router, meta.router):
    app.include_router(r, prefix=settings.api_prefix)
