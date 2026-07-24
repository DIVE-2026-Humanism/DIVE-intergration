"""진단 API 요청 스키마. 프론트와의 계약 (API명세_v0.1.md §3).

응답은 여기서 타입화하지 않는다 — ai-server 응답(계약버전 1.2)을 그대로
passthrough하며, 앱이 필드를 걸러내거나 보정하지 않는다.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

DiagnosisMode = Literal["light", "precise"]


class UserInputs(BaseModel):
    """공통 사용자 입력 8개 필드 (API명세_v0.1.md §3-1)."""

    성별: str
    결혼여부: str
    연소득: int = Field(ge=0, description="원(KRW) 단위")
    직업군: str = Field(description="코드북 미확정 — enum 고정하지 않음")
    학력: str
    특화: list[str] = Field(default_factory=list, description="취약계층 복수선택")
    사는곳: str
    나이: int = Field(ge=0, description="필수 만 나이. KCB 연령대보다 우선")


class DiagnoseRequest(BaseModel):
    mode: DiagnosisMode
    user_inputs: UserInputs
    sampleId: Optional[str] = Field(
        default=None, description="정밀 진단용 KCB 샘플 식별자. 생략 시 기본 샘플 사용"
    )
