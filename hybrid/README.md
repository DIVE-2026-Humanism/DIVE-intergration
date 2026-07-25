# hybrid — 잠재 E1~E6 + 정책 기준 + 문진 축소

`model.md`의 잠재 PCA·GMM 라벨 체계(E1~E6)를 메인으로 쓰고,
`method.md`/`analysis`의 정책 기준·문진 압축·외부 검증을 결합한 파이프라인이다.

## 왜 결합했나

| 비교 | model.md (E1~E6) | analysis (T1~T6) | 채택 |
|---|---|---|---|
| 외부 타당도 (연령·자가·직업군 eta²) | 0.075 / 0.050 / 0.033 | 0.004 / 0.001 / 0.007 | **E1~E6** |
| 문진 재현력 | — (42변수 필수) | 스크리닝+8문항 | **analysis 구조** |
| 종합점수 0~100 | 있음 | 없음 | **model.md** |
| 설명 가능성 | PCA 성분 가중 | 규칙 트리 | **analysis** |
| 정책 자격 연결 | 없음 | 기준 중위소득 등급 | **analysis** |

E1~E6가 외부 변수를 더 잘 설명하지만 42개 금융변수를 요구해 서비스로 성립하지 않는다.
그래서 **라벨은 E1~E6, 사용자 진입은 문진 7문항**으로 결합했다.

## 실행

```bash
# 저장소 루트에서
python -m hybrid.src.run --input "important data/(합성데이터)종합해커톤.csv" --outdir hybrid/outputs/ --seed 42
```

- 전수 실행 약 25초. 동일 시드 2회 실행 시 산출물이 바이트 단위로 동일하다.
- 상류 STEP 0~4(정합성·로딩·분할·전세가 대체·파생변수)는 `analysis.src`를 그대로 import한다.

## 파이프라인

| STEP | 모듈 | 내용 | 출처 |
|---|---|---|---|
| 0~4 | `analysis.src.*` | 정합성 26종 → 열 제거 → 분할 → 전세가 대체 → 파생변수 | method.md |
| 5 | `latent.py` | PCA 잠재공간 → 종합점수(0~100) → GMM 6유형 → E1~E6 | model.md §5~8 |
| 6 | `policy.py` | 기준 중위소득 등급 · 정책 사각지대 | method.md 확장 |
| 7 | `diagnose.py` | 문진 7문항 축소 모델 + 백엔드 payload | method.md §12 확장 |
| 8 | `validate.py` | 외부/준순환 분리 검증 · 시각화 | 신규 |

## 라벨 체계

| 유형 | 명칭 | 대분류 | 평균 종합점수 |
|---|---|---|---:|
| E1 | 안정형 | 안정 | 82.3 |
| E2 | 주택대출형 | 안정 | 66.8 |
| E3 | 저부채형 | 안정 | 56.7 |
| E4 | 금융이력부족형 | 취약 | 45.4 |
| E5 | 대출부담형 | 취약 | 18.3 |
| E6 | 위기형 | 취약 | 9.9 |

대분류(안정/취약)는 발제사 정의와 맞춘 것이고, 세부 6유형은 그 아래 계층이다.

## 문진 7문항

| # | 문항 | 변수 |
|---|---|---|
| 1 | 고용 형태 (급여소득/자영업/무직) | `employment_type` |
| 2 | 월 실수령액 | `income_band` |
| 3 | 월 카드 사용액 ÷ 소득 | `consumption_band` |
| 4 | 월 대출 상환액 ÷ 소득 | `repay_band` |
| 5 | 대출 잔액 | `debt_band` |
| 6 | 최근 2년 이직 횟수 | `job_turnover` |
| 7 | 최근 연체·현금서비스 경험 | `distress_flag` |

**연령·성별·거주지는 넣지 않았다.** 실측에서 기여가 0이었다(포함/제외 시 accuracy·macro F1이 소수점 셋째 자리까지 동일).

성능: test accuracy **0.521** / macro F1 **0.503** (6클래스, 무작위 기준 0.167 대비 **3.1배**).

## 백엔드 전달 계약

`diagnosis_samples.json`이 유형별 예시다. `diagnose.build_payload()`가 조립한다.

```json
{
  "etype": "E6", "etype_name": "위기형", "major_class": "취약",
  "stability_score": 3.8,
  "type_confidence": 1.0,
  "display_level": "detail", "confidence_guidance": "세부유형까지 표시 가능",
  "income": { "grade": "50~60% 취약경계", "ratio_to_median": 0.539,
              "percentile_busan_youth": 15.4, "policy_eligible": true },
  "employment_type": "급여소득",
  "flags": { "policy_blindspot": false, "no_housing_record": false,
             "cash_advance": false, "multi_debt": false },
  "indicators": [
    { "name": "추정 연소득", "percentile": 0.8, "position": "하위 1%",
      "risk_percentile": 99.2, "flagged": true }
  ],
  "survey_decision_path": ["distress_flag > 0.50", "consumption_band ≤ 1.50", "..."],
  "reasons": ["최근 연체 이력 존재", "추정 연소득 하위 1% — 표본 대비 위험 구간"]
}
```

- `flags`·`income.grade`로 **정책 매칭**(백엔드 담당)
- `indicators`·`survey_decision_path`·`reasons`로 **판정 근거 표시**(프론트)

### `display_level` — 프론트가 지켜야 할 표시 한도

`etype` 값은 항상 실어 보내되, **어디까지 단정해도 되는지는 `display_level`이 정한다.**
확신도 임계값은 경로별 실측으로 정했다. 문진과 정밀은 확신도 분포가 전혀 다르므로
(문진 평균 0.516 / GMM 평균 0.918) 같은 임계값을 쓰지 않는다.

| `display_level` | 프론트 동작 | 문진 경로 임계 | 정밀 경로 임계 |
|---|---|---|---|
| `detail` | 세부유형(E1~E6)까지 표시 | ≥ 0.80 | ≥ 0.70 |
| `major` | **대분류(안정/취약)까지만** 표시, 세부유형은 참고값 | ≥ 0.60 | ≥ 0.50 |
| `reference` | 유형 표시 안 함 — 지표·정책 근거만, **추가 질문 트리거** | < 0.60 | < 0.50 |

문진 경로 실측(test 15,123명) 근거:

| 수준 | 대상 | 세부유형 정확도 | 대분류 정확도 |
|---|---:|---:|---:|
| `detail` | 1.4% | **0.750** | 0.957 |
| `major` | 14.5% | 0.669 | **0.857** |
| `reference` | 84.1% | 0.492 | 0.664 |

> **왜 세부유형 기준이 0.70이 아니라 0.80인가.** 0.70~0.80 구간만 세부 정확도가
> **0.320으로 붕괴**한다. 단일 leaf 과적합이 원인이다(train 775명 순도 0.725 →
> test 161명 정확도 0.317). 같은 구간에서도 대분류는 0.897을 유지하므로,
> 그 구간은 `major`로 내려 대분류만 표시한다.

## 산출물 (`hybrid/outputs/`)

| 파일 | 내용 |
|---|---|
| `validation_report.md` | 종합 검증 리포트 |
| `segments.csv` | 행별 유형 · 점수 · 확신도 · 정책등급 · 플래그 |
| `diagnosis_samples.json` | 유형별 진단 payload 예시 |
| `fitted_params.json` | 잠재모델 파라미터 · 구간 경계 · 백분위 기준 (실서비스 재사용) |
| `latent_model.pkl` / `survey_model.pkl` / `imputer_jeonse.pkl` | 저장 모델 |
| `decision_rules.txt` | 문진 판정 규칙 전문 |
| `consistency_report.md` / `data_caveats.md` | 데이터 검증·한계 |
| `figures/*.png` | 시각화 3종 |

## 해석 시 주의

- **GMM 실루엣 0.058.** 자연 경계가 강하지 않다. "데이터가 6개 집단을 발견했다"가 아니라
  **"정책 우선순위를 위해 6단계로 나눴다"**고 말해야 한다.
- **PCA 90% 설명에 32개 중 19개 성분이 필요하다.** 잠재 요인 구조가 약하다는 뜻이다.
- **외부 vs 준순환을 구분한다.** `multi_debt`·`pir`·`income_percentile_busan`은 잠재 입력이거나
  그 파생이므로 타당성 근거로 쓰면 안 된다. 리포트 §3에 구분해 두었다.
- 유형 라벨은 개인 신용 판정이 아니라 **정책 아웃리치 우선순위**다.
