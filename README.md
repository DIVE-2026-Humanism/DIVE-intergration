# DIVE-intergration

DIVE 2026 서비스 통합 — 모노레포 제안 구조

## 폴더 트리

```
DIVE-intergration/
│
├── apps/                       # 사용자 대면 (배포 단위)
│   ├── web/                    프론트 — 라이트/정밀 진단 화면
│   └── backend/                Node — /v1/diagnose 호출, 세션·KCB샘플 로드
│
├── services/                   # 독립 배포 백엔드 서비스
│   └── ai-server/              FastAPI + Ollama + PostgreSQL
│                               (진단·6유형분류·추천, = ai.beceleb.org)
│
├── packages/                   # 라이브러리·파이프라인 (직접 배포 X)
│   ├── policy-pipeline/        ★ 정책 데이터 파이프라인 (현재 이 레포)
│   │   └── src/                수집①·전처리②·export③·규칙/추천 (참조·검증용)
│   └── model/                  6유형 분류 모델 (DIVE-typepredict)
│                               KCB → CatBoost → predictions.jsonl
│
├── contracts/                  # ⭐ 공유 계약 (생산자↔소비자 스키마 단일 진실)
│
├── data/                       # 공유 데이터셋 (큰 파일 gitignore)
│   ├── policy/
│   │   ├── raw/                원본 534건 (gitignore)
│   │   ├── clean/              정제 175건 + _norm
│   │   ├── export/             서버 ingest용 175건
│   │   └── llm/                LLM 추출 입출력
│   ├── kcb/                    KCB 합성데이터 (gitignore, 반출금지)
│   └── external/               소득·전월세·인구 xlsx
│
├── docs/                       # 통합 문서 (MODULES / FINDINGS / FIELDS / STATUS)
│
├── meeting/                    # 브리프·기획·아키텍처
│   └── idea/                   아키텍처 다이어그램, 연동가이드
│
└── .github/workflows/          # 경로별 CI (바뀐 패키지만)
```

## 핵심 원칙

- **apps** = 사용자 대면 배포 / **services** = 독립 백엔드 / **packages** = 배포 안 되는 라이브러리
- **contracts/** = 스키마 단일 진실. export 생산자(policy-pipeline)와 소비자(ai-server)가
  같은 파일을 봐서 스키마 드리프트 방지 (15 vs 175 같은 사고 예방)
- **data/** = 공유 (kcb는 model·ai-server·pipeline 셋 다 사용)
- 폴리글랏이라 Nx/Turborepo 강제 안 함 → 최상위 Makefile + 언어별 기존 도구
