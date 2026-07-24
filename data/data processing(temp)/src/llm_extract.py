"""LLM 소득·재산 요건 추출 — 계약(입력/스키마/병합).

정형 코드로 안 잡히는 요건(소득·재산·무주택·중복수혜)이 자유서술에 묻혀 있다(FINDINGS §1).
LLM 런타임(모델 구동·배치)은 별도 담당. 이 모듈은 그 도구에 물릴 **계약**만 정의한다:

    build_input()  → data/policy/llm/extract_input.json   (LLM에 넣을 배치)
    [LLM 실행]     → data/policy/llm/extract_output.json   (담당자 산출)
    merge()        → 각 정책에 _extracted 부착 (STATUS §4: 출처 물리적 분리)

정형(_norm.요건)·LLM(_extracted)·코드계산(_norm) 을 섞지 않는다. 검수는 _extracted만 보면 된다.

사용법:
    python3 src/llm_extract.py build     # 입력 배치 생성
    python3 src/llm_extract.py merge      # LLM 출력 병합 (output 있을 때)
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "policy"
CLEAN = DATA / "clean" / "policies_clean.json"
LLM_DIR = DATA / "llm"
IN = LLM_DIR / "extract_input.json"
OUT = LLM_DIR / "extract_output.json"

TEXT_FIELDS = ("earnEtcCn", "addAplyQlfcCndCn", "ptcpPrpTrgtCn", "plcySprtCn")

# ── 추출 스키마: 정책 1건당 LLM이 뱉어야 할 _extracted 형태 ───────────────────
# 판정주체(STATUS §4 원칙3): KCB=데이터로 판정 / USER=물어봄 / NEVER=아무도 모름.
# 값이 없으면 null. "정보없음(null)"과 "해당없음"을 섞지 말 것.
EXTRACTION_SCHEMA = {
    "본인소득": {"중위소득_max_pct": "int|null", "연소득_max_만원": "int|null", "판정주체": "KCB"},
    "원가구소득": {"중위소득_max_pct": "int|null", "판정주체": "NEVER"},  # 부모 소득 = KCB 없음
    "무주택": {"required": "bool|null", "판정주체": "USER"},
    "재산": {"본인_max_만원": "int|null", "원가구_max_만원": "int|null", "판정주체": "KCB(본인)/NEVER(원가구)"},
    "중복수혜배제": {"있음": "bool|null", "판정주체": "USER"},
    "_근거": {"필드명": "인용문 (검수용, 반드시 원문에서)"},
}

PROMPT = """\
너는 청년정책 지원요건 추출기다. 아래 정책의 자유서술에서 **소득·재산·주택·중복수혜** 요건만
JSON으로 뽑아라. 규칙:

1. 원문에 **명시된 것만** 뽑는다. 추론·상식 보충 금지. 없으면 null.
2. 본인(청년가구)과 원가구(부모/원가족)를 **반드시 구분**한다. "원가구/가구/부모"는 원가구로.
3. 중위소득은 퍼센트 정수(60), 금액은 만원 정수(재산 4억 → 40000)로 정규화.
4. 각 추출값의 **근거 문장을 원문에서 그대로 인용**해 _근거에 넣는다 (검수용).
5. 출력은 아래 스키마의 JSON 하나. 설명 문장 금지.

스키마:
%s

정책명: {정책명}
원문:
{원문}
""" % json.dumps(EXTRACTION_SCHEMA, ensure_ascii=False, indent=2)


def build_input():
    """flagged 정책의 원문을 모아 LLM 입력 배치를 만든다."""
    policies = json.loads(CLEAN.read_text(encoding="utf-8"))
    batch = []
    for r in policies:
        if not r["_norm"]["llm추출필요"]:
            continue
        texts = {f: (r.get(f) or "").strip() for f in TEXT_FIELDS if (r.get(f) or "").strip()}
        batch.append({"plcyNo": r["plcyNo"], "정책명": r["plcyNm"], "원문": texts})
    LLM_DIR.mkdir(parents=True, exist_ok=True)
    IN.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    no_text = sum(1 for b in batch if not b["원문"])
    print(f"입력 배치 {len(batch)}건 → {IN}", file=sys.stderr)
    print(f"  (원문 없음 {no_text}건 — 코드 flagged만, LLM이 null 반환하면 됨)", file=sys.stderr)
    print(f"프롬프트 템플릿: llm_extract.PROMPT ({{정책명}}/{{원문}} 치환)", file=sys.stderr)


def merge():
    """LLM 출력(plcyNo→_extracted)을 각 정책에 병합해 clean을 갱신한다."""
    if not OUT.exists():
        sys.exit(f"LLM 출력이 없다: {OUT}\n담당자 배치 실행 후 다시.")
    policies = json.loads(CLEAN.read_text(encoding="utf-8"))
    extracted = json.loads(OUT.read_text(encoding="utf-8"))  # {plcyNo: _extracted}
    hit = 0
    for r in policies:
        ext = extracted.get(r["plcyNo"])
        if ext is not None:
            r["_extracted"] = ext
            hit += 1
    CLEAN.write_text(json.dumps(policies, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"_extracted 병합 {hit}건 → {CLEAN}", file=sys.stderr)
    print("다음: rules.judge_income이 _extracted를 읽도록 확장 (+ 기준중위소득 표)", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build_input, "merge": merge}.get(cmd, build_input)()
