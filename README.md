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
├── LLM service/                # LLM 서비스 (진단·6유형분류·추천)
│
├── data/                       # 공유 데이터셋 (큰 파일 gitignore)
│   ├── policy/
│   │   ├── raw/                원본 데이터
│   │   └── clean/              정제 데이터
│   ├── kcb/                    KCB 합성데이터 (gitignore, 반출금지)
│   └── external/               외부 데이터 (소득·전월세·인구 xlsx)
│
├── meeting/                    # 회의내용정리·기획·아키텍처
│
└── .github/workflows/          # 경로별 CI (바뀐 패키지만)
```

## 핵심 원칙

- **apps** = 사용자 대면 배포
- **LLM service** = 진단·분류·추천 백엔드
- **data/** = 공유 데이터셋

## LLM 서비스 실행

```bash
git clone https://github.com/DIVE-2026-Humanism/DIVE-intergration.git
cd DIVE-intergration/'LLM service'
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health/ready
```

GPU 서버에서는 마지막 실행 명령을 다음과 같이 바꾼다.

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

상세 사용법은 [`LLM service/README.md`](<LLM service/README.md>), 외부 백엔드 연동은 [`LLM service/reports/integration_guide.md`](<LLM service/reports/integration_guide.md>)를 참고한다.
