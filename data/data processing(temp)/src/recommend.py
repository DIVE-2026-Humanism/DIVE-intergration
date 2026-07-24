"""추천 — 규칙엔진 판정 → 지원가능 정책 그룹핑 + 유형별 정렬 + top-K.

파이프라인상 위치:
    rules.judge_all ─→ recommend.py ─→ 결과화면
                         (그룹핑·정렬·추천)

다이어그램의 '지원가능 정책 분류별 그룹핑' + '상단 추천' 담당. LLM 안 씀(순수 코드).

동작:
    1. 불가 제외 → 가능 + 정보부족만 남김 (정보부족도 "이것만 확인하세요"로 노출, STATUS §4)
    2. 대분류별 그룹핑
    3. 유형 가중치로 정렬 (정렬 전용 — 자격판정엔 안 씀, STATUS §4 부수규칙)
       유형이 없으면(라이트 진단) 가중치 0 → 상태·조회수 등 tie-break만으로 정렬
    4. top-K 추천 목록 (정밀 진단, 즉 유형이 있을 때만 상단 노출)

유형은 모델 레포(predictions.jsonl)의 산출물. 이 레포엔 아직 없어 계약으로만 받는다.
"""
import sys
from collections import defaultdict

import rules

# 유형별 정렬 가중치 — STUB(큐레이션 대상, STATUS 남은작업 6).
# ⚠️ 자격 판정엔 절대 안 쓴다. 같은 '가능' 정책들의 정렬 우선순위만 조정.
# 취약형(V*)=안정·주거·금융 우선 / 안정형(S*)=성장·자산형성·일자리 우선.
TYPE_WEIGHTS = {
    "V1": {"대분류": {"주거": 3, "복지문화": 2}, "키워드": {"신용회복": 3, "공공임대주택": 2, "주거지원": 2}},
    "V2": {"대분류": {"복지문화": 3, "주거": 2}, "키워드": {"신용회복": 2, "보조금": 1}},
    "V3": {"대분류": {"주거": 3, "일자리": 2}, "키워드": {"주거지원": 2, "장기미취업청년": 2}},
    "S1": {"대분류": {"일자리": 3, "교육": 2}, "키워드": {"인턴": 2, "교육지원": 2}},
    "S2": {"대분류": {"교육": 3, "일자리": 2}, "키워드": {"해외진출": 2, "교육지원": 2}},
    "S3": {"대분류": {"주거": 2, "일자리": 2}, "키워드": {"금리혜택": 2, "대출": 1}},
}

# tie-break: 진행중 > 상시 > 시작전 > 기간미상
STATUS_RANK = {"진행중": 3, "상시": 2, "시작전": 1, "기간미상": 0}
# 판정 우선순위: 가능이 정보부족보다 위
VERDICT_RANK = {rules.POSSIBLE: 0, rules.INSUFFICIENT: 1}


def score(policy, 유형):
    """정렬 점수. 유형 가중치(정렬 전용) + 상태·인기·지역밀착 tie-break."""
    norm = policy["_norm"]
    w = TYPE_WEIGHTS.get(유형, {})
    s = 0.0
    for cat in norm["대분류"]:
        s += w.get("대분류", {}).get(cat, 0)
    for kw in (policy.get("plcyKywdNm") or "").split(","):
        s += w.get("키워드", {}).get(kw.strip(), 0)
    # tie-break (유형 가중치보다 작게)
    s += STATUS_RANK.get(norm["상태"], 0) * 0.1
    s += min(int(policy.get("inqCnt") or 0), 100000) / 1e6
    if norm["지역구분"] == "부산한정":
        s += 0.05
    return round(s, 4)


def _card(verdict, policy):
    """결과화면용 정책 카드 (판정 + 표시 메타)."""
    norm = policy["_norm"]
    return {
        "plcyNo": verdict["plcyNo"],
        "정책명": verdict["정책명"],
        "판정": verdict["판정"],
        "정보부족축": verdict["정보부족"],
        "대분류": norm["대분류"],
        "상태": norm["상태"],
        "지역구분": norm["지역구분"],
        "설명": policy.get("plcyExplnCn", ""),
    }


def recommend(profile, policies, 유형=None, top_k=5):
    """지원가능 정책을 그룹핑·정렬하고 top-K 추천을 얹어 돌려준다."""
    verdicts = rules.judge_all(profile, policies)
    by_no = {p["plcyNo"]: p for p in policies}

    scored = []  # (점수, 카드, 정책)
    for v in verdicts:
        if v["판정"] == rules.IMPOSSIBLE:
            continue
        pol = by_no[v["plcyNo"]]
        scored.append((score(pol, 유형), _card(v, pol)))

    # 가능 먼저, 그 안에서 점수 내림차순
    scored.sort(key=lambda t: (VERDICT_RANK[t[1]["판정"]], -t[0]))
    ordered = [card for _, card in scored]

    groups = defaultdict(list)
    for card in ordered:
        for cat in card["대분류"] or ["기타"]:
            groups[cat].append(card)

    return {
        "추천": ordered[:top_k] if 유형 else [],   # 정밀(유형 有)만 상단 추천
        "그룹": dict(groups),
        "요약": {
            rules.POSSIBLE: sum(c["판정"] == rules.POSSIBLE for c in ordered),
            rules.INSUFFICIENT: sum(c["판정"] == rules.INSUFFICIENT for c in ordered),
            "불가": len(verdicts) - len(ordered),
        },
    }


# --- 데모 -------------------------------------------------------------------

def _demo():
    import json
    import profile as profile_mod

    policies = json.loads(rules.CLEAN.read_text(encoding="utf-8"))
    prof = profile_mod.from_light(profile_mod.SAMPLE_FORM)

    for 유형 in (None, "V3"):
        res = recommend(prof, policies, 유형=유형, top_k=3)
        tag = f"유형={유형}" if 유형 else "라이트(유형없음)"
        print(f"\n=== {tag} ===", file=sys.stderr)
        print(f"요약: {res['요약']}", file=sys.stderr)
        print(f"그룹: {[(k, len(v)) for k, v in res['그룹'].items()]}", file=sys.stderr)
        if res["추천"]:
            print("상단 추천 top-3:", file=sys.stderr)
            for c in res["추천"]:
                print(f"    [{c['판정']}] {c['정책명']} ({'/'.join(c['대분류'])}, {c['상태']})",
                      file=sys.stderr)


if __name__ == "__main__":
    _demo()
