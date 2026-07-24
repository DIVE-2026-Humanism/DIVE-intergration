"""수집한 부산 청년정책 전처리 파이프라인.

파이프라인: fetch_policies.py → preprocess.py → (이후 매칭 단계)

구조: STEPS 리스트에 (이름, 함수)를 순서대로 등록하고 run()이 차례로 실행한다.
전처리 스텝을 추가하려면 함수 하나를 쓰고 STEPS에 한 줄 넣으면 된다.
각 스텝은 records(list) → records(list) 순수 변환이며,
- 필터 스텝: 리스트를 줄인다 (예: 마감 제외)
- 주석 스텝: 각 레코드에 `_norm` 블록을 채운다 (원본 필드는 건드리지 않음)

현재 스텝:
    1. 마감 필터        (filter_closed)
    2. 요건 정규화      (normalize)   → _norm.{상태, 지역구분, 대분류, 요건, llm추출필요}
향후 추가 예정:
    - 중복 제거(정책명 정규화), LLM 소득요건 추출 결과 병합, 연령버킷 판정 등

사용법:
    python3 src/preprocess.py
입력:
    data/policy/raw/busan_policies.json,  data/policy/codebook.json
결과:
    data/policy/clean/policies_clean.json  (마감 제외 + _norm 부착, 원본 필드 무변경)
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "policy"
RAW = DATA / "raw" / "busan_policies.json"
CODEBOOK = DATA / "codebook.json"
OUT = DATA / "clean" / "policies_clean.json"


# --- 공통 헬퍼 --------------------------------------------------------------

def _codes(raw):
    """콤마 다중값 → 코드 리스트 (공백 제거)."""
    return [c.strip() for c in (raw or "").split(",") if c.strip()]


def _num(v):
    """숫자 문자열 → int, '0'/공백/비숫자는 None."""
    v = str(v or "").strip()
    return int(v) if v.isdigit() and v != "0" else None


# --- 스텝 1: 마감 필터 ------------------------------------------------------

def is_closed(r, today):
    """마감이 확실하면 True. 판정 불가(종료일 없음)는 False로 남긴다.

    - aplyPrdSeCd == 0057003        마감 명시
    - 특정기간(0057001) + 종료일<오늘  기간 경과
    - aplyPrdSeCd == 0057002        상시 → 항상 열림
    """
    ap = r.get("aplyPrdSeCd")
    if ap == "0057002":
        return False
    if ap == "0057003":
        return True
    end = (r.get("bizPrdEndYmd") or "").strip()   # 특정기간(0057001)
    return end.isdigit() and end < today          # 종료일 경과 시 마감


def filter_closed(records, ctx):
    kept = [r for r in records if not is_closed(r, ctx["today"])]
    ctx["log"].append(f"[마감필터] {len(records)}건 → {len(kept)}건 "
                      f"(마감 {len(records) - len(kept)}건 제외)")
    return kept


# --- 스텝 2: 요건 정규화 ----------------------------------------------------

# 코드형 요건축: 이름 → (원본필드, codebook키, '제한없음' 코드)
CODE_AXES = {
    "취업": ("jobCd", "jobCd", "0013010"),
    "학력": ("schoolCd", "schoolCd", "0049010"),
    "전공": ("plcyMajorCd", "plcyMajorCd", "0011009"),
    "혼인": ("mrgSttsCd", "mrgSttsCd", "0055003"),
    "특화": ("sbizCd", "sbizCd", "0014010"),
}
# 자유서술에 소득·재산 조건이 숨어있는지 걸러내는 정규식 (FINDINGS §1)
INCOME_RX = re.compile(r"중위소득|만원 이하|재산|무주택|기초생활|차상위|소득")
INCOME_TEXT_FIELDS = ("earnEtcCn", "addAplyQlfcCndCn", "ptcpPrpTrgtCn")


def norm_code_axis(r, field, book, unlimited, codebook):
    """코드 요건 → 'ANY'(제한없음) / 라벨 리스트 / None(정보없음)."""
    codes = _codes(r.get(field))
    if not codes:
        return None
    if unlimited in codes:
        return "ANY"
    labels = codebook.get(book, {})
    return [labels.get(c, c) for c in codes]


def norm_age(r):
    """연령 → {min,max} / 'ANY'. 신뢰불가 플래그(sprtTrgtAgeLmtYn)는 무시."""
    mn, mx = _num(r.get("sprtTrgtMinAge")), _num(r.get("sprtTrgtMaxAge"))
    if mn is None and mx is None:
        return "ANY"
    return {"min": mn, "max": mx}


def norm_income(r):
    """소득 → 'ANY' / {판정:'LLM필요'}. 무관이어도 서술에 조건 있으면 LLM필요."""
    code = r.get("earnCndSeCd")
    text = " ".join(r.get(f) or "" for f in INCOME_TEXT_FIELDS)
    hidden = bool(INCOME_RX.search(text))
    if code == "0043001" and not hidden:      # 무관 + 서술에도 조건 없음
        return "ANY"
    return {"판정": "LLM필요"}


def norm_region(r):
    """zipCd 시도 prefix → 전국 / 부산한정 / 광역."""
    sido = {c[:2] for c in _codes(r.get("zipCd"))}
    if sido == {"26"}:
        return "부산한정"
    if len(sido) == 16:
        return "전국"
    return "광역"


def norm_category(r, codebook):
    """lclsfNm 구분류 정규화 + 콤마 중복 제거."""
    remap = codebook["lclsfNm"]["_normalize"]
    out = []
    for v in _codes(r.get("lclsfNm")):
        v = remap.get(v, v)
        if v not in out:
            out.append(v)
    return out


def status_label(r, today):
    """생존 정책의 상태 라벨 (마감은 이미 필터됨)."""
    if r.get("aplyPrdSeCd") == "0057002":
        return "상시"
    end = (r.get("bizPrdEndYmd") or "").strip()
    bgn = (r.get("bizPrdBgngYmd") or "").strip()
    if end.isdigit():
        return "시작전" if (bgn.isdigit() and bgn > today) else "진행중"
    return "기간미상"


def llm_needed(r):
    """자유서술에 코드로 안 잡히는 요건(소득·재산 등)이 있는가."""
    if r.get("earnCndSeCd") != "0043001":
        return True
    text = " ".join(r.get(f) or "" for f in INCOME_TEXT_FIELDS)
    return bool(INCOME_RX.search(text))


def normalize(records, ctx):
    cb = ctx["codebook"]
    today = ctx["today"]
    for r in records:
        req = {"연령": norm_age(r)}
        for axis, (field, book, unlimited) in CODE_AXES.items():
            req[axis] = norm_code_axis(r, field, book, unlimited, cb)
        req["소득"] = norm_income(r)
        r["_norm"] = {
            "상태": status_label(r, today),
            "지역구분": norm_region(r),
            "대분류": norm_category(r, cb),
            "요건": req,
            "llm추출필요": llm_needed(r),
        }
    ctx["log"].append(f"[요건정규화] {len(records)}건에 _norm 부착 "
                      f"(LLM추출필요 {sum(r['_norm']['llm추출필요'] for r in records)}건)")
    return records


# --- 파이프라인 -------------------------------------------------------------

STEPS = [
    ("마감필터", filter_closed),
    ("요건정규화", normalize),
]


def run(records, ctx):
    for _, fn in STEPS:
        records = fn(records, ctx)
    return records


def main():
    ctx = {
        "today": date.today().strftime("%Y%m%d"),
        "codebook": json.loads(CODEBOOK.read_text(encoding="utf-8")),
        "log": [],
    }
    records = json.loads(RAW.read_text(encoding="utf-8"))
    records = run(records, ctx)

    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"기준일 {ctx['today']}", file=sys.stderr)
    for line in ctx["log"]:
        print(line, file=sys.stderr)
    print(f"저장: {OUT} ({len(records)}건)", file=sys.stderr)


if __name__ == "__main__":
    main()
