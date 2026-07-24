from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from .benchmarks import age_to_band
from .classify_service import classify
from .consumption import feedback
from .io_load import load_config
from .llm_recommend import fallback_recommendations, recommend_policies
from .rule_engine import UserInputs, find_eligible_policies

LOGGER = logging.getLogger(__name__)

_KCB_CONFIG = load_config()
KCBRecord = create_model(
    "KCBRecord",
    __config__=ConfigDict(extra="allow"),
    **{
        column: (Any, ...)
        for column in _KCB_CONFIG["columns"]["required"]
    },
)


class DiagnosePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["light", "precise"]
    user_inputs: UserInputs
    kcb_record: KCBRecord | None = None

    @model_validator(mode="after")
    def require_kcb_for_precise(self) -> "DiagnosePayload":
        if self.mode == "precise" and self.kcb_record is None:
            raise ValueError("precise 모드에는 kcb_record가 필요합니다.")
        return self


class Driver(BaseModel):
    feature: str
    value: float
    impact: float
    direction: Literal["POSITIVE", "NEGATIVE"]


class ModelResult(BaseModel):
    score: float = Field(ge=0, le=100)
    score_ci: tuple[float, float] | None = None
    type_code: Literal["V1", "V2", "V3", "S1", "S2", "S3"]
    type_probabilities: dict[str, float]
    thin_filer: bool
    key_drivers: list[Driver]
    model_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_probabilities(self) -> "ModelResult":
        expected = {"V1", "V2", "V3", "S1", "S2", "S3"}
        if set(self.type_probabilities) != expected:
            raise ValueError("type_probabilities에는 6개 유형이 정확히 필요합니다.")
        if any(value < 0 or value > 1 for value in self.type_probabilities.values()):
            raise ValueError("유형 확률은 0~1 범위여야 합니다.")
        if abs(sum(self.type_probabilities.values()) - 1.0) > 1e-6:
            raise ValueError("유형 확률 합은 1이어야 합니다.")
        expected_score = 100.0 * sum(self.type_probabilities[key] for key in ("S1", "S2", "S3"))
        if abs(self.score - expected_score) > 0.11:
            raise ValueError("score는 안정 유형 확률 합과 일치해야 합니다.")
        return self


class DiagnoseResponse(BaseModel):
    """프론트·백엔드가 OpenAPI에서 공유하는 고정 응답 계약."""

    model_config = ConfigDict(extra="forbid")

    계약버전: Literal["1.2"]
    진단모드: Literal["light", "precise"]
    진단상태: Literal["완료", "부분완료"]
    모델결과: ModelResult | None
    대분류: str | None
    유형: Literal["경제적 취약 청년", "경제적 안정 청년"] | None
    세부유형코드: Literal["V1", "V2", "V3", "S1", "S2", "S3"] | None
    유형확률: dict[str, float] | None
    유형점수: float | None
    점수설명: str | None
    안정점수: float | None
    불안정점수: float | None
    신뢰주의: bool | None
    분류상태: Literal["미사용", "완료", "사용불가"]
    분류오류코드: str | None
    분류오류: str | None
    소비피드백: dict[str, Any]
    지원가능정책: list[dict[str, Any]]
    추천정책: list[dict[str, Any]]
    추천상태: str
    추천방식: str
    추천오류: str | None


def diagnose(
    payload: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    policies: list[dict[str, Any]] | None = None,
    llm_callable: Any | None = None,
    today: date | None = None,
    credit_benchmarks: dict[int, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """백엔드가 호출하는 light/precise 공통 서비스 함수."""
    config = config or load_config()
    request = DiagnosePayload.model_validate(payload)
    user = request.user_inputs
    classification: dict[str, Any] | None = None
    classification_status = "미사용" if request.mode == "light" else "완료"
    classification_error: str | None = None
    classification_error_code: str | None = None
    kcb_record = request.kcb_record.model_dump() if request.kcb_record is not None else None

    if request.mode == "precise":
        assert kcb_record is not None
        # 정밀진단의 연령 기준은 사용자가 직접 입력한 만 나이다. KCB 연령대는
        # 공식 컬럼으로 받되, 실제 처리에는 입력 나이를 해당 KCB 구간으로 변환해 사용한다.
        kcb_record["연령대"] = age_to_band(user.나이) or user.나이
        try:
            classification = classify(kcb_record, config)
        except FileNotFoundError:
            # 분류기가 준비되지 않아도 자격 기반 정책 조회와 추천은 계속 제공한다.
            classification_status = "사용불가"
            classification_error_code = "MODEL_ARTIFACTS_MISSING"
            classification_error = "실제 KCB 데이터로 학습한 분류 아티팩트가 준비되지 않았습니다."
        except Exception:  # 분류 라이브러리·손상 아티팩트 오류를 정책 fallback과 격리한다.
            LOGGER.exception("정밀 분류를 사용할 수 없어 부분 응답으로 전환합니다.")
            classification_status = "사용불가"
            classification_error_code = "CLASSIFICATION_FAILED"
            classification_error = "정밀 분류 처리에 실패했습니다. 서버 로그에서 원인을 확인하세요."

    policy_result = find_eligible_policies(user, config=config, policies=policies, today=today)
    consumption = feedback(
        kcb_record if request.mode == "precise" else None,
        user_inputs=user.model_dump(),
        config=config,
        credit_benchmarks=credit_benchmarks,
    )
    recommendations: list[dict[str, Any]] = []
    recommendation_error: str | None = None
    recommendation_method = "없음"
    recommendation_enabled = request.mode == "precise"
    if recommendation_enabled:
        try:
            recommendations = recommend_policies(
                policy_result["groups"],
                user.model_dump(),
                classification,
                consumption,
                config=config,
                llm_callable=llm_callable,
            )
            if recommendations:
                recommendation_method = "로컬LLM"
        except Exception as exc:  # 로컬 모델 런타임 오류가 전체 진단을 중단하지 않게 한다.
            LOGGER.warning("로컬 LLM 추천 실패로 규칙 기반 추천을 사용합니다: %s", type(exc).__name__)
            recommendation_error = "LOCAL_LLM_UNAVAILABLE"
        if not recommendations and policy_result["count"] > 0:
            recommendations = fallback_recommendations(
                policy_result["groups"],
                user.model_dump(),
                classification,
                top_k=int(config.get("service", {}).get("recommendation_top_k", 5)),
            )
            recommendation_method = "규칙기반대체"
    if request.mode == "light":
        recommendation_status = "미사용"
    elif recommendations:
        recommendation_status = "완료"
    else:
        recommendation_status = "자격일치정책없음"
    if request.mode == "precise" and classification is None:
        diagnosis_status = "부분완료"
    else:
        diagnosis_status = "완료"
    model_result = None if classification is None else {
        "score": classification["안정점수"],
        "score_ci": None,
        "type_code": classification["세부유형코드"],
        "type_probabilities": classification["확률"],
        "thin_filer": bool(classification.get("thin_filer", False)),
        "key_drivers": classification.get("key_drivers", []),
        "model_version": str(classification.get("model_version") or "unknown"),
    }
    return {
        "계약버전": "1.2",
        "진단모드": request.mode,
        "진단상태": diagnosis_status,
        "모델결과": model_result,
        "대분류": classification["대분류"] if classification else None,
        "유형": classification["유형"] if classification else None,
        "세부유형코드": classification["세부유형코드"] if classification else None,
        "유형확률": classification["유형확률"] if classification else None,
        "유형점수": classification["유형점수"] if classification else None,
        "점수설명": (
            "실제 KCB 데이터로 학습한 6개 세부유형 확률을 취약·안정 두 범주로 합산한 분류 확신도입니다. 미래 연체확률이나 절대 경제점수가 아닙니다."
            if classification else None
        ),
        "안정점수": classification["안정점수"] if classification else None,
        "불안정점수": classification["불안정점수"] if classification else None,
        "신뢰주의": classification["신뢰주의"] if classification else None,
        "분류상태": classification_status,
        "분류오류코드": classification_error_code,
        "분류오류": classification_error,
        "소비피드백": consumption,
        "지원가능정책": policy_result["groups"],
        "추천정책": recommendations,
        "추천상태": recommendation_status,
        "추천방식": recommendation_method,
        "추천오류": recommendation_error,
    }
