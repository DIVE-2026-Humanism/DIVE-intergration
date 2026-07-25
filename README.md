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
├── hybrid/                     # ★ 진단 파이프라인 (채택) — 잠재 E1~E6 + 정책기준 + 문진
│
├── analysis/                   # 상류 모듈(정합성·로딩·분할·대체·파생) + 비교 실험 근거
│
├── LLM service/                # LLM 서비스 (정책 추천·LLM)
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
- **hybrid** = 경제 안정성 진단 (유형·점수·근거 산출)
- **LLM service** = 정책 추천·LLM
- **data/** = 공유 데이터셋

## 진단 파이프라인 실행

```bash
python -m hybrid.src.run --input "important data/(합성데이터)종합해커톤.csv" --outdir hybrid/outputs/ --seed 42
```

전수 10만 행 약 25초. 동일 시드 2회 실행 시 산출물이 바이트 단위로 동일하다.
상세는 [`hybrid/README.md`](hybrid/README.md), 비교 근거는 [`analysis/README.md`](analysis/README.md).

### 라벨 체계 (채택)

| 유형 | 명칭 | 대분류 | 평균 종합점수 |
|---|---|---|---:|
| E1 | 안정형 | 안정 | 82.3 |
| E2 | 주택대출형 | 안정 | 66.8 |
| E3 | 저부채형 | 안정 | 56.7 |
| E4 | 금융이력부족형 | 취약 | 45.4 |
| E5 | 대출부담형 | 취약 | 18.3 |
| E6 | 위기형 | 취약 | 9.9 |

- 사용자 진입은 **문진 7문항** (고용형태·소득·소비·상환·부채·이직·연체) — test accuracy 0.521 / macro F1 0.503
- 백엔드 전달 payload는 유형·종합점수·확신도·정책등급·플래그·판정근거를 함께 담는다
  (`hybrid/outputs/diagnosis_samples.json`)
- 정책 매칭은 백엔드 담당. 진단 측은 `flags`·`income.grade`를 제공한다

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

# ISSUE

1. ~~데이터 정제 합의점 찾기~~ → 정합성 26종 전수 검증으로 열 제거 7개 확정,
   보류 3열은 위반율 30% 기준 미달로 유지. 근거표는 `hybrid/outputs/consistency_report.md`.
2. **라벨 체계 통합** — `hybrid`(E1~E6)와 `LLM service`(S1~S3/V1~V3)가 병존한다.
   `hybrid`의 `major_class`(안정/취약)가 S/V 대분류와 대응하므로 기존 `/v1/diagnose` 계약을
   깨지 않고 연결할 수 있다. 세부 코드 통일 여부는 합의 필요.
3. **부스팅 사용 여부** — `method.md` §16-9는 설명 가능성을 이유로 부스팅 계열을 금지하는데
   `LLM service`는 CatBoost를 쓴다. 최종 수요자가 부산시 공무원인 점을 고려해 정리 필요.
