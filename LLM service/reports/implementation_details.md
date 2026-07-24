# DIVE 2026 구현 상세

## 1. 서비스가 하는 일

이 프로젝트는 부산 청년에게 신청 가능한 정책을 찾아 보여주는 AI API다.

```text
라이트 진단
8개 기본정보 → 정책 조건 필터 → 통과 정책 전체 표시

정밀 진단
8개 기본정보 + KCB 43개 필드 → 사용자 유형·점수·소비분석
                               → 신청 가능 정책 전체 → 로컬 LLM 추천 3~5개
                               → 1인가구이면 상세 소비피드백 추가
```

화면에 보여주는 사용자 유형은 다음 두 개뿐이다.

- `경제적 취약 청년`
- `경제적 안정 청년`

V1~V3, S1~S3는 모델을 학습하고 결과를 추적하기 위한 내부 세부클래스다. 화면용 사용자 유형과 혼동하지 않는다.

## 2. 라이트 진단과 정밀 진단

### 2.1 라이트 진단

필수 입력은 다음 8개 그룹이다.

1. 성별
2. 결혼 여부
3. 연소득
4. 직업군
5. 학력
6. 특화조건: 장애인, 기초생활수급자, 한부모가정, 군인
7. 사는 곳: 부산 구·군
8. 나이: 만 나이

라이트 진단은 다음 원칙을 지킨다.

- 정책 자격은 규칙으로만 판단한다.
- 모든 조건을 통과한 정책만 `지원가능정책`에 대분류별로 반환한다.
- 통과하지 못하거나 현재 정보로 확정할 수 없는 정책은 응답에서 제외한다.
- LLM을 호출하지 않는다.
- KCB 금융정보가 없으므로 사용자 유형과 점수를 만들지 않는다.
- `추천정책=[]`, `추천상태=미사용`이다.

### 2.2 정밀 진단

서버가 준비한 공식 KCB 한 행을 `kcb_record` 안에 43개 필드로 나누어 전달한다. 하나의 문자열이나 배열로 보내지 않는다.

정밀 진단은 다음 순서로 동작한다.

1. 사용자가 입력한 만 나이를 KCB 연령구간으로 바꾸어 KCB의 `연령대` 대신 적용한다.
2. 실제 KCB 데이터로 학습한 CatBoost로 사용자 유형과 점수를 계산한다.
3. 소득·카드소비·대출·신용을 실제 비교통계와 비교한다.
4. 라이트와 같은 규칙으로 통과 정책 전체를 구한다.
5. 통과 정책을 규칙점수로 최대 12개까지 줄인다.
6. 줄인 후보만 로컬 LLM에 전달한다.
7. 후보 안에서 최종 3~5개를 추천하고 서버 원문으로 정책 ID·이름·URL을 다시 검증한다.
8. `지원가능정책`에는 추천 여부와 관계없이 통과 정책 전체를 별도로 반환한다.
9. `추정가구원수=1`이면 일반 소비비교를 이용한 1인가구 상세 피드백을 추가한다.

가구원수가 1이 아니어도 분류와 추천을 동일하게 수행한다. `추정가구원수`는 정밀진단 대상자를 탈락시키는 필터가 아니다.

## 3. 실행 방법

### 3.1 Docker로 전체 실행

```bash
git clone https://github.com/DIVE-2026-Humanism/DIVE-intergration.git
cd DIVE-intergration/'LLM service'
cp .env.example .env
```

`.env`에서 PostgreSQL 비밀번호를 변경한다.

```dotenv
POSTGRES_PASSWORD=충분히-긴-비밀번호
```

프론트·백엔드 서버에서 AI 서버 주소만으로 호출한다.

CPU 실행:

```bash
docker compose up -d --build
```

NVIDIA GPU 실행:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

상태 확인:

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
docker compose logs --tail=100 ai-api ollama-init
```

Ollama가 아직 준비되지 않아도 라이트 정책 목록과 정밀 규칙기반 대체추천은 동작한다. PostgreSQL이 준비되지 않으면 정책 원천을 조회할 수 없으므로 readiness는 HTTP 503이다.

### 3.2 공개 HTTPS와 외부 서버 연결

현재 공개 주소는 `https://ai.beceleb.org`다.

```text
프론트·백엔드 서버
→ https://ai.beceleb.org
→ Cloudflare Tunnel
→ AI 서버의 http://127.0.0.1:8000
→ PostgreSQL·Ollama
```

Cloudflare에는 AI API만 공개한다. PostgreSQL 5432와 Ollama 11434는 loopback 주소로 유지하며 프론트·백엔드 서버에 같은 DB나 LLM을 따로 구축하지 않는다. Tunnel origin은 `http://127.0.0.1:8000`이며, FastAPI origin이 HTTP이므로 `https://localhost:8000`으로 설정하면 502가 발생한다. `cloudflared`는 AI 서버의 systemd 서비스로 계속 실행한다.

호출에는 별도 인증 헤더가 없다. 외부 서버는 다음 주소만 설정한다.

```dotenv
DIVE_AI_BASE_URL=https://ai.beceleb.org
```

2026-07-24 실제 공개 경로 점검 결과는 다음과 같다.

| 항목 | 결과 | 의미 |
|---|---|---|
| 외부 `/health/live` | HTTP 200, `status=ok` | DNS·TLS·Tunnel·API 연결 정상 |
| 공개 라이트 진단 | HTTP 200, `진단상태=완료` | 규칙 기반 정책 목록 사용 가능 |
| PostgreSQL | `true` | 정책 조회 가능 |
| Ollama 모델 | `true` | 모델 등록 확인 |
| 분류 모델 | `true` | 합성데이터 기반 연결 시험 모델 로드 |
| 공개 정밀 진단 | `완료` | 합성 V3 행 분류와 정책 추천 완료 |

현재 Qwen3 8B는 RTX 4080에 `100% GPU`로 로드된다. 예열 후 공개 정밀 진단은 약 7.4초에 `추천방식=로컬LLM`으로 완료됐다. 현재 분류 아티팩트는 `data_kind=synthetic_test`인 연결 시험용이므로, `status=ok`여도 대회 제출용 모델이 준비됐다는 뜻은 아니다.

외부 호출에서 502가 발생하면 `docker compose ps`, 로컬 `/health/live`, `systemctl status cloudflared`, Tunnel origin 순으로 확인한다.

Python `urllib`의 기본 User-Agent는 Cloudflare Error 1010으로 차단될 수 있다. `scripts/smoke_api.py`는 `DIVE-TypePredict-Smoke/1.0`을 보내도록 구성되어 있으며, 다른 서버용 클라이언트도 식별 가능한 User-Agent를 사용한다.

### 3.3 테스트

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python -m pytest -q
.venv/bin/python -m pyflakes src tests scripts
```

배포된 API 연동 확인:

```bash
.venv/bin/python scripts/smoke_api.py --base-url https://ai.beceleb.org
.venv/bin/python scripts/smoke_api.py \
  --base-url https://ai.beceleb.org \
  --kcb-json sample_kcb_row.json
```

AI 서버 내부의 직접 호출을 검사할 때는 `--base-url http://127.0.0.1:8000`을 사용한다. 외부 연동 검사는 반드시 프론트·백엔드가 배포된 다른 서버에서 공개 주소로 실행한다.

### 3.4 합성데이터로 전체 연결 시험

샘플 Excel은 46개 실제 컬럼명이 담긴 데이터 정의서다. 테스트 빌더는 이 순서를 유지하고 V1~S3 규칙 신호가 서로 모순되지 않도록 소득·부채·연체·신용·소비값을 함께 생성한다.

```bash
.venv/bin/python scripts/build_synthetic_test_model.py --overwrite
```

기본값은 목표 유형별 250행, 총 1,500행과 테스트용 CatBoost 최대 250회 반복이다. 결과는 다음에 저장된다.

| 파일 | 내용 |
|---|---|
| `Dataset/KCB_테스트_합성데이터.csv` | 샘플 정의서 46개 컬럼과 테스트 표식 3개 |
| `Dataset/KCB_테스트_합성데이터.manifest.json` | seed·행수·SHA-256·목표/규칙 레이블 교차표 |
| `Dataset/KCB_테스트_샘플.json` | 공개 정밀 API 스모크 테스트용 V3 한 행 |
| `artifacts/model.cbm` | API 연결 시험용 CatBoost 모델 |
| `artifacts/model_provenance.json` | `synthetic_test`, 운영 사용 금지 표식 |

현재 생성된 1,500행은 전처리 탈락 0행이며 학습 확정 레이블은 V1 250, V2 150, V3 250, S1 250, S2 250, S3 250행이다. V2 나머지 100행은 학습 분위 기준상 유보돼 모델 학습에서 제외된다. 합성 규칙을 모델 피처로 재현하므로 CV Macro-F1 1.0은 실제 예측성능이 아니다.

### 3.5 대회 당일 실제 KCB 학습

최종 모델에는 합성·mock 데이터를 사용하지 않는다.

```bash
cp 대회에서_받은_파일.csv Dataset/KCB_공식데이터.csv
docker compose run --rm ai-api python -m src.run --stage profile
docker compose run --rm ai-api python -m src.run --stage all
jq . artifacts/model_provenance.json
```

`profile` 단계에서 필수 컬럼과 단위를 먼저 확인한다. 현재 계약은 모델용 42개 컬럼과 1인가구 맞춤 피드백용 `추정가구원수`까지 총 43개를 필수 검사하며, 공식 파일의 추가 컬럼은 허용한다. 학습 후 `model_provenance.json`이 `data_kind=official_kcb`, `do_not_use_for_production=false`인지 확인해야 합성 시험 모델 교체가 끝난 것이다.

## 4. 분류 모델

### 4.1 사용자 유형과 점수

내부 모델은 실제 KCB 데이터로 학습하는 하나의 `CatBoostClassifier` 다중분류 모델이다. 내부 확률은 V1~V3, S1~S3 여섯 개지만 화면용 결과는 두 개로 합친다.

```text
취약확률 = P(V1) + P(V2) + P(V3)
안정확률 = P(S1) + P(S2) + P(S3)

취약확률 > 안정확률  → 경제적 취약 청년
안정확률 ≥ 취약확률  → 경제적 안정 청년

유형점수 = 선택된 두 범주 확률 × 100
```

예를 들어 취약확률이 0.72라면 다음처럼 표시할 수 있다.

```text
당신은 경제적 취약 청년 유형입니다.
유형점수는 72점입니다.
```

이 점수는 실제 KCB 학습 결과의 보정 확률을 합산한 `분류 확신도`다. 미래 연체확률, 신용점수 또는 사람의 경제상태를 절대적으로 평가하는 점수가 아니다.

### 4.2 모델 입력 피처

원본 KCB에서 다음 12개 모델 피처를 만든다.

| 피처 | 의미 |
|---|---|
| `추정 연소득` | 현재 추정 연소득 |
| `REL_INC` | 같은 연령 평균소득 대비 소득 배수 |
| `INC_CHG` | 2년 전 대비 소득 변화율 |
| `DEBT_SUM` | 신용·주택담보·정책자금 대출잔액 합 |
| `REL_DEBT` | 같은 연령 채무보유자 평균 대비 부채 배수 |
| `DSR_PROXY` | 최근 12개월 상환액 ÷ 추정연소득 |
| 현금서비스 이용금액 | 최근 12개월 원본값 |
| `CARD_CONSUME_RATIO` | 신용·체크카드 소비 합 ÷ 추정연소득 |
| `DELQ_LEVEL` | 연체 없음·경미·중간·중대 0~3단계 |
| `신용평점` | Thin Filer이면 결측 처리 |
| `총대출건수` | 원본값 |
| `BUFFER` | 주택 순자산 완충 여부 |

### 4.3 레이블 분기 조건

학습용 내부 레이블은 다음 여섯 개다.

| 내부 코드 | 조건 요약 |
|---|---|
| V1 연체·채무조정 위험형 | 중대 연체가 있고 상환부담·현금서비스·낮은 소득·낮은 신용 중 하나 이상이 함께 나타남 |
| V2 상환 과부하형 | 연체가 없거나 경미하지만 상환부담이 높고, 또래 대비 부채가 높거나 현금서비스 부담이 큼 |
| V3 소득·생활 취약형 | 같은 연령 소득 1분위 이하이며 연체가 없고, 부채가 없거나 낮으면서 소비부담·현금서비스·소득감소 신호가 있음 |
| S1 상위소득 여유형 | 같은 연령 소득 5분위 이상이고 연체·현금서비스가 없으며 상환부담이 낮음 |
| S2 부채·자산 균형 관리형 | 부채가 또래 평균 이하이거나 자산 완충이 있고, 연체가 없으며 상환부담이 낮고 신용이 중간 이상임 |
| S3 무부채 건전형 | 대출·연체·현금서비스가 없고 소득이 또래 평균 이상이며 소비비율이 또래 기준 이하임 |

세부 숫자 경계는 임의 고정값이 아니라 실제 학습 데이터의 분위수와 로컬 외부통계 CSV를 사용한다. 핵심값 누락, 신호 충돌, 확인할 수 없는 부채잔액 등은 학습용 레이블에서 제외한다. 운영 추론에서는 학습된 모델 확률로 반드시 내부 코드 하나를 고르며 `규칙판정=유보`를 출력하지 않는다.

### 4.4 학습과 장애 처리

- 목적함수: `MultiClass`
- 클래스 불균형: `auto_class_weights=Balanced`
- 검증: 3-fold, 데이터에 따라 TimeSeriesSplit·GroupKFold·StratifiedKFold 선택
- 점수 보정: OOF 확률 기반 temperature scaling
- 모델 로딩: API 프로세스에서 최초 한 번 로드 후 캐시

실제 `model.cbm`, `quantiles.json`, `calibration.json`이 없으면 임의 점수를 만들지 않는다. 정밀 응답은 `진단상태=부분완료`, `분류상태=사용불가`, `모델결과=null`이지만 정책 목록과 규칙기반 대체추천은 계속 제공한다.

## 5. 정책 자격판정과 추천

`busan_policies.json`은 시작할 때 PostgreSQL로 적재한다. 프론트와 일반 백엔드는 DB에 직접 연결하지 않고 AI API만 호출한다.

정책 엔진은 내부적으로 각 정책을 다음처럼 처리한다.

| 내부 판정 | 처리 |
|---|---|
| `PASS` | `지원가능정책`에 포함하고 정밀추천 후보로 사용 |
| `UNKNOWN` | 자연어 조건이나 공식 의미를 확정할 수 없으므로 응답에서 제외 |
| `FAIL` | 입력 조건과 맞지 않으므로 응답에서 제외 |

API는 내부 판정 건수나 제외 정책을 별도 필드로 반환하지 않는다. 프론트·백엔드는 `지원가능정책`만 표시하면 된다.

정책 자격은 LLM이 결정하지 않는다. LLM은 정밀 진단의 확정 `PASS` 후보 안에서 순서와 설명만 만든다.

LLM 입력은 최대 12개 정책이며 정확한 금융금액과 전체 개인정보를 보내지 않는다. LLM이 후보 밖 정책 ID를 만들면 폐기한다. 정책명·URL·자격근거는 PostgreSQL 원문으로 다시 덮어써 환각을 막는다. 20초 제한, 동시 요청 1개, 30초 회로 차단을 사용하며 실패하면 정밀 진단에서 규칙기반 추천으로 대체한다.

## 6. 소비분석과 외부데이터

현재 코드가 실제로 읽고 계산에 사용하는 데이터만 아래에 적는다.

| 비교 지표 | 실제 파일/아티팩트 | 기준 |
|---|---|---|
| 연소득 | `개인소득_및_카드소비_20260717200619.csv` | 2023년 부산 청년 연령대 평균 |
| 월 카드소비 | 같은 CSV | 연간 카드이용금액을 12개월로 환산 |
| 대출잔액 | `개인_가계대출_20260717200650.csv` | 2023년 부산 청년 연령대 채무보유자 평균 |
| 신용평점 | 학습 시 생성하는 `credit_benchmarks.json` | KCB 부산 청년 표본, Thin Filer 제외 |

로컬 파일에서 읽는 값의 단위는 만원이고 KCB 금액은 천원이므로 비교 전에 `만원 × 10 = 천원`으로 변환한다.

구군별 소득 행은 연령과 교차된 값이 아니어서 `지역+연령 평균소득`으로 사용하지 않는다. 검증된 구군별 월세 CSV도 현재 없으므로 평균 월세 숫자나 퍼센트를 만들지 않는다. `consumption.rent_csv`에 기준이 확인된 파일이 연결된 경우에만 월세를 표시한다.

현재 확정된 소비피드백 방향은 외부데이터와 비교해 “또래 평균보다 몇 % 높거나 낮음”을 제공하는 것이다. `추정가구원수=1`이면 같은 비교 결과를 이용해 더 자세한 피드백을 제공한다. 구체적인 문구와 화면 책임은 아직 확정하지 않는다.

## 7. API 핵심 계약

```json
{
  "계약버전": "1.2",
  "진단모드": "light | precise",
  "진단상태": "완료 | 부분완료",
  "유형": "경제적 취약 청년 | 경제적 안정 청년 | null",
  "세부유형코드": "V1 | V2 | V3 | S1 | S2 | S3 | null",
  "유형점수": 72.0,
  "점수설명": "두 범주로 합산한 분류 확신도...",
  "지원가능정책": [],
  "추천정책": [],
  "추천상태": "미사용 | 완료 | 자격일치정책없음",
  "추천방식": "없음 | 로컬LLM | 규칙기반대체"
}
```

프론트·백엔드는 `/openapi.json`을 계약 원본으로 사용한다. 라이트에서는 `추천정책=[]`, 유형과 점수는 `null`이다. 정밀에서는 가구원수와 관계없이 분류하며 실제 모델 준비 상태에 따라 유형·점수가 제공된다.

## 8. 코드별 역할

| 파일 | 역할 |
|---|---|
| `config/config.yaml` | 데이터 경로, 필수 컬럼, DB·Ollama·소비분석 설정 |
| `src/api.py` | FastAPI, CORS, health/readiness, 연동 메타데이터 |
| `src/service.py` | 라이트·정밀 흐름 통합과 장애 격리 |
| `src/rule_engine.py` | 정책 조건 판정, 통과 정책 선별과 대분류 그룹핑 |
| `src/policy_db/schema.sql` | PostgreSQL 테이블과 인덱스 |
| `src/policy_db/ingest.py` | 정책 JSON·코드북을 PostgreSQL에 안전하게 적재 |
| `src/preprocess.py` | 숫자 변환, 센티널 처리, 청년·부산 필터 |
| `src/features.py` | 모델용 12개 피처와 보조값 계산 |
| `src/labeling.py` | V1~S3 학습용 내부 레이블 분기 |
| `src/train.py` | CatBoost 교차검증·학습·아티팩트 저장 |
| `src/calibration.py` | 모델 확률 보정 |
| `src/classify_service.py` | 단건 KCB 분류, 2유형·유형점수 계산, 모델 캐시 |
| `src/external.py` | 실제 외부통계 CSV 읽기와 설정값 검증 |
| `src/benchmarks.py` | 연령대 변환과 실제 KCB 신용평점 기준 생성 |
| `src/consumption.py` | 소득·소비·대출·신용·1인가구 상세 피드백 |
| `src/llm_recommend.py` | 정밀 후보 12개 축소, 로컬 LLM, 결과 검증, 대체추천 |
| `src/run.py` | profile·train·validate·infer CLI 진입점 |
| `scripts/smoke_api.py` | 다른 서버에서 API 계약과 대표 흐름 확인 |
| `scripts/build_synthetic_test_model.py` | 샘플 46컬럼 기반 테스트 데이터·모델 생성과 출처 표시 |
| `compose.yaml` | PostgreSQL·Ollama·AI API 통합 실행 |
| `tests/` | 계약·규칙·모델·소비·LLM·DB 회귀검사 |

## 9. 서버 구성 판단

분리 환경에서는 프론트·백엔드 서버가 `https://ai.beceleb.org`를 호출한다. Cloudflare Tunnel이 요청을 AI 서버의 `http://127.0.0.1:8000`으로 전달한다. PostgreSQL과 Ollama는 AI 서버에만 두며 다른 서버에 복제하지 않는다. 합쳐서 제출할 때는 같은 Compose 네트워크의 `http://ai-api:8000` 또는 AI 호스트의 `http://127.0.0.1:8000`으로 바꿀 수 있고 API 계약은 그대로 유지된다.
