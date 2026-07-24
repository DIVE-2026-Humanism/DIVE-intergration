# DIVE 2026 부산 청년 진단·정책추천

부산 청년에게 신청 가능한 정책 전체를 규칙으로 찾고, 정밀 진단에서는 실제 KCB 데이터로 `경제적 취약 청년` 또는 `경제적 안정 청년`을 판정해 로컬 LLM이 정책 우선순위를 추천한다. OpenAI 등 외부 LLM API는 사용하지 않는다.

```text
라이트: 기본정보 8개 → 규칙 필터 → 통과 정책 전체
정밀:   기본정보 8개 + KCB 43개 필드 → CatBoost 2유형·점수
                                        └→ 통과 정책 상위 12개 → Ollama 추천 3~5개
                                        └→ 1인가구이면 상세 소비피드백 추가
```

## 시스템 아키텍처

![DIVE 시스템 아키텍처](diagram.png)

## 공개 API

- 기본 주소: `https://ai.beceleb.org`
- Swagger: `https://ai.beceleb.org/docs`
- OpenAPI: `https://ai.beceleb.org/openapi.json`
- 입력 메타데이터: `https://ai.beceleb.org/v1/meta`

공개 주소는 Cloudflare Tunnel을 통해 AI 서버의 `http://127.0.0.1:8000`으로 연결된다. 별도 인증 모드는 없으므로 `Authorization` 헤더 없이 JSON API를 호출한다. 분리된 프론트·백엔드 구성에서는 백엔드가 이 공개 주소를 호출하는 방식을 권장한다.

## 1. 새 서버에서 실행

필수 환경은 Git, Docker Engine, Docker Compose다.

```bash
git clone https://github.com/DIVE-2026-Humanism/DIVE-intergration.git
cd DIVE-intergration/'LLM service'
cp .env.example .env
```

`.env`에서 PostgreSQL 비밀번호를 변경한다.

```dotenv
POSTGRES_PASSWORD=change-this-postgres-password
```

`DIVE_CORS_ORIGINS=*`로 프론트·백엔드 서버에서 바로 호출할 수 있다.

CPU로 실행:

```bash
docker compose up -d --build
```

NVIDIA GPU로 실행:

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

GPU 실행에는 NVIDIA Container Toolkit이 필요하다. 설치 확인은 다음 명령으로 한다.

```bash
docker run --rm --gpus all ubuntu:24.04 nvidia-smi
```

최초 실행 시 `qwen3:8b` 약 5.2GB를 내려받아 `dive-qwen3:8b` 모델을 생성한다. 이후에는 Docker 영구 볼륨을 사용하므로 다시 받지 않는다. 모델 다운로드가 실패해도 라이트 정책 목록과 정밀 규칙기반 대체추천은 동작한다. 인터넷 없이 시연하려면 `.env`의 `DIVE_LLM_ENABLED=false`로 두거나 행사 전에 모델 볼륨을 준비한다.

```bash
docker compose logs -f ollama-init ai-api
curl http://127.0.0.1:8000/health/ready
```

실제 데이터 모델과 Ollama까지 모두 준비된 응답:

```json
{"status":"ok","components":{"postgresql":true,"ollama_model":true,"classification_model":true},"capabilities":{"light_diagnosis":true,"light_rule_policy_list":true,"precise_classification":true,"llm_recommendation":true,"rule_fallback_recommendation":true,"precise_llm_recommendation":true,"precise_rule_fallback":true}}
```

모델 또는 Ollama가 없고 PostgreSQL만 정상이면 HTTP 200과 `status=degraded`를 반환한다. PostgreSQL이 없을 때만 HTTP 503이다. `components`와 `capabilities`를 보고 시연 가능한 기능을 판단한다.

2026-07-24 현재 공개 서버에는 연결 시험용 합성 모델이 있어 `status=ok`, `classification_model=true`다. 공개 라이트·정밀 진단과 GPU 로컬 LLM 연동은 동작하지만 `artifacts/model_provenance.json`의 `data_kind=synthetic_test`인 테스트 아티팩트다. 이 모델의 유형·점수와 검증성능은 실제 성능으로 해석하거나 최종 시연에 사용하면 안 되며, 대회 당일 공식 KCB 데이터로 반드시 다시 학습한다.

## 2. 컨테이너 구성

| 서비스 | 역할 | 외부 노출 |
|---|---|---|
| `postgres` | 정책 원천 313건과 코드 라벨 69건 저장 | 기본값 `127.0.0.1:5432` |
| `ollama` | `dive-qwen3:8b` 로컬 추론 | 기본값 `127.0.0.1:11434` |
| `ollama-init` | 모델 다운로드·ID 검증·프로젝트 모델 생성 후 종료 | 없음 |
| `ai-api` | 진단·정책·추천 HTTP API | 기본값 `0.0.0.0:8000` |

`ai-api`는 `ollama-init` 완료를 기다리지 않는다. 정밀 진단에서 Ollama가 늦거나 실패하면 요청당 최대 20초 이내에 규칙 기반 추천으로 전환하고, 이후 30초 동안 실패한 LLM 재호출을 막는다. 라이트 진단은 처음부터 LLM을 호출하지 않는다.

`health/ready`의 `ollama_model=true`는 모델이 Ollama에 등록됐다는 뜻이다. 제한시간 안에 추천 생성이 완료된다는 보장은 없으므로 실제 정밀 응답의 `추천방식`도 확인한다. 현재 RTX 4080에서 `dive-qwen3:8b`가 `100% GPU`로 로드되며, 예열 후 공개 정밀 진단은 약 7.4초에 `추천방식=로컬LLM`으로 완료됐다.

PostgreSQL과 Ollama 데이터는 각각 `postgres_data`, `ollama_data` 영구 볼륨에 저장된다. `docker compose down`만 실행하면 데이터는 유지된다.

```bash
docker compose down
```

`docker compose down -v`는 DB와 다운로드한 LLM을 모두 삭제하므로 초기화가 명확히 필요할 때만 사용한다.

## 3. 분리된 서버에서 연동

권장 운영 구조는 다음과 같다.

```text
[프론트·백엔드 서버]
          │ HTTPS
          ▼
https://ai.beceleb.org
          │ Cloudflare Tunnel
          ▼
[AI 서버 127.0.0.1:8000]
          ├ PostgreSQL
          └ Ollama/GPU
```

- PostgreSQL은 AI 서버 측에 한 번만 구축한다.
- 프론트엔드·백엔드 서버마다 PostgreSQL을 복제하지 않는다.
- 프론트 또는 백엔드는 AI 서버 주소만으로 호출할 수 있다.
- DB 5432와 Ollama 11434는 외부에 공개하지 않는다.
- 공개 호출에는 포트 번호 없이 `https://ai.beceleb.org`를 사용한다.
- Cloudflare Tunnel의 origin은 TLS가 아닌 `http://127.0.0.1:8000`이다.
- `cloudflared`는 AI 서버의 systemd 서비스로 계속 실행한다.

최종 제출 때 한 서버에 합치더라도 코드는 바뀌지 않는다. 같은 Compose 네트워크에서 프론트·백엔드가 `http://ai-api:8000`을 호출하거나, 현재 Compose만 실행하고 백엔드가 `http://127.0.0.1:8000`을 호출하면 된다.

## 4. API 호출

```bash
curl https://ai.beceleb.org/health/live
curl https://ai.beceleb.org/health/ready
curl https://ai.beceleb.org/v1/meta
```

```bash
curl -X POST https://ai.beceleb.org/v1/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "light",
    "user_inputs": {
      "성별": "여",
      "결혼여부": "미혼",
      "연소득": 30000000,
      "직업군": "재직자",
      "학력": "대학 졸업",
      "특화": [],
      "사는곳": "중구",
      "나이": 27
    }
  }'
```

- `light`: 성별·결혼여부·연소득·직업군·학력·특화조건·거주지·나이로 규칙 필터만 수행한다. `지원가능정책` 전체를 반환하며 LLM, 유형, 점수는 사용하지 않는다.
- `precise`: 같은 기본정보와 공식 KCB 43개 필드를 받는다. 가구원수와 관계없이 CatBoost 분류와 정책 추천을 수행한다.
- `나이`는 필수 만 나이다. 정책 연령 조건과 정밀진단 연령 기준 모두 사용자가 입력한 나이를 사용한다.
- KCB의 `연령대`는 공식 필드로 받지만, 처리할 때 `user_inputs.나이`를 해당 KCB 연령구간으로 변환해 적용한다.
- `지원가능정책`에는 모든 규칙 조건을 통과한 정책만 들어간다. 조건을 통과하지 못하거나 현재 정보로 확정할 수 없는 정책은 응답에서 제외한다.
- `추천정책`은 정밀 진단에만 있다. `PASS` 후보를 규칙으로 최대 12개까지 줄이고 정책명 중복을 제거한 뒤 한 번만 LLM에 전달한다. 후보 밖 ID는 폐기하고 정책명·판정근거·URL은 서버 원문에서 다시 결합한다.
- 정밀 진단에서 Ollama 장애 또는 빈 응답 시 통과 정책만 규칙 기반으로 추천한다. 통과 정책이 없으면 `추천상태=자격일치정책없음`을 반환한다.
- `추정가구원수=1`이면 일반 소비 비교 결과를 바탕으로 1인가구 상세 피드백을 추가한다. 1이 아니어도 정밀진단과 추천은 정상 수행한다.
- 모델 아티팩트가 없는 precise 요청은 HTTP 응답 자체는 제공하되 `진단상태=부분완료`, `분류상태=사용불가`, `모델결과=null`이다.

Swagger는 `https://ai.beceleb.org/docs`, 기계 판독 계약은 `https://ai.beceleb.org/openapi.json`, 입력 enum과 KCB 필수 컬럼은 `https://ai.beceleb.org/v1/meta`에서 확인한다.

요청·응답과 상태 처리 방법은 [AI 서버 연동 가이드](reports/integration_guide.md)를 참고한다.

6유형 분류 이유와 정책 우선순위의 발표용 설명은 [AI 유형 분류·정책 추천 모델 가이드](reports/llm_model_guide.md)를 참고한다.

배포 후 연동 점검:

```bash
.venv/bin/python scripts/smoke_api.py --base-url https://ai.beceleb.org
```

공식 KCB 한 행 JSON이 있으면 `--kcb-json sample.json`을 추가한다. JSON에는 모델 입력 42개와 `추정가구원수`를 각각 키로 넣으며 추가 공식 컬럼도 허용한다. 정확한 필드명은 `/v1/meta`, `/openapi.json`, [연동 가이드](reports/integration_guide.md)를 기준으로 한다. 도구는 원문 대신 상태·정책 그룹 수·추천 ID만 출력한다.

AI 서버 자체에서 Tunnel을 거치지 않고 확인할 때만 `--base-url http://127.0.0.1:8000`을 사용한다. 진짜 외부 연결 검증은 프론트·백엔드가 배포된 다른 서버에서 공개 주소로 실행한다.

## 5. PostgreSQL 정책 DB

AI API가 시작할 때 `Dataset/busan_policies.json`과 `codebook.json`을 PostgreSQL에 자동 적재한다. 적재는 advisory lock과 단일 트랜잭션을 사용하며 재실행해도 중복되지 않는다.

수동 적재:

```bash
docker compose run --rm ai-api python -m src.policy_db.ingest
```

건수 확인:

```bash
docker compose exec postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) FROM busan_policies;"'
```

정책의 직업·학력·특화·지역 코드는 PostgreSQL `TEXT[]`로 저장하고 GIN 인덱스로 검색한다. 자유문장과 원본 정책은 `JSONB`로 보존한다.

외부 관리형 PostgreSQL을 사용할 때는 AI API 컨테이너에 `DIVE_DATABASE_URL`을 전달하면 된다. 프론트·백엔드가 DB에 직접 접속할 필요는 없다.

## 6. LLM 모델 재현 방식

5.2GB 모델 가중치는 GitHub 저장소에 직접 커밋하지 않는다. 대신 재현에 필요한 다음 항목을 저장소에 포함했다.

- [Modelfile](models/Modelfile): 컨텍스트와 생성 파라미터
- [manifest.json](models/manifest.json): 기반 모델명, 검증 모델 ID, 양자화, 크기
- `ollama-init`: clone 후 모델을 자동 다운로드하고 ID가 다르면 실패 처리
- `ollama_data`: 한 번 받은 모델을 영구 보관

인터넷이 제한된 해커톤 서버라면 행사 전에 한 번 Compose를 실행해 모델 볼륨을 준비해야 한다. 기반 모델이나 ID를 변경하려면 `.env`, `models/Modelfile`, `models/manifest.json`을 함께 변경하고 다시 검증한다.

## 7. KCB 모델 학습

### 7.1 현재 연결 시험용 합성 모델

샘플 Excel의 46개 컬럼 정의를 그대로 사용해 1,500행의 테스트 데이터를 만들고 CatBoost 아티팩트까지 생성할 수 있다.

```bash
.venv/bin/python scripts/build_synthetic_test_model.py --overwrite
```

- CSV: `Dataset/KCB_테스트_합성데이터.csv`
- 데이터 생성 명세: `Dataset/KCB_테스트_합성데이터.manifest.json`
- 정밀 호출 샘플: `Dataset/KCB_테스트_샘플.json`
- 모델 출처: `artifacts/model_provenance.json`
- 기본 생성량: V1~S3 목표 유형별 250행, 총 1,500행

CSV와 모델 아티팩트는 Git에 포함되지 않는다. 이는 API·학습·GPU LLM 연결 시험 전용이며 실제 성능이나 경제상태 판단에 사용할 수 없다. 합성 규칙을 재현하므로 검증 점수가 비정상적으로 높게 나오는 것이 정상이다.

```bash
.venv/bin/python scripts/smoke_api.py \
  --base-url https://ai.beceleb.org \
  --kcb-json Dataset/KCB_테스트_샘플.json
```

### 7.2 대회 당일 실제 KCB 데이터 학습

최종 모델의 학습과 점수 계산에는 합성·mock 데이터를 사용하지 않는다.

1. 대회 당일 파일을 `Dataset/KCB_공식데이터.csv`로 저장한다.
2. 데이터 계약을 검사한다.
3. 실제 데이터로 학습·검증·추론한다.

```bash
docker compose run --rm ai-api python -m src.run --stage profile
docker compose run --rm ai-api python -m src.run --stage all
jq . artifacts/model_provenance.json
```

마지막 출력의 `data_kind`가 `official_kcb`, `do_not_use_for_production`이 `false`인지 확인한다. 기본 학습 명령은 합성 모델과 출처 파일을 실제 데이터 기반 산출물로 덮어쓴다.

학습 결과는 호스트의 `artifacts/`에 저장된다.

- `model.cbm`: 내부 V1~S3 세부클래스를 학습한 CatBoost 모델
- `quantiles.json`: 실제 데이터 기반 분기 기준
- `calibration.json`: OOF 확률 보정값
- `credit_benchmarks.json`: 신용 비교 기준
- `metrics.json`: 교차검증 결과
- `model_provenance.json`: 공식·합성 데이터 구분과 모델 SHA-256

위 파일이 없으면 `precise`의 유형·점수는 `null`, `분류상태=사용불가`가 되지만 PostgreSQL 정책 조회와 정밀 규칙기반 대체추천은 계속된다. 운영 전에는 실제 데이터로 학습해 세 파일을 반드시 준비하며, 임의 유형이나 점수를 만들지 않는다.

### 실제로 사용하는 비교 데이터

| 지표 | 현재 실제 입력 | 사용 방식 |
|---|---|---|
| 연령별 연소득·카드소비 | `Dataset/개인소득_및_카드소비_*.csv`의 2023 부산 청년 값 | 소득과 월 환산 카드소비의 또래 격차 계산 |
| 연령별 대출잔액 | `Dataset/개인_가계대출_*.csv`의 2023 부산 청년 채무보유자 값 | 관측 가능한 대출이 있는 경우만 비교 |
| 연령별 신용평점 | 대회 당일 KCB 부산 청년 표본으로 생성한 `credit_benchmarks.json` | Thin Filer를 제외하고 학습 후에만 비교 |
| 지역별 월세 | 현재 연결된 검증 데이터 없음 | 숫자와 격차를 표시하지 않음 |

구군별 소득 CSV 값은 연령과 교차된 통계가 아니므로 청년 개인의 “지역+연령 평균소득”으로 사용하지 않는다. 지역별 월세는 국토교통부 전월세 실거래 원자료 등으로 주택유형·기간·구군 기준을 확정해 만든 CSV가 연결된 뒤에만 표시한다.

## 8. 로컬 개발과 테스트

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
cp .env.example .env
docker compose up -d postgres
```

PostgreSQL 통합 테스트를 포함해 실행한다.

```bash
export DIVE_TEST_DATABASE_URL="postgresql://dive:YOUR_PASSWORD@127.0.0.1:5432/dive"
.venv/bin/python -m pytest -q
.venv/bin/python -m pyflakes src tests scripts
```

GitHub Actions도 PostgreSQL 18 서비스와 함께 동일 테스트를 실행한다.

유형 분기 조건, 점수, DB 스키마와 코드별 역할은 [구현 상세 문서](reports/implementation_details.md)에 정리되어 있다.
