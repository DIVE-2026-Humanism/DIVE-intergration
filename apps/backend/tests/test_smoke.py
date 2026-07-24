"""골격이 배선대로 동작하는지 확인하는 최소 smoke test.

세부 케이스(재시도, 422/502/503, KCB 샘플 등)는 실제 로직을 채울 때
같이 작성한다.
"""

import httpx

LIGHT_BODY = {
    "mode": "light",
    "user_inputs": {
        "성별": "여",
        "결혼여부": "미혼",
        "연소득": 30000000,
        "직업군": "재직자",
        "학력": "대학 졸업",
        "특화": [],
        "사는곳": "중구",
        "나이": 27,
    },
}


def test_diagnose_relays_ai_server_response(client, mock_ai_server):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/diagnose"
        return httpx.Response(200, json={"진단상태": "완료", "분류상태": "미사용"})

    mock_ai_server(handler)

    resp = client.post("/api/diagnose", json=LIGHT_BODY)

    assert resp.status_code == 200
    assert resp.json() == {"진단상태": "완료", "분류상태": "미사용"}
