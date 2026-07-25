# 경제 계층 6유형 분석 파이프라인

기존 FastAPI용 `src/`와 독립된 `method.md` v2 구현이다. 부스팅 모델을 사용하지
않으며 모든 학습 통계와 임계값은 train에서만 적합한다.

```bash
cd "$HOME/DIVE-intergration/LLM service"
.venv/bin/pip install -r economic_segments/requirements.txt
.venv/bin/python -m economic_segments.run \
  --input "Dataset/(합성데이터) 종합해커톤.csv" \
  --outdir outputs/economic_segments_v2 \
  --seed 42
```

주요 결과는 `validation_report.md`, `segments.csv`, `fitted_params.json`,
`model_metrics.json`이며 학습 모델 4종과 발표용 그림 8종도 같은 출력 디렉터리에
생성된다. 현재 데이터 전체 실행 시간은 CPU 기준 약 2분이다.

## 분류기 선택

- `classifier.pkl`: 기존 8문항 압축 모델. 빠른 사전 선별용이며 낮은 확신도에서는
  유형을 확정하지 않는다.
- `full_questionnaire_classifier.pkl`: 21개 입력으로 라벨 생성에 쓰인 재무·고용축을
  동일하게 복원하는 고충실도 설명 가능 모델이다. `full_questionnaire_rules.txt`에
  T6 → T5 → 사분면 순서의 전체 판정 규칙을 함께 저장한다.

확장 모델의 100% 재현율은 독립적인 미래 위험 예측 성능이 아니라, 동일한 입력과
고정된 train 분위수로 정책 아웃리치 라벨을 결정론적으로 복원한 충실도 지표다.

## 레이블 없는 잠재 경제점수 모델

정답 레이블 없이 종합점수와 유형을 함께 학습하려면 다음을 실행한다.

```bash
.venv/bin/python -m economic_segments.latent_run \
  --input "Dataset/(합성데이터) 종합해커톤.csv" \
  --outdir outputs/latent_economic_model_final \
  --seed 42
```

저장된 모델은 원본 42개 컬럼의 `DataFrame`을 직접 입력받는다.

```python
import joblib

model = joblib.load("outputs/latent_economic_model_final/latent_economic_model.pkl")
result = model.predict(raw_dataframe)
```

반환 컬럼은 `composite_stability_score`(0~100), `economic_type`(E1~E6),
`economic_type_name`, `type_confidence`다. 점수는 PCA 잠재축 기반 상대 안정성이고,
유형은 6성분 GMM 군집이다. 현재 데이터의 실루엣이 낮으므로 유형 간 자연 경계가
강하다고 해석해서는 안 된다.
