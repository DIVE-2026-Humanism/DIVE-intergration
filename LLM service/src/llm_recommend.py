from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

TYPE_HINTS = {
    "V1": ("연체·채무조정 위험형", "신용회복·채무조정·긴급생활 우선"),
    "V2": ("상환 과부하형", "대환·서민금융 상담 우선"),
    "V3": ("소득·생활 취약형", "소득·주거·생활비 지원 우선"),
    "S1": ("상위소득 여유형", "자산형성·투자형 우선"),
    "S2": ("부채·자산 균형형", "우대금리·신용우수 혜택 우선"),
    "S3": ("무부채 건전형", "최초 자산형성(청년적금 등) 우선"),
}

TYPE_CATEGORY_PRIORITY = {
    "V1": ("복지문화", "주거", "일자리", "교육", "참여권리"),
    "V2": ("복지문화", "일자리", "주거", "교육", "참여권리"),
    "V3": ("복지문화", "주거", "일자리", "교육", "참여권리"),
    "S1": ("일자리", "교육", "참여권리", "복지문화", "주거"),
    "S2": ("일자리", "복지문화", "교육", "주거", "참여권리"),
    "S3": ("일자리", "교육", "복지문화", "참여권리", "주거"),
}
DEFAULT_CATEGORY_PRIORITY = ("일자리", "주거", "교육", "복지문화", "참여권리")
TYPE_TERMS = {
    "V1": ("신용", "채무", "금융", "상담", "복지"),
    "V2": ("대출", "금리", "금융", "상환", "일자리"),
    "V3": ("생활", "주거", "소득", "월세", "복지", "일자리"),
    "S1": ("창업", "자산", "교육", "일자리"),
    "S2": ("금리", "자산", "교육", "일자리"),
    "S3": ("저축", "자산", "교육", "일자리"),
}
_LLM_SLOT = threading.BoundedSemaphore(value=1)
_LLM_CIRCUIT_LOCK = threading.Lock()
_LLM_UNAVAILABLE_UNTIL = 0.0


def _classification_type_code(classification: dict[str, Any] | None) -> str:
    """응답 계약의 내부 세부유형 코드를 추천 우선순위에 사용한다."""
    if not classification:
        return ""
    code = str(classification.get("세부유형코드") or "")
    if code in TYPE_HINTS:
        return code
    legacy = str(classification.get("유형") or "")
    return legacy if legacy in TYPE_HINTS else ""


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plcyNo: str
    순위: int = Field(ge=1)
    추천이유: str = Field(min_length=1, max_length=500)
    매칭포인트: str = Field(min_length=1, max_length=300)
    주의: str = Field(min_length=1, max_length=300)


class RecommendationList(RootModel[list[Recommendation]]):
    pass


def _http_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"로컬 LLM HTTP 오류({exc.code}): {detail}") from exc
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise RuntimeError(f"로컬 LLM 호출 실패: {exc}") from exc


def resolve_local_llm(config: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    section = config.get("local_llm", {})
    base_url = str(os.getenv(str(section.get("base_url_env", "OLLAMA_BASE_URL"))) or section.get("base_url") or "").rstrip("/")
    parsed = urlparse(base_url)
    allowed_hosts = {str(host) for host in section.get("allowed_hosts", ["127.0.0.1", "localhost", "::1"])}
    if parsed.scheme != "http" or parsed.hostname not in allowed_hosts:
        raise ValueError(f"Ollama 주소는 허용된 내부 HTTP 호스트만 사용할 수 있습니다: {sorted(allowed_hosts)}")
    model = os.getenv(str(section.get("model_env", "OLLAMA_MODEL"))) or section.get("model")
    if not model:
        raise RuntimeError("local_llm.model이 설정되지 않았습니다.")
    return base_url, str(model), section


def call_local_llm(system: str, user: str, config: dict[str, Any]) -> str:
    """허용된 로컬·컨테이너 Ollama만 호출하고 구조화 JSON 응답을 받는다."""
    global _LLM_UNAVAILABLE_UNTIL
    base_url, model, section = resolve_local_llm(config)
    timeout = int(section.get("timeout_seconds", 30))
    with _LLM_CIRCUIT_LOCK:
        if time.monotonic() < _LLM_UNAVAILABLE_UNTIL:
            raise RuntimeError("로컬 LLM 장애 대기시간 중이어서 규칙 기반 추천으로 전환합니다.")
    if not _LLM_SLOT.acquire(timeout=float(section.get("queue_timeout_seconds", 1))):
        raise RuntimeError("로컬 LLM이 다른 요청을 처리 중이어서 규칙 기반 추천으로 전환합니다.")
    try:
        try:
            response = _http_json(
                f"{base_url}/api/chat",
                {
                    "model": model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "stream": False,
                    "think": False,
                    "format": RecommendationList.model_json_schema(),
                    "options": {"temperature": 0, "num_ctx": int(section.get("context_length", 16384))},
                    "keep_alive": section.get("keep_alive", "10m"),
                },
                timeout,
            )
        except RuntimeError:
            with _LLM_CIRCUIT_LOCK:
                _LLM_UNAVAILABLE_UNTIL = time.monotonic() + float(section.get("failure_cooldown_seconds", 30))
            raise
        with _LLM_CIRCUIT_LOCK:
            _LLM_UNAVAILABLE_UNTIL = 0.0
    finally:
        _LLM_SLOT.release()
    try:
        return str(response["message"]["content"])
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Ollama 응답 계약이 올바르지 않습니다: {response}") from exc


def _json_value(text: str) -> Any:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        start = clean.find("[")
        end = clean.rfind("]")
        if start >= 0 and end > start:
            return json.loads(clean[start : end + 1])
        raise


def validate_recommendations(text: str, candidate_ids: set[str], *, top_k: int = 5) -> list[dict[str, Any]]:
    payload = _json_value(text)
    if isinstance(payload, dict):
        payload = payload.get("추천정책", payload.get("recommendations"))
    if not isinstance(payload, list):
        raise ValueError("LLM 출력은 JSON 배열이어야 합니다.")
    valid: list[Recommendation] = []
    seen: set[str] = set()
    for item in payload:
        try:
            recommendation = Recommendation.model_validate(item)
        except ValidationError:
            continue
        if recommendation.plcyNo not in candidate_ids or recommendation.plcyNo in seen:
            continue
        seen.add(recommendation.plcyNo)
        valid.append(recommendation)
    valid.sort(key=lambda item: item.순위)
    return [item.model_dump() for item in valid[:top_k]]


def _flatten_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for policy in group.get("정책", []):
            code = str(policy.get("plcyNo") or "")
            if code and code not in seen:
                seen.add(code)
                output.append(policy)
    return output


def _categories(policy: dict[str, Any]) -> list[str]:
    value = policy.get("대분류")
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)] if value else []


def _normalized_name(policy: dict[str, Any]) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(policy.get("plcyNm") or "")).lower()


def shortlist_candidates(
    policy_groups: list[dict[str, Any]],
    classification: dict[str, Any] | None,
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """LLM 호출 전에 확정 PASS 정책을 점수화하고 정책명 중복을 제거한다."""
    candidates = [item for item in _flatten_groups(policy_groups) if item.get("자격판정", "PASS") == "PASS"]
    type_code = _classification_type_code(classification)
    priority = TYPE_CATEGORY_PRIORITY.get(type_code, DEFAULT_CATEGORY_PRIORITY)
    priority_index = {category: index for index, category in enumerate(priority)}
    terms = TYPE_TERMS.get(type_code, ())

    def score(policy: dict[str, Any]) -> tuple[int, int, str, str]:
        categories = _categories(policy)
        category_rank = min((priority_index.get(value, len(priority)) for value in categories), default=len(priority))
        searchable = " ".join(
            str(policy.get(key) or "")
            for key in ("plcyNm", "중분류", "키워드", "설명", "지원내용")
        )
        term_hits = sum(term in searchable for term in terms)
        return category_rank, -term_hits, _normalized_name(policy), str(policy.get("plcyNo") or "")

    unique: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for policy in sorted(candidates, key=score):
        name = _normalized_name(policy) or str(policy.get("plcyNo") or "")
        if name in seen_names:
            continue
        seen_names.add(name)
        unique.append(policy)

    limit = max(1, int(limit))
    quota = max(1, limit // len(priority))
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for category in priority:
        category_items = [policy for policy in unique if category in _categories(policy)]
        for policy in category_items[:quota]:
            policy_id = str(policy.get("plcyNo") or "")
            if policy_id not in selected_ids:
                selected.append(policy)
                selected_ids.add(policy_id)
    for policy in unique:
        if len(selected) >= limit:
            break
        policy_id = str(policy.get("plcyNo") or "")
        if policy_id not in selected_ids:
            selected.append(policy)
            selected_ids.add(policy_id)
    return selected[:limit]


def attach_recommendation_evidence(
    recommendations: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """LLM이 만들 수 없는 정책 원문 근거를 서버가 후보 데이터에서 강제로 결합한다."""
    by_id = {str(item.get("plcyNo")): item for item in candidates}
    output: list[dict[str, Any]] = []
    for rank, recommendation in enumerate(recommendations, start=1):
        policy = by_id.get(str(recommendation.get("plcyNo")))
        if policy is None:
            continue
        output.append(
            {
                **recommendation,
                "순위": rank,
                "정책명": policy.get("plcyNm"),
                "자격판정": policy.get("자격판정", "PASS"),
                "판정근거": policy.get("판정근거", []),
                "대분류": _categories(policy),
                "정책키워드": policy.get("키워드", []),
                "출처URL": policy.get("참고URL") or policy.get("신청URL"),
            }
        )
    return output


def fallback_recommendations(
    policy_groups: list[dict[str, Any]],
    user_profile: dict[str, Any],
    classification: dict[str, Any] | None,
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """LLM 없이도 자격조건을 통과한 실제 정책만 결정적으로 추천한다."""
    candidates = shortlist_candidates(policy_groups, classification, limit=top_k)
    if not candidates:
        return []
    type_code = _classification_type_code(classification)
    category_priority = TYPE_CATEGORY_PRIORITY.get(type_code, DEFAULT_CATEGORY_PRIORITY)
    priority_index = {category: index for index, category in enumerate(category_priority)}

    def ranking(item: tuple[int, dict[str, Any]]) -> tuple[int, int, str]:
        original_index, policy = item
        categories = _categories(policy)
        category_rank = min(
            (priority_index.get(category, len(priority_index)) for category in categories),
            default=len(priority_index),
        )
        return category_rank, original_index, str(policy.get("plcyNo") or "")

    ordered = [policy for _, policy in sorted(enumerate(candidates), key=ranking)]
    type_name, type_priority = TYPE_HINTS.get(type_code, ("미분류", "사용자 자격조건 직접 일치 우선"))
    profile_points = [
        key for key in ("나이", "사는곳", "연소득", "직업군", "학력")
        if user_profile.get(key) not in (None, "")
    ]
    matched_profile = "·".join(profile_points) if profile_points else "구조화 자격"
    recommendations: list[dict[str, Any]] = []
    for rank, policy in enumerate(ordered[: max(1, int(top_k))], start=1):
        categories = _categories(policy)
        category_text = categories[0] if categories else "청년정책"
        has_free_text = any(policy.get(key) for key in ("소득기타", "추가자격", "제외대상"))
        if classification:
            reason = f"{type_name}의 지원 우선방향({type_priority})을 반영한 {category_text} 정책입니다."
        else:
            reason = f"사용자 자격조건을 통과한 {category_text} 정책입니다."
        recommendations.append(
            {
                "plcyNo": str(policy["plcyNo"]),
                "순위": rank,
                "추천이유": reason,
                "매칭포인트": f"{matched_profile} 조건 일치",
                "주의": "추가자격·제외대상과 제출서류 확인 필요" if has_free_text else "신청 전 최신 공고와 제출서류 확인 필요",
            }
        )
    return attach_recommendation_evidence(recommendations, ordered)


def _compact_candidate(policy: dict[str, Any]) -> dict[str, Any]:
    """추천에 필요 없는 URL·중복 필드를 빼서 로컬 컨텍스트를 절약한다."""
    def text(value: Any, limit: int) -> str:
        clean = re.sub(r"\s+", " ", str(value or "")).strip()
        return clean if len(clean) <= limit else clean[: limit - 1] + "…"

    return {
        "plcyNo": policy.get("plcyNo"),
        "정책명": text(policy.get("plcyNm"), 120),
        "대분류": policy.get("대분류"),
        "중분류": text(policy.get("중분류"), 100),
        "설명": text(policy.get("설명"), 500),
        "지원내용": text(policy.get("지원내용"), 800),
        "소득기타": text(policy.get("소득기타"), 300),
        "추가자격": text(policy.get("추가자격"), 400),
        "제외대상": text(policy.get("제외대상"), 400),
        "신청종료일": policy.get("신청종료일"),
        "자격판정": policy.get("자격판정", "PASS"),
        "판정근거": policy.get("판정근거", []),
    }


def build_prompts(
    candidates: list[dict[str, Any]],
    user_profile: dict[str, Any],
    classification: dict[str, Any] | None,
    consumption: dict[str, Any],
    top_k: int,
) -> tuple[str, str]:
    type_code = _classification_type_code(classification) or None
    type_name, priority = TYPE_HINTS.get(type_code, ("미분류", "사용자 자격과 지원 내용의 직접 일치 우선"))
    system = f"""너는 부산 청년정책 추천 어시스턴트다. 아래 후보 정책 안에서만 추천하라.
- 목록에 없는 정책, URL, 금액을 만들지 마라.
- 자유텍스트 요건(추가자격, 제외대상, 기타소득)을 읽고 명백히 부적합한 후보는 제외하라.
- 불확실하면 주의에 '서류 확인 필요'라고 표시하라.
- 사용자 유형 {type_code or '없음'} {type_name}의 우선순위({priority})를 고려하라.
- 모델이 준 점수를 그대로 참고하고 점수나 위험확률을 새로 만들지 마라.
- 출력은 설명 없이 JSON 배열만 사용하라."""
    safe_profile = {key: user_profile.get(key) for key in ("직업군", "학력") if user_profile.get(key)}
    safe_classification = None if not classification else {
        key: classification.get(key)
        for key in ("유형", "세부유형코드", "대분류", "유형점수", "안정점수", "신뢰주의")
    }
    safe_consumption = {
        "비교": [
            {key: item.get(key) for key in ("지표", "격차%", "기준설명") if item.get(key) is not None}
            for item in consumption.get("items", [])
        ],
        "주거지원_우선": bool(consumption.get("주거지원_우선")),
    }
    summary = {
        "추천맥락": safe_profile,
        "분류": safe_classification,
        "소비분석": safe_consumption,
        "후보정책": [_compact_candidate(policy) for policy in candidates],
    }
    user = json.dumps(summary, ensure_ascii=False, default=str) + f"\n적합한 상위 {top_k}개를 plcyNo, 순위, 추천이유, 매칭포인트, 주의 필드의 JSON 배열로 반환하라."
    return system, user


def _recommend_batch(
    candidates: list[dict[str, Any]],
    user_profile: dict[str, Any],
    classification: dict[str, Any] | None,
    consumption: dict[str, Any],
    *,
    config: dict[str, Any],
    llm_callable: Callable[[str, str], str],
    top_k: int,
) -> list[dict[str, Any]]:
    system, user = build_prompts(candidates, user_profile, classification, consumption, top_k)
    attempts = int(config.get("local_llm", {}).get("max_retries", 1)) + 1
    candidate_ids = {str(policy["plcyNo"]) for policy in candidates}
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            response = llm_callable(system, user)
            return validate_recommendations(response, candidate_ids, top_k=top_k)
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            user += "\n이전 응답이 계약을 위반했다. 후보 plcyNo만 사용해 올바른 JSON 배열로 다시 응답하라."
    raise RuntimeError(f"로컬 LLM 추천 JSON 검증 실패: {last_error}")


def recommend_policies(
    policy_groups: list[dict[str, Any]],
    user_profile: dict[str, Any],
    classification: dict[str, Any] | None,
    consumption: dict[str, Any],
    *,
    config: dict[str, Any],
    llm_callable: Callable[[str, str], str] | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    top_k = int(top_k or config.get("service", {}).get("recommendation_top_k", 5))
    shortlist_size = int(config.get("local_llm", {}).get("shortlist_size", 12))
    candidates = shortlist_candidates(policy_groups, classification, limit=max(top_k, shortlist_size))
    if not candidates:
        return []
    if llm_callable is None:
        env_enabled = os.getenv("DIVE_LLM_ENABLED")
        enabled = config.get("local_llm", {}).get("enabled", True)
        if env_enabled is not None:
            enabled = env_enabled.strip().lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return []
        llm_callable = lambda system_text, user_text: call_local_llm(system_text, user_text, config)
    recommendations = _recommend_batch(
        candidates, user_profile, classification, consumption,
        config=config, llm_callable=llm_callable, top_k=top_k,
    )
    return attach_recommendation_evidence(recommendations, candidates)
