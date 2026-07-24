"""핸드오프 export — 정제된 정책을 AI 서버 스키마로 내보낸다.

파이프라인상 위치:
    preprocess.py (policies_clean.json, 내부용 _norm 포함)
        └─→ export_policies.py → policies_export.json (AI 서버 ingest용)

AI 서버(ai.beceleb.org)의 정책카드 키에 맞춰 내보내고, 매칭용 정규화 요건(_norm.요건)을
함께 실어 서버 자격판정이 FINDINGS 규칙(제한없음→ANY, 연령 min/max, 소득 LLM필요)을
그대로 쓰도록 한다. 서버 카드 키는 /v1/diagnose 응답에서 관측한 값 기준.

⚠️ 최종 ingest 스키마는 AI 서버 담당자와 확정할 것. 여기 키명은 관측 기반 초안이다.

사용법:
    python3 src/export_policies.py
입력:
    data/policy/clean/policies_clean.json
결과:
    data/policy/export/policies_export.json  (마감 제외 175건, 서버 스키마)
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "policy"
CLEAN = DATA / "clean" / "policies_clean.json"
OUT = DATA / "export" / "policies_export.json"


def _split(raw):
    """콤마 다중값 → 중복 제거 리스트."""
    out = []
    for v in (raw or "").split(","):
        v = v.strip()
        if v and v not in out:
            out.append(v)
    return out


def to_card(r):
    """정제 레코드 1건 → 서버 ingest용 카드."""
    norm = r["_norm"]
    return {
        # 식별·표시 (서버 정책카드 관측 키)
        "plcyNo": r["plcyNo"],
        "plcyNm": r["plcyNm"],
        "대분류": norm["대분류"],
        "중분류": _split(r.get("mclsfNm")),
        "키워드": _split(r.get("plcyKywdNm")),
        "설명": r.get("plcyExplnCn", ""),
        "지원내용": r.get("plcySprtCn", ""),
        "소득기타": r.get("earnEtcCn", ""),
        "추가자격": r.get("addAplyQlfcCndCn", ""),
        "제외대상": r.get("ptcpPrpTrgtCn", ""),
        "신청시작일": (r.get("bizPrdBgngYmd") or "").strip(),
        "신청종료일": (r.get("bizPrdEndYmd") or "").strip(),
        "참고URL": r.get("refUrlAddr1", ""),
        "신청URL": r.get("aplyUrlAddr", ""),
        # 파생 (우리 도메인 계산)
        "상태": norm["상태"],
        "지역구분": norm["지역구분"],
        "적용지역코드": r.get("zipCd", ""),      # 지역 매칭용 (콤마 다중)
        # 매칭용 정규화 요건 — 서버 자격판정이 이걸 쓰면 FINDINGS 규칙 상속
        "요건": norm["요건"],
        "llm추출필요": norm["llm추출필요"],
    }


def main():
    policies = json.loads(CLEAN.read_text(encoding="utf-8"))
    cards = [to_card(r) for r in policies]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")

    import collections
    region = collections.Counter(c["지역구분"] for c in cards)
    status = collections.Counter(c["상태"] for c in cards)
    llm = sum(c["llm추출필요"] for c in cards)
    print(f"export {len(cards)}건 → {OUT}", file=sys.stderr)
    print(f"  지역구분 {dict(region)} / 상태 {dict(status)}", file=sys.stderr)
    print(f"  소득 LLM추출필요 {llm}건 (서버가 소득기타/추가자격에서 추출)", file=sys.stderr)


if __name__ == "__main__":
    main()
