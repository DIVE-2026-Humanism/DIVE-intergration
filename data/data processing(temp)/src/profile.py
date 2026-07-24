"""입력 어댑터 — 라이트 폼 / KCB 샘플행 → 통합 Profile.

파이프라인상 위치:
    라이트 폼(7문항) ┐
                     ├─→ profile.py → Profile(8필드) → rules.py
    KCB 샘플행(42열) ┘

두 진단 모드가 형태가 전혀 다른 입력을 주므로, 규칙엔진이 먹는 하나의 Profile로
번역한다. idea 다이어그램대로 정밀 모드도 7문항을 함께 받으므로,
KCB가 채우는 축(연령·소득·지역·성별)은 선채움하고 나머지(혼인·직업군·학력·특화)는
폼에서 받는다. 두 소스가 겹치면 폼(사용자 입력)이 이긴다.

핵심 규칙:
    - KCB가 못 채우는 축(혼인·직업군·학력·특화)은 폼에서만 온다.
      특히 직업군: KCB 코드(420·910…)는 코드북이 없어 라벨 매핑 불가 →
      폼 선택이 이를 우회한다. (STATUS 막힌 것 참조)
    - 각 축에 _source(USER/KCB/None)를 달아 규칙엔진의 '정보부족' 근거로 쓴다.
    - 프로필 라벨은 codebook.json 라벨과 정렬돼야 rules의 멤버십 비교가 성립한다.

산출물 Profile 계약은 rules.py 상단 docstring 참조.
"""
import csv
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
KCB_SAMPLE = DATA / "kcb" / "KCB합성데이터 종합해커톤샘플.csv"

# KCB가 채우는 축 / 폼에서만 오는 축
KCB_AXES = ("연령", "연소득", "지역")
USER_AXES = ("혼인", "직업군", "학력", "특화")
# 성별 코드 (KCB) — 1:남, 2:여 (KCB 컬럼 정의서 기준, 확인 필요)
SEX_FEMALE = "2"


def _blank():
    return {
        "연령": None, "혼인": None, "연소득": None,
        "직업군": None, "학력": None, "전공": None,
        "특화": None, "지역": None,
        "_source": {},
    }


def _set(profile, axis, value, source):
    profile[axis] = value
    profile["_source"][axis] = source


def _merge_special(current, extra):
    """특화 목록에 항목 추가 (None은 빈 목록으로 승격)."""
    out = list(current) if current else []
    for x in extra:
        if x and x not in out:
            out.append(x)
    return out


# --- 라이트 폼 → Profile -----------------------------------------------------

def _apply_form(p, form):
    """7문항 폼 dict를 Profile에 반영 (USER 소스). 겹치면 덮어씀."""
    for axis in ("연령", "혼인", "연소득", "직업군", "학력", "지역"):
        if form.get(axis) is not None:
            _set(p, axis, form[axis], "USER")

    # 특화: 폼 선택 + 성별 여성 → sbizCd '여성'
    special = list(form.get("특화") or [])
    if str(form.get("성별")) == SEX_FEMALE or form.get("성별") in ("여", "여성"):
        special = _merge_special(special, ["여성"])
    if "특화" in form or special:
        _set(p, "특화", special, "USER")


def from_light(form):
    """라이트 진단: 7문항 폼만으로 Profile 생성."""
    p = _blank()
    _apply_form(p, form)
    return p


# --- KCB행 → Profile ---------------------------------------------------------

def _apply_kcb(p, row):
    """KCB 42컬럼에서 자격축을 반영 (KCB 소스)."""
    # 연령: 연령대는 5세 구간 시작값(18/20/25/30/35). 지금은 구간 시작 나이로 둔다.
    # TODO: 구간 겹침 판정 — 정책 연령하한이 19면 18버킷은 '부분해당'(정보부족)이어야 함.
    age = str(row.get("연령대") or "").strip()
    if age.isdigit():
        _set(p, "연령", int(age), "KCB")

    # 연소득: KCB는 천원 단위 → 만원으로 변환 (월소득×12 ≈ 연소득으로 검증됨)
    inc = str(row.get("추정 연소득") or "").strip()
    if inc.lstrip("-").isdigit():
        _set(p, "연소득", int(inc) // 10, "KCB")

    loc = str(row.get("거주지 시군구 코드") or "").strip()
    if loc:
        _set(p, "지역", loc, "KCB")

    # 성별 → 특화 여성
    if str(row.get("성별") or "").strip() == SEX_FEMALE:
        _set(p, "특화", _merge_special(p.get("특화"), ["여성"]), "KCB")

    # 직업군: KCB 코드(420 등)는 코드북 없어 매핑 불가 → 값 없음으로 두고 표시만.
    #         폼이 있으면 _apply_form이 USER 값으로 덮어써 우회한다.
    if row.get("직업군"):
        p["_source"]["직업군"] = "KCB_코드북없음"


def from_kcb(row, form=None):
    """정밀 진단: KCB행으로 선채움 후, 폼이 있으면 USER축을 채우고 덮어쓴다.

    원본 KCB행은 유형모델·소비분석용으로 profile['_kcb']에 보존한다.
    """
    p = _blank()
    _apply_kcb(p, row)
    if form:
        _apply_form(p, form)
    p["_kcb"] = dict(row)
    return p


# --- 데모 -------------------------------------------------------------------

SAMPLE_FORM = {
    "성별": "여", "혼인": "미혼", "연령": 25, "연소득": 2650,
    "직업군": "재직자", "학력": "대학 졸업", "특화": ["장애인"], "지역": "26350",
}


def _show(title, p):
    print(f"\n=== {title} ===", file=sys.stderr)
    for k in ("연령", "혼인", "연소득", "직업군", "학력", "전공", "특화", "지역"):
        src = p["_source"].get(k)
        print(f"  {k:5} = {str(p[k]):14} [{src}]", file=sys.stderr)


def _demo():
    _show("라이트: 폼만", from_light(SAMPLE_FORM))

    with open(KCB_SAMPLE, encoding="utf-8-sig") as f:
        kcb_row = next(csv.DictReader(f))

    _show("정밀: KCB만 (폼 없음)", from_kcb(kcb_row))
    _show("정밀: KCB + 폼 병합", from_kcb(kcb_row, SAMPLE_FORM))

    # 규칙엔진에 실제로 물려보기
    try:
        import json
        import rules
        policies = json.loads(rules.CLEAN.read_text(encoding="utf-8"))
        p = from_light(SAMPLE_FORM)
        p.pop("_source", None)
        import collections
        dist = collections.Counter(r["판정"] for r in rules.judge_all(p, policies))
        print(f"\n[rules 연동] 라이트 프로필 {len(policies)}건 판정 → {dict(dist)}",
              file=sys.stderr)
    except Exception as e:
        print(f"\n[rules 연동 스킵] {e}", file=sys.stderr)


if __name__ == "__main__":
    _demo()
