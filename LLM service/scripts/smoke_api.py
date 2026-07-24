#!/usr/bin/env python3
"""배포된 DIVE AI API의 라이트/정밀 계약을 비파괴적으로 확인한다."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


LIGHT_PAYLOAD = {
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


def request_json(url: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "DIVE-TypePredict-Smoke/1.0",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"API 호출 실패: {exc}") from exc


def validate_response(result: dict[str, Any], expected_mode: str) -> None:
    required = {
        "계약버전", "진단모드", "진단상태", "모델결과", "분류상태",
        "유형", "세부유형코드", "유형점수",
        "지원가능정책", "추천정책", "추천상태",
    }
    missing = sorted(required - set(result))
    if missing:
        raise RuntimeError(f"응답 계약 필드 누락: {missing}")
    if result["계약버전"] != "1.2" or result["진단모드"] != expected_mode:
        raise RuntimeError("응답 계약버전 또는 진단모드가 요청과 다릅니다.")
    for item in result["추천정책"]:
        if item.get("자격판정") != "PASS":
            raise RuntimeError(f"확정 PASS가 아닌 정책이 추천되었습니다: {item.get('plcyNo')}")
    if expected_mode == "light" and (result["추천정책"] or result["추천상태"] != "미사용"):
        raise RuntimeError("라이트 진단은 LLM 추천정책을 반환하면 안 됩니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description="DIVE AI API smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--kcb-json", type=Path,
        help="모델 피처 42개와 추정가구원수를 개별 키로 포함한 공식 KCB 한 행 JSON 파일",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    health = request_json(f"{base_url}/health/ready")
    print(json.dumps({"health": health}, ensure_ascii=False))

    payload = LIGHT_PAYLOAD
    if args.kcb_json:
        kcb_record = json.loads(args.kcb_json.read_text(encoding="utf-8"))
        payload = {
            **LIGHT_PAYLOAD,
            "mode": "precise",
            "kcb_record": kcb_record,
        }
    result = request_json(f"{base_url}/v1/diagnose", payload=payload)
    validate_response(result, payload["mode"])
    summary = {
        "mode": result["진단모드"],
        "status": result["진단상태"],
        "classification_status": result["분류상태"],
        "user_type": result["유형"],
        "type_score": result["유형점수"],
        "policy_group_count": len(result["지원가능정책"]),
        "recommendation_status": result["추천상태"],
        "recommendation_method": result.get("추천방식"),
        "recommendation_ids": [item["plcyNo"] for item in result["추천정책"]],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
