"""온통청년 OpenAPI에서 부산 청년정책을 전건 수집한다.

사용법:
    YOUTH_API_KEY=... python3 src/fetch_policies.py
결과:
    data/policy/raw/busan_policies.json  (원본 레코드 배열)
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.youthcenter.go.kr/go/ythip/getPlcy"

# 부산광역시 16개 시군구 법정동 코드
BUSAN_SGG = [
    ("26110", "중구"), ("26140", "서구"), ("26170", "동구"), ("26200", "영도구"),
    ("26230", "부산진구"), ("26260", "동래구"), ("26290", "남구"), ("26320", "북구"),
    ("26350", "해운대구"), ("26380", "사하구"), ("26410", "금정구"), ("26440", "강서구"),
    ("26470", "연제구"), ("26500", "수영구"), ("26530", "사상구"), ("26710", "기장군"),
]

PAGE_SIZE = 100
OUT = Path(__file__).resolve().parents[1] / "data" / "policy" / "raw" / "busan_policies.json"


def get(params):
    url = f"{API}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        body = json.loads(r.read().decode("utf-8"))
    if body.get("resultCode") != 200:
        raise RuntimeError(f"API error: {body.get('resultCode')} {body.get('resultMessage')}")
    return body["result"]


def main():
    key = os.environ.get("YOUTH_API_KEY")
    if not key:
        sys.exit("YOUTH_API_KEY 환경변수가 필요합니다 (.env 참고)")

    base = {
        "apiKeyNm": key,
        "rtnType": "json",
        "pageSize": PAGE_SIZE,
        "zipCd": ",".join(code for code, _ in BUSAN_SGG),
    }

    first = get({**base, "pageNum": 1})
    total = first["pagging"]["totCount"]
    records = list(first["youthPolicyList"])
    pages = -(-total // PAGE_SIZE)
    print(f"총 {total}건 / {pages}페이지", file=sys.stderr)

    for page in range(2, pages + 1):
        chunk = get({**base, "pageNum": page})["youthPolicyList"]
        records.extend(chunk)
        print(f"  page {page}/{pages} (+{len(chunk)}, 누적 {len(records)})", file=sys.stderr)
        time.sleep(0.3)

    # plcyNo 기준 중복 제거 (페이지 경계에서 중복될 수 있음)
    seen, deduped = set(), []
    for r in records:
        if r["plcyNo"] not in seen:
            seen.add(r["plcyNo"])
            deduped.append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {OUT} ({len(deduped)}건, 중복 {len(records) - len(deduped)}건 제거)", file=sys.stderr)


if __name__ == "__main__":
    main()
