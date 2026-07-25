# analysis — method.md 구현체 · 상류 모듈 · 비교 실험 근거

> **역할 정리 (2026-07-26)**
> 최종 진단 파이프라인은 [`hybrid/`](../hybrid/README.md)를 채택했다. 이 디렉터리는 두 가지 역할로 남는다.
> 1. **상류 모듈 제공** — `consistency` · `load` · `split` · `impute` · `features`를 `hybrid`가 그대로 import한다.
> 2. **비교 실험 근거** — T1~T6(규칙 2×2) 방식의 산출물과 검증 리포트. hybrid 채택 사유의 대조군이다.
>
> T1~T6 라벨은 서비스에 쓰지 않는다. 외부 타당도(연령대 eta² 0.004, 자가여부 0.001)에서
> E1~E6(0.075 / 0.050)에 밀렸고 문진 재현력도 낮았다.

`method.md`(저장소 루트) 구현체. KCB 신용 마이크로데이터 10만 행을 입력받아
**6개 경제 계층 유형**으로 분류하고, 유형별 프로파일 · 검증 리포트 · **8문항 축소 분류기**를 산출한다.

## 실행

```bash
cd analysis
pip install -r requirements.txt
python -m src.run --input "../important data/(합성데이터)종합해커톤.csv" --outdir outputs/ --seed 42
```

- `--seed` 기본 42. 동일 시드로 2회 실행하면 결과가 동일하다.
- `--sample N` 은 스모크 테스트용 행 샘플. 전수 실행은 생략한다.
- 전수 실행 소요 약 30초(8코어 기준).

## 파이프라인 (method.md §17)

| STEP | 모듈 | 내용 |
|---|---|---|
| 0 | `consistency.py` | 논리 정합성 26종 전수 검증 → 확정 7열 즉시 제거, 보류 3열은 위반율 30% 초과 시 자동 추가 |
| 1 | `load.py` | 인코딩 폴백 · 센티널 `-99999999` → NaN + `__missing` 플래그 · 열 제거 |
| 2 | `split.py` | train 70 / valid 15 / test 15, stratify = 연령대 × 성별 |
| 3 | `impute.py` | [학습①] 전세가 결측 대체 (RF vs 구·군 중앙값 베이스라인) |
| 4 | `features.py` | 파생변수 (분모 0·NaN → NaN, 0으로 채우지 않음) |
| 5 | `residual.py` | [학습②] 신용평점 잔차 = 실제 − 예측. 신용평점 150(하한 절단) 행 학습 제외 |
| 6 | `scores.py` | 축 스코어. train 분위수 격자로 0~100 정규화, **PC1 ≥ 40% ? PCA가중 : 균등가중** |
| 7 | `segment.py` | T6 → T5 → 2×2 주 분류 → H flag. **실루엣 ≥ 0.25 ? GMM주도 : 규칙주도** |
| 8 | `reduced_model.py` | [학습③] 스크리닝 2문항(T5·T6 결정적 배정) + 8문항 DecisionTree(주) / LogisticRegression(비교군) |
| 9 | `anomaly.py` | [학습④] IsolationForest, T4 중복률 검증 |
| 10 | `validate.py` | 프로파일 · ANOVA + eta² · 교차표 · 시각화 |

## 산출물 (`outputs/`)

| 파일 | 내용 |
|---|---|
| `consistency_report.md` | 정합성 26종 결과 + 열 제거 결정 |
| `data_caveats.md` | 가정 · 한계 · 발제사 확인 필요 항목 |
| `fitted_params.json` | train 기준 분위수 격자 · 컷 · 가중치 · 구간 경계 (누수 방지 핵심, 실서비스 재사용) |
| `features_summary.csv` | 파생변수 기술통계 |
| `segments.csv` | 행별 유형 · 두 축 스코어 · H/R flag · 소득등급 · 고용형태 · 주요 파생변수 |
| `segment_profile.csv` | 유형별 통계 (발표 표 직행) |
| `effect_sizes.csv` | 유형 간 차이의 eta² |
| `imputer_jeonse.pkl` / `score_residual_model.pkl` / `classifier.pkl` / `anomaly_model.pkl` | 학습 ①~④ |
| `decision_rules.txt` | 8문항 판정 규칙 전문 |
| `binning.json` | 구간 경계 (실서비스 재사용) |
| `validation_report.md` | 종합 리포트 |
| `run_metrics.json` | 전 단계 지표 원본 |
| `figures/*.png` | 시각화 9종 |

`outputs/`는 gitignore 대상이다. KCB 원본 행은 저장소에 커밋하지 않는다.

## 설계 제약 (method.md §16)

- 부스팅 계열(LightGBM · XGBoost · CatBoost · HistGradientBoosting) **사용 금지** — 판정 근거를 규칙으로 출력해야 한다.
- 모든 컷은 **분위수 기준**. 유일한 예외는 정부 고시 기준 중위소득(정책 자격선).
- train 외 데이터로 통계량을 계산하지 않는다 → 전부 `fitted_params.json`에 저장 후 valid/test에 적용.
- 결측을 0으로 채우지 않는다. 결측 여부 자체가 신호다.
- 직업군 코드북은 `데이터사용컬럼정의서.xlsx` [코드] 시트로 확보 — 고용형태 3분류(급여소득·자영업·무직)로 사용한다.
- 유형 라벨은 개인 신용 판정이 아니라 **정책 아웃리치 우선순위**다.

## 실서비스 연동

`classifier.pkl` + `binning.json` 조합이 서비스 진입점이다. 판정은 **2단계**다.

**1단계 — 스크리닝 2문항 (모델 호출 전, 결정적 배정)**

| 유형 | 질문 |
|---|---|
| T6 회생·파산 진행군 | 최근 파산 또는 개인회생을 신청한 적이 있습니까? |
| T5 신용 무이력군 | 신용카드·대출 등 신용거래 이력이 전혀 없습니까? |

T5·T6는 `segment.py`의 결정적 규칙으로만 배정되고 사용자가 직접 답할 수 있는 사실이므로
모델 타깃에서 제외했다. 극소 클래스(합계 701행)를 `class_weight='balanced'` 모델에 넣으면
트리 용량을 잠식해 주 4유형 성능이 떨어진다. 스크리닝 질문 문구는 `classifier.pkl`의
`screening` 키와 `config.SCREENING_QUESTIONS`에 함께 저장된다.

**2단계 — 8문항 모델 (대상 클래스 T1~T4)**

8문항 입력(`age_band`, `gender`, `region`, `income_band`, `housing_cost_band`, `debt_band`,
`job_turnover`, `distress_flag`)을 `src/reduced_model.build_questionnaire()`와 동일한
구간 경계로 인코딩한 뒤 `predict` / `predict_proba`를 호출한다.
확신도가 낮은 구간은 추가 질문 트리거 대상이며, 그 비율은 `validation_report.md` §7에 기록된다.

그림 라벨은 한글 폰트가 없는 환경을 고려해 ASCII로 쓴다. 리포트 본문은 한국어다.
