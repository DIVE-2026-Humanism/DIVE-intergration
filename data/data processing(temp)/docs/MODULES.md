# 모듈 상세 설명

각 모듈이 **무엇을 입력받아, 어떤 처리를 거쳐, 무엇을 내보내는지**를 함수 단위로 기술한다.
전체 그림은 루트 `README.md`, API 함정 근거는 `docs/FINDINGS.md` 참조.

```
fetch_policies ─▶ preprocess ─▶ export_policies ─▶ AI 서버
                     │
                     ├─ (참조) rules ◀─ profile
                     ├─ (참조) recommend ◀─ rules
                     └─ (선택) llm_extract
```

범례: 🟢 데이터 파이프라인(유효) · 🔷 참조·검증용(런타임은 서버) · ❓ 분담 미정

---

## 🟢 fetch_policies.py — 수집

| | |
|---|---|
| 입력 | 온통청년 OpenAPI (`getPlcy`), 환경변수 `YOUTH_API_KEY` |
| 출력 | `data/policy/raw/busan_policies.json` (534건, 원본 60필드) |

- 부산 16개 시군구 법정동 코드를 `zipCd`에 콤마로 지정해 호출 (앞 2자리 prefix는 무시됨)
- `pageSize=100`으로 페이지네이션, 전 페이지 순회
- `plcyNo` 기준 중복 제거 (페이지 경계 중복 대비)
- 인증 파라미터는 **`apiKeyNm`** — 문서 없이 실측으로 확인 (`serviceKey` 등은 400)

---

## 🟢 preprocess.py — 전처리 파이프라인

| | |
|---|---|
| 입력 | `raw/busan_policies.json`, `codebook.json` |
| 출력 | `clean/policies_clean.json` (마감제외 175건 + `_norm` 부착) |

**구조**: `STEPS = [(이름, 함수)]` 리스트를 `run()`이 순서대로 실행. 각 스텝은
`(records, ctx) → records` 순수 함수. 원본 60필드는 건드리지 않고 `_norm`에만 쌓는다.
`ctx`는 공유 자원 `{today, codebook, log}`.

### 스텝 1 — 마감필터 `filter_closed`

닫힌 정책을 리스트에서 제거한다. 판정은 `is_closed(r, today)`:

| 조건 | 판정 |
|---|---|
| `aplyPrdSeCd == 0057002` (상시) | 열림 |
| `aplyPrdSeCd == 0057003` (마감 명시) | **마감** |
| `0057001`(특정기간) + `bizPrdEndYmd < 오늘` | **마감**(기간경과) |
| 특정기간인데 종료일 없음 | 열림 (마감 증거 없음 → 남김) |

- **명시 마감 221 + 기간경과 138 = 359건 제외** → 175건
- 종료일 없는 65건은 살린다 (마감이라 단정 못 함)
- `today`는 `date.today()` — **실행일 기준**이라 재실행하면 그날로 다시 걸러짐

### 스텝 2 — 요건정규화 `normalize`

각 정책에 `_norm` 블록을 부착. 코드로 판정 가능한 요건을 규칙엔진이 읽을 형태로 편다.

| `_norm` 키 | 처리 함수 | 내용 |
|---|---|---|
| `상태` | `status_label` | 진행중 / 상시 / 시작전 / 기간미상 |
| `지역구분` | `norm_region` | zipCd 시도 prefix로 전국 / 부산한정 / 광역 |
| `대분류` | `norm_category` | `lclsfNm` 구분류 정규화 + 콤마 중복 제거 |
| `요건` | (아래) | 축별 정규화 요건 |
| `llm추출필요` | `llm_needed` | 자유서술에 소득·재산 조건이 숨었는가 |

**`요건` 축별 처리:**

- **연령** `norm_age` — `sprtTrgtMinAge/MaxAge`만 사용, **신뢰불가 플래그(`sprtTrgtAgeLmtYn`)는 무시**.
  둘 다 0/공백이면 `"ANY"`, 아니면 `{min, max}`
- **취업·학력·전공·혼인·특화** `norm_code_axis` — `CODE_AXES` 매핑대로 코드→라벨 디코드.
  콤마 split 후, **"제한없음" 코드가 있으면 `"ANY"`**, 없으면 라벨 리스트, 비었으면 `None`
  - 제한없음 코드가 축마다 다름: 취업 `0013010`, 학력 `0049010`, 전공 `0011009`, 혼인 `0055003`, 특화 `0014010`
- **소득** `norm_income` — `earnCndSeCd=무관`이고 서술에도 조건 없으면 `"ANY"`,
  아니면 `{"판정":"LLM필요"}`. **"무관"이어도 서술에 조건 있으면 LLM필요로** (정규식 `INCOME_RX`)

> **핵심 구분**: `"ANY"`(제한없음) ≠ `None`(정보없음). 이 구분이 가능/불가/정보부족
> **3분류의 기반**이다.

---

## 🟢 export_policies.py — 서버 핸드오프

| | |
|---|---|
| 입력 | `clean/policies_clean.json` |
| 출력 | `export/policies_export.json` (서버 ingest용 175건) |

- `to_card(r)`가 정제 레코드를 **AI 서버 정책카드 스키마**로 변환
  (`/v1/diagnose` 응답에서 관측한 키: plcyNo·plcyNm·대분류·중분류·키워드·설명·지원내용·
  소득기타·추가자격·제외대상·신청시작일·신청종료일·참고URL·신청URL)
- 매칭용 `요건`(정규화)·`지역구분`·`적용지역코드`·`llm추출필요`를 함께 실어
  서버 자격판정이 FINDINGS 규칙을 그대로 상속하게 함
- ⚠️ 최종 키명은 담당자와 확정 (관측 기반 초안)

---

## 🔷 rules.py — 규칙엔진 (참조·검증용)

| | |
|---|---|
| 입력 | 통합 `Profile`, `clean/policies_clean.json`의 `_norm.요건` |
| 출력 | 정책별 `{판정, 불충족축, 정보부족축, 축별근거}` |

**축 판정**(각 `(판정, 근거)` 반환): `PASS`/`FAIL`/`UNKNOWN`

| 함수 | 축 | 로직 |
|---|---|---|
| `judge_age` | 연령 | ANY→통과, 미입력→UNKNOWN, min≤나이≤max |
| `judge_membership` | 취업·학력·전공·혼인 | ANY/None→통과, 미입력→UNKNOWN, 값∈요건 |
| `judge_special` | 특화 | 프로필 특화목록과 요건의 **교집합** 있으면 통과 |
| `judge_income` | 소득 | ANY→통과, `LLM필요`→UNKNOWN (추출 전이라 미해석) |
| `judge_region` | 지역 | 전국→통과, 미입력→UNKNOWN, 코드∈zipCd |

**종합 판정** `judge_policy`:
```
하나라도 FAIL          → 불가
아니고 하나라도 UNKNOWN → 정보부족
전부 PASS              → 가능
```

- 유형(6분류)은 자격판정에 쓰지 않는다 (정렬 전용, recommend에서)
- 축별 근거를 남겨 "왜 이 결과인지" 설명 가능

---

## 🔷 profile.py — 입력 어댑터 (참조·검증용)

| | |
|---|---|
| 입력 | 라이트 폼(7문항) 또는 KCB 행(42~43열) |
| 출력 | 통합 `Profile` (8축 + `_source`) |

- `from_light(form)` — 폼 7문항을 codebook 라벨과 정렬해 매핑. 성별 여성→특화 "여성" 추가
- `from_kcb(row, form)` — KCB로 연령·연소득(천원→만원)·지역·성별 선채움 후, 폼이 있으면
  USER축(혼인·직업군·학력·특화)을 채우고 **겹치면 폼이 덮어씀**
- `_source`로 각 축 출처(USER/KCB/None) 태깅 → 규칙엔진 "정보부족" 근거
- **직업군 코드북 우회**: KCB 코드(420)는 매핑 불가 → `KCB_코드북없음`으로 두고 폼이 덮음

> 연령버킷(KCB 5세 구간 → 단일 나이)과 성별코드(1남/2여)는 TODO로 남음.

---

## 🔷 recommend.py — 추천 (참조·검증용)

| | |
|---|---|
| 입력 | `Profile`, 정책들, 유형(선택), `top_k` |
| 출력 | `{추천, 그룹, 요약}` |

- `judge_all`로 판정 → **불가 제외**, 가능+정보부족만 남김
- `score(policy, 유형)` — `TYPE_WEIGHTS`(유형별 부스트, **정렬 전용 STUB**) +
  상태·조회수·부산밀착 tie-break
- 가능 우선, 그 안에서 점수순 정렬 → 대분류별 그룹핑
- **유형 있을 때(정밀)만** top-K 추천 노출, 라이트는 그룹핑만

---

## ❓ llm_extract.py — 소득요건 추출 계약 (분담 미정)

| | |
|---|---|
| 입력 | `clean`의 flagged 29건 자유서술 |
| 출력 | `llm/extract_input.json` → (LLM) → `extract_output.json` → `_extracted` 병합 |

- `build_input()` — flagged 정책의 원문(소득기타·추가자격·제외대상·지원내용)을 배치로
- `PROMPT` + `EXTRACTION_SCHEMA` — 본인/원가구 소득·재산·무주택·중복수혜를 정규화 추출.
  **판정주체**(KCB/USER/**NEVER**) 명시 → 원가구 소득은 NEVER라 자동 정보부족
- `merge()` — LLM 출력(`{plcyNo: _extracted}`)을 clean에 병합
- ⚠️ **서버 ollama가 직접 추출하면 이 모듈은 불필요** (담당자 확인)

---

## 데이터 산출물 요약

| 파일 | 생성자 | 내용 | 커밋 |
|---|---|---|---|
| `raw/busan_policies.json` | fetch | 원본 534건 | ✗ gitignore |
| `clean/policies_clean.json` | preprocess | 정제 175건 + `_norm` | ✓ |
| `export/policies_export.json` | export | 서버 스키마 175건 | ✓ |
| `llm/extract_input.json` | llm_extract | LLM 입력 29건 | ✓ |
| `codebook.json` | 수작업 | 코드→라벨 매핑 | ✓ |
