"""hybrid 파이프라인 상수.

라벨 체계는 model.md(잠재 PCA + GMM, E1~E6)를 따르고,
정책 기준·고용형태·문진 등 analysis 자산은 `analysis.src.config`에서 그대로 재사용한다.
"""

from __future__ import annotations

from analysis.src import config as AC  # 상류 상수 재사용 (컬럼명·정책기준·코드북)

SEED = AC.SEED

# ---------------------------------------------------------------- E1~E6 라벨 (model.md §8.4)
ETYPE_NAMES: dict[str, str] = {
    "E1": "안정형",
    "E2": "주택대출형",
    "E3": "저부채형",
    "E4": "금융이력부족형",
    "E5": "대출부담형",
    "E6": "위기형",
}
ETYPE_ORDER = list(ETYPE_NAMES)
# 발제사 정의(안정/취약 2분류)와의 매핑 — 종합점수 상위 3유형을 안정으로 본다.
ETYPE_MAJOR: dict[str, str] = {
    "E1": "안정", "E2": "안정", "E3": "안정",
    "E4": "취약", "E5": "취약", "E6": "취약",
}

# ---------------------------------------------------------------- 잠재모델 입력 32개 (model.md §4.2)
LATENT_RAW_FEATURES = [
    AC.COL_INCOME_Y, AC.COL_INCOME_Y_PREV, AC.COL_INCOME_VERIFIED, AC.COL_ASSET_TOTAL,
    AC.COL_HOME_PRICE, AC.COL_SCORE, AC.COL_LOAN_CNT, AC.COL_CREDIT_BAL,
    AC.COL_MORT_BAL, AC.COL_POLICY_BAL, AC.COL_REPAY_12M,
    AC.COL_CARD_CREDIT, AC.COL_CARD_CHECK, AC.COL_CASH_ADVANCE,
    AC.COL_DELINQ_LOAN_CNT, AC.COL_DELINQ_CARD_CNT, AC.COL_DELINQ_LOAN_AMT,
    AC.COL_DELINQ_CARD_AMT, AC.COL_THIN, AC.COL_BANKRUPT, AC.COL_JOB_HIST,
]
LATENT_DERIVED_FEATURES = [
    "income_trajectory", "total_loan_balance", "avg_loan_balance", "dsr",
    "consumption_ratio", "credit_dependency", "total_delinq_cnt", "delinq_severity",
    "jeonse_income_multiple", "pir", "commute_mismatch",
]

# ---------------------------------------------------------------- 안정성 앵커 (model.md §7.2)
# 앵커는 지도학습 정답이 아니라 잠재축의 부호를 정하는 방향 기준이다.
ANCHOR_POSITIVE = [
    AC.COL_INCOME_Y, AC.COL_INCOME_VERIFIED, AC.COL_ASSET_TOTAL, AC.COL_SCORE,
    "income_trajectory",
]
ANCHOR_NEGATIVE = [
    "dsr", "total_loan_balance", AC.COL_LOAN_CNT, "consumption_ratio",
    "total_delinq_cnt", "delinq_severity", AC.COL_CASH_ADVANCE, AC.COL_THIN,
    AC.COL_BANKRUPT, AC.COL_JOB_HIST,
]

PCA_VARIANCE_TARGET = 0.90   # §6.2 누적 설명분산 기준
LATENT_DIMS = 8              # §6.3 점수·GMM 공통 잠재차원
SCORE_COMPONENTS = 5         # §7.3 점수에 쓸 최대 성분 수
SCORE_GRID = 1001            # §7.4 분위수 보정 격자
GMM_COMPONENTS = 6
GMM_COVARIANCE = "diag"
GMM_N_INIT = 5
GMM_REG_COVAR = 1e-5

# ---------------------------------------------------------------- 정책 연결 (analysis 자산)
BLINDSPOT_INCOME_RATIO = AC.BLINDSPOT_INCOME_RATIO   # 기준 중위소득 100% 초과
BLINDSPOT_SCORE_QUANTILE = 0.25                      # 종합점수 하위 25%

# ---------------------------------------------------------------- 문진 (analysis 자산 + 개선)
# 실측상 연령·성별·거주지는 기여 0이므로 문진에서 뺀다(analysis 실험 결과).
QUESTION_CATEGORICAL = ["employment_type"]
QUESTION_NUMERIC = [
    "income_band",        # 월 실수령액
    "consumption_band",   # 월 카드 사용액 ÷ 소득
    "repay_band",         # 월 대출 상환액 ÷ 소득
    "debt_band",          # 대출 잔액
    "job_turnover",       # 최근 2년 이직 횟수
    "distress_flag",      # 연체·현금서비스 경험
]
QUESTION_FEATURES = QUESTION_CATEGORICAL + QUESTION_NUMERIC
BAND_COUNT = 5
TREE_MAX_DEPTHS = [4, 5, 6]
CV_FOLDS = 5

# 모델 앞단 경고 플래그 — 라벨을 강제하지 않고 진단 결과에 병기한다.
SCREENING_FLAGS: dict[str, str] = {
    "bankruptcy": "최근 파산 또는 개인회생을 신청한 적이 있습니까?",
    "no_credit_history": "신용카드·대출 등 신용거래 이력이 전혀 없습니까?",
}

# ---------------------------------------------------------------- 확신도 → 표시 수준
# 확신도는 "얼마나 확신하는가"이고, 표시 수준은 "그래서 무엇까지 단정해도 되는가"다.
# 둘을 분리한 이유: 문진 경로에서 확신도가 높은 구간이 세부유형은 오히려 더 자주 틀린다.
#
# 문진 경로 실측 (test 15,123명, 임계값 이상 구간)
#   ≥0.80   1.4%   세부 0.750 · 대분류 0.957
#   ≥0.60  15.9%   세부 0.676 · 대분류 0.865
#   <0.60  84.1%   세부 0.463 · 대분류 0.665   → 유형 단정 불가
#
# 0.70~0.80 구간만 세부 정확도가 0.320으로 붕괴한다(단일 leaf 과적합, train 775 →
# test 161명에서 순도 0.725 → 정확도 0.317). 그래서 세부유형 단독 표시 기준을
# 0.70이 아니라 0.80으로 잡았다. 반면 같은 구간에서도 대분류는 0.897을 유지한다.
DISPLAY_DETAIL = "detail"        # 세부유형(E1~E6)까지 단독 표시
DISPLAY_MAJOR = "major"          # 대분류(안정/취약)만 단독 표시, 세부유형은 참고값
DISPLAY_REFERENCE = "reference"  # 유형 단정 금지 — 지표·정책 근거만 표시, 추가 질문 트리거

CONFIDENCE_BANDS_SURVEY = [
    (0.80, DISPLAY_DETAIL, "세부유형까지 표시 가능"),
    (0.60, DISPLAY_MAJOR, "대분류만 표시 · 세부유형은 참고"),
    (0.00, DISPLAY_REFERENCE, "유형 확정 자제 · 추가 질문 필요"),
]
# 정밀(KCB) 경로는 GMM 사후확률이라 분포 자체가 다르다(평균 0.918 · 0.5 미만 1.1%).
# 문진과 같은 임계값을 쓰면 안 된다.
CONFIDENCE_BANDS_PRECISE = [
    (0.70, DISPLAY_DETAIL, "세부유형까지 표시 가능"),
    (0.50, DISPLAY_MAJOR, "대분류만 표시 · 세부유형은 참고"),
    (0.00, DISPLAY_REFERENCE, "유형 확정 자제 · 추가 질문 필요"),
]
CONFIDENCE_SOURCE_COLUMN = {"survey": "survey_confidence", "precise": "type_confidence"}
