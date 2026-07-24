from __future__ import annotations

from copy import deepcopy
import json

import pytest

from src.io_load import load_config
from src.llm_recommend import (
    call_local_llm,
    fallback_recommendations,
    recommend_policies,
    validate_recommendations,
)


def test_candidate_outside_policy_is_filtered() -> None:
    response = json.dumps([
        {"plcyNo": "OUTSIDE", "순위": 1, "추천이유": "x", "매칭포인트": "x", "주의": "x"},
        {"plcyNo": "P1", "순위": 2, "추천이유": "적합", "매칭포인트": "부산 거주", "주의": "서류 확인 필요"},
    ], ensure_ascii=False)
    result = validate_recommendations(response, {"P1"})
    assert [item["plcyNo"] for item in result] == ["P1"]


def test_recommendation_uses_mock_llm_and_candidate_contract() -> None:
    groups = [{"대분류": "주거", "정책": [{"plcyNo": "P1", "plcyNm": "주거지원", "추가자격": "무주택", "제외대상": "", "소득기타": ""}]}]
    calls = []

    def fake(system: str, user: str) -> str:
        calls.append((system, user))
        return '[{"plcyNo":"P1","순위":1,"추천이유":"주거 지원 필요","매칭포인트":"무주택 확인","주의":"서류 확인 필요"}]'

    result = recommend_policies(
        groups,
        {"사는곳": "중구"},
        {"유형": "경제적 취약 청년", "세부유형코드": "V3", "유형점수": 70.0, "안정점수": 30.0},
        {"items": []},
        config=load_config(),
        llm_callable=fake,
    )
    assert result[0]["plcyNo"] == "P1"
    assert "V3" in calls[0][0]
    assert "무주택" in calls[0][1]


def test_local_ollama_request_uses_structured_non_streaming_output(monkeypatch) -> None:
    captured = {}

    def fake_http(url, payload, timeout):
        captured.update({"url": url, "payload": payload, "timeout": timeout})
        return {"message": {"content": "[]"}}

    monkeypatch.setattr("src.llm_recommend._http_json", fake_http)
    assert call_local_llm("system", "user", load_config()) == "[]"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["think"] is False
    assert captured["payload"]["format"]["type"] == "array"
    assert captured["payload"]["options"]["num_ctx"] == 16384


def test_local_llm_rejects_remote_host() -> None:
    config = deepcopy(load_config())
    config["local_llm"]["base_url"] = "https://example.com"
    with pytest.raises(ValueError, match="허용된 내부"):
        call_local_llm("system", "user", config)


def test_many_candidates_are_shortlisted_once_before_llm() -> None:
    config = deepcopy(load_config())
    config["local_llm"]["shortlist_size"] = 2
    config["service"]["recommendation_top_k"] = 1
    groups = [{"대분류": "주거", "정책": [
        {"plcyNo": "P1", "plcyNm": "1"},
        {"plcyNo": "P2", "plcyNm": "2"},
        {"plcyNo": "P3", "plcyNm": "3"},
    ]}]
    calls = []

    def fake(system: str, user: str) -> str:
        calls.append(user)
        return '[{"plcyNo":"P1","순위":1,"추천이유":"a","매칭포인트":"a","주의":"a"}]'

    result = recommend_policies(groups, {}, None, {}, config=config, llm_callable=fake)
    assert result[0]["plcyNo"] == "P1"
    assert len(calls) == 1
    assert '"plcyNo": "P3"' not in calls[0]


def test_llm_prompt_omits_exact_financial_values() -> None:
    groups = [{"대분류": "주거", "정책": [{"plcyNo": "P1", "plcyNm": "주거지원"}]}]
    calls = []

    def fake(system: str, user: str) -> str:
        calls.append(user)
        return '[{"plcyNo":"P1","순위":1,"추천이유":"a","매칭포인트":"a","주의":"a"}]'

    recommend_policies(
        groups,
        {"연소득": 39_916_000, "사는곳": "동래구", "직업군": "재직자"},
        {"유형": "경제적 취약 청년", "세부유형코드": "V3", "유형점수": 57.9, "안정점수": 42.1, "확률": {"V3": 0.8}},
        {"items": [{"지표": "연소득", "값": 39_916, "또래평균": 42_070, "격차%": -5.1}]},
        config=load_config(),
        llm_callable=fake,
    )
    assert "39916000" not in calls[0]
    assert "39916" not in calls[0]
    assert "42070" not in calls[0]


def test_candidate_text_is_bounded_before_llm() -> None:
    groups = [{"대분류": "주거", "정책": [
        {"plcyNo": f"P{index}", "plcyNm": f"정책{index}", "설명": "가" * 5_000, "지원내용": "나" * 5_000}
        for index in range(20)
    ]}]
    prompts = []

    def fake(system: str, user: str) -> str:
        prompts.append(user)
        return "[]"

    recommend_policies(groups, {}, None, {}, config=load_config(), llm_callable=fake)
    assert len(prompts) == 1
    assert len(prompts[0]) < 20_000


def test_fallback_recommendation_uses_only_eligible_candidates() -> None:
    groups = [
        {"대분류": "주거", "정책": [{"plcyNo": "P1", "plcyNm": "주거지원", "대분류": ["주거"]}]},
        {"대분류": "복지문화", "정책": [{"plcyNo": "P2", "plcyNm": "생활지원", "대분류": ["복지문화"]}]},
    ]
    result = fallback_recommendations(
        groups,
        {"나이": 35, "사는곳": "동래구", "연소득": 39_916_000},
        {"유형": "경제적 취약 청년", "세부유형코드": "V3"},
        top_k=2,
    )
    assert [item["plcyNo"] for item in result] == ["P2", "P1"]
    assert [item["순위"] for item in result] == [1, 2]
    assert all(item["plcyNo"] in {"P1", "P2"} for item in result)
    assert "V3" not in result[0]["추천이유"]


def test_shortlist_preserves_category_diversity() -> None:
    config = deepcopy(load_config())
    config["local_llm"]["shortlist_size"] = 5
    config["service"]["recommendation_top_k"] = 5
    groups = [
        {"대분류": "일자리", "정책": [
            {"plcyNo": f"J{index}", "plcyNm": f"일자리{index}", "대분류": ["일자리"]}
            for index in range(10)
        ]},
        {"대분류": "주거", "정책": [{"plcyNo": "H1", "plcyNm": "주거", "대분류": ["주거"]}]},
        {"대분류": "교육", "정책": [{"plcyNo": "E1", "plcyNm": "교육", "대분류": ["교육"]}]},
        {"대분류": "복지문화", "정책": [{"plcyNo": "W1", "plcyNm": "복지", "대분류": ["복지문화"]}]},
        {"대분류": "참여권리", "정책": [{"plcyNo": "R1", "plcyNm": "참여", "대분류": ["참여권리"]}]},
    ]
    captured = []

    def fake(system: str, user: str) -> str:
        captured.extend(item["plcyNo"] for item in json.loads(user.split("\n적합한", 1)[0])["후보정책"])
        return "[]"

    recommend_policies(groups, {}, None, {}, config=config, llm_callable=fake)
    assert set(captured) == {"J0", "H1", "E1", "W1", "R1"}
