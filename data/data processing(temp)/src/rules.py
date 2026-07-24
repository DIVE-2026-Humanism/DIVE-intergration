"""규칙엔진 — 통합 프로필 × 정규화 정책 → 자격 3분류.

파이프라인상 위치:
    preprocess.py (_norm.요건 부착) ─┐
    profile.py    (통합 프로필)      ─┴─→ rules.py → 정책별 {가능 / 불가 / 정보부족}

설계 원칙 (STATUS §4):
    - "제한없음"(ANY) 과 "정보없음"(None) 을 구분한다. 이게 3분류의 기반.
    - 자격 판정에 유형(6분류)은 쓰지 않는다. 정렬은 recommend.py 담당.
    - 축별 판정을 남겨 "왜 이 결과인지" 설명 가능하게 한다.

축 집계 규칙:
    하나라도 불충족 → 불가
    아니고 하나라도 정보부족 → 정보부족
    전부 충족 → 가능

── 통합 프로필 계약 (profile.py가 생산, 여기선 소비만) ──────────────────
Profile = {
    "연령":   int | None,          # 만 나이
    "혼인":   str | None,          # "미혼" / "기혼"          (mrgSttsCd 라벨)
    "연소득": int | None,          # 만원
    "직업군": str | None,          # "재직자" / "미취업자" …  (jobCd 라벨)
    "학력":   str | None,          # "대학 졸업" …            (schoolCd 라벨)
    "전공":   str | None,          # (plcyMajorCd 라벨)
    "특화":   list[str] | None,    # ["장애인","여성",…]      (sbizCd 라벨)
    "지역":   str | None,          # 시군구 코드 "26350"
}
프로필 값 라벨은 codebook.json 라벨과 정렬돼 있어야 멤버십 비교가 성립한다.
"""
import json
import sys
from pathlib import Path

# 축 판정 값
PASS, FAIL, UNKNOWN = "충족", "불충족", "정보부족"
# 정책 종합 판정 값
POSSIBLE, IMPOSSIBLE, INSUFFICIENT = "가능", "불가", "정보부족"

CLEAN = Path(__file__).resolve().parents[1] / "data" / "policy" / "clean" / "policies_clean.json"


# --- 축별 판정 함수 (각각 (판정, 근거) 반환) --------------------------------

def judge_age(profile, req):
    if req == "ANY":
        return PASS, "연령 무관"
    age = profile.get("연령")
    if age is None:
        return UNKNOWN, "연령 미입력"
    mn, mx = req.get("min"), req.get("max")
    if mn is not None and age < mn:
        return FAIL, f"{age}세 < 하한 {mn}"
    if mx is not None and age > mx:
        return FAIL, f"{age}세 > 상한 {mx}"
    return PASS, f"{age}세 ∈ {mn or 0}~{mx or '∞'}"


def judge_membership(value, req, axis):
    """코드 요건(ANY/None/라벨리스트) vs 프로필 단일값."""
    if req in ("ANY", None):
        return PASS, f"{axis} 무관"
    if value is None:
        return UNKNOWN, f"{axis} 미입력"
    if value in req:
        return PASS, f"{value} ∈ {req}"
    return FAIL, f"{value} ∉ {req}"


def judge_special(profile, req):
    """특화 요건 vs 프로필 특화 목록. 교집합 있으면 충족."""
    if req in ("ANY", None):
        return PASS, "특화 무관"
    user = profile.get("특화")
    if user is None:
        return UNKNOWN, "특화 미입력"
    hit = set(user) & set(req)
    if hit:
        return PASS, f"{sorted(hit)} 해당"
    return FAIL, f"{user} ∉ {req}"


def judge_income(profile, req):
    if req == "ANY":
        return PASS, "소득 무관"
    # req == {"판정":"LLM필요"} : 소득요건이 자유서술에 있어 아직 미해석
    # TODO: LLM 추출 후 req가 {"중위소득_max":60,...} 형태로 오면 여기서 실제 비교
    return UNKNOWN, "소득요건 미해석(LLM 추출 전)"


def judge_region(profile, policy):
    if policy["_norm"]["지역구분"] == "전국":
        return PASS, "전국"
    loc = profile.get("지역")
    if loc is None:
        return UNKNOWN, "지역 미입력"
    codes = {c.strip() for c in (policy.get("zipCd") or "").split(",") if c.strip()}
    if loc in codes:
        return PASS, f"{loc} 적용지역"
    return FAIL, f"{loc} 적용지역 아님"


# --- 정책 1건 판정 ----------------------------------------------------------

def judge_policy(profile, policy):
    req = policy["_norm"]["요건"]
    axes = {
        "연령": judge_age(profile, req["연령"]),
        "지역": judge_region(profile, policy),
        "취업": judge_membership(profile.get("직업군"), req["취업"], "직업"),
        "학력": judge_membership(profile.get("학력"), req["학력"], "학력"),
        "전공": judge_membership(profile.get("전공"), req["전공"], "전공"),
        "혼인": judge_membership(profile.get("혼인"), req["혼인"], "혼인"),
        "특화": judge_special(profile, req["특화"]),
        "소득": judge_income(profile, req["소득"]),
    }
    verdicts = [v for v, _ in axes.values()]
    if FAIL in verdicts:
        overall = IMPOSSIBLE
    elif UNKNOWN in verdicts:
        overall = INSUFFICIENT
    else:
        overall = POSSIBLE
    return {
        "plcyNo": policy.get("plcyNo"),
        "정책명": policy.get("plcyNm"),
        "판정": overall,
        "불충족": [k for k, (v, _) in axes.items() if v == FAIL],
        "정보부족": [k for k, (v, _) in axes.items() if v == UNKNOWN],
        "축별": {k: {"판정": v, "근거": why} for k, (v, why) in axes.items()},
    }


def judge_all(profile, policies):
    return [judge_policy(profile, p) for p in policies]


# --- 데모 -------------------------------------------------------------------

# 라이트 진단 예시 (STATUS §4): 25세 / 해운대 / 연소득 2650 / 무주택 / 재직자
SAMPLE_PROFILE = {
    "연령": 25, "혼인": "미혼", "연소득": 2650,
    "직업군": "재직자", "학력": "대학 졸업", "전공": None,
    "특화": [], "지역": "26350",
}


def _demo():
    policies = json.loads(CLEAN.read_text(encoding="utf-8"))
    results = judge_all(SAMPLE_PROFILE, policies)

    import collections
    dist = collections.Counter(r["판정"] for r in results)
    print(f"프로필: {SAMPLE_PROFILE}", file=sys.stderr)
    print(f"정책 {len(results)}건 판정 → {dict(dist)}", file=sys.stderr)

    for verdict in (POSSIBLE, INSUFFICIENT, IMPOSSIBLE):
        ex = next((r for r in results if r["판정"] == verdict), None)
        if ex:
            print(f"\n[{verdict}] {ex['정책명']}", file=sys.stderr)
            for axis, d in ex["축별"].items():
                print(f"    {axis}: {d['판정']} ({d['근거']})", file=sys.stderr)


if __name__ == "__main__":
    _demo()
