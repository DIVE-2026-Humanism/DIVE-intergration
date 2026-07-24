# DIVE 2026 백엔드

부산 청년 1인가구 경제안정성 진단 · 정책 추천 API

## 아키텍처

```
React  →  FastAPI(이 repo, 얇은 relay)  →  ai-server(https://ai.beceleb.org, 모델팀 소유)
```

진단·6유형분류·정책매칭·LLM설명은 전부 ai-server가 처리한다. 이 backend는
`/api/meta`, `/api/diagnose`로 ai-server를 프록시하고, 정밀 진단일 때 KCB 샘플을
붙여주는 역할만 한다. 응답은 passthrough — ai-server가 준 필드를 그대로 전달한다.

## 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload
```

- Swagger: http://localhost:8000/docs
- OpenAPI 스펙: http://localhost:8000/openapi.json

## 현재 상태 (골격)

엔드포인트 배선과 relay 패턴만 잡혀 있다. 세부 로직은 내일 채운다.

| 영역 | 상태 |
|---|---|
| `/api/meta` | ai-server `/v1/meta` relay |
| `/api/diagnose` | ai-server `/v1/diagnose` relay, 정밀 모드는 `sampleId` → KCB 붙임 |
| KCB 샘플 | `services/kcb_samples.py`가 `app/data/kcb_samples.json`에서 로드 — `sample-01` 1건 있음 (출처: `meeting/integration_guide.md`, 상세는 `app/data/README.md`) |
| 에러 정규화 | 502/503 1회 재시도 후 `AppError`로 변환 |
| 테스트 | smoke test 1개만 (`tests/test_smoke.py`) |

## 구조

```
app/
  main.py              앱, CORS, 공통 에러 핸들러, /api/health
  config.py            환경변수 (AI_SERVER_BASE_URL 등)
  schemas/
    diagnosis.py        /api/diagnose 요청 스키마 (응답은 passthrough라 미타입화)
    common.py            에러 포맷 + AppError
  routers/
    diagnosis.py         POST /api/diagnose
    meta.py               GET /api/meta
  services/
    ai_client.py         ai-server httpx 클라이언트 (재시도·에러 정규화)
    kcb_samples.py        정밀 진단용 KCB 샘플 로더
```

## 남은 작업

- [ ] `app/data/kcb_samples.json`에 샘플 추가(`sample-02` 등) — 지금은 `sample-01` 1건뿐
- [ ] `/v1/meta`·`/v1/diagnose`의 실제 ai-server 응답으로 relay 검증 (지금은 mock으로만 확인)
- [ ] 직업군 등 코드북 확정되면 `schemas/diagnosis.py`의 `UserInputs` 갱신
- [ ] 카카오 로그인 목업

## 규약

- 응답 JSON은 ai-server 계약(한글 키) passthrough — 앱에서 재가공하지 않는다
- 에러: `{"error": {"code", "message", "field", "trace_id"}}`
- 인증 없음 (데모)
