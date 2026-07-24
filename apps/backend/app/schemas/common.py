"""전 엔드포인트 공통 에러 포맷."""

from typing import Optional

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    trace_id: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    """서비스 계층에서 던지는 에러. main.py 의 핸들러가 잡는다."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        field: Optional[str] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field
        super().__init__(message)
