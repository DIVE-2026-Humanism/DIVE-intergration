"""컬럼 상수 · EXCLUDED_COLUMNS · 임계값 파라미터 (method.md §4.2 / §16).

모든 임계값은 분위수 기준이며, 절대 금액 임계값은 사용하지 않는다.
"""

from __future__ import annotations

# ---------------------------------------------------------------- 실행 파라미터
SEED = 42
SENTINEL = -99999999
EXPECTED_ROWS = 100_816

SPLIT_RATIO = {"train": 0.70, "valid": 0.15, "test": 0.15}

# ---------------------------------------------------------------- 원본 컬럼명
COL_GENDER = "성별"
COL_AGE = "연령대"
COL_JOB = "직업군"
COL_REGION_HOME = "거주지 시군구 코드"
COL_REGION_WORK = "근무지 시군구 코드"
COL_INCOME_M = "추정월소득"
COL_INCOME_VERIFIED = "증빙연소득"
COL_INCOME_Y = "추정 연소득"
COL_INCOME_Y_PREV = "2년전 추정 연소득 금액"
COL_ASSET_TOTAL = "총자산평가금액(주택)"
COL_ASSET_NET = "순자산평가금액(주택)"
COL_OWNERSHIP = "자가거주여부"
COL_IS_APT = "현 거주지의 아파트여부"
COL_HOME_PRICE = "현 거주지의 매매가(국토부 실거래가) 또는 공시가격"
COL_CAR = "차량보유(국산/수입)"
COL_LTV = "추정 LTV"
COL_DTI = "추정DTI"
COL_SCORE = "신용평점"
COL_LOAN_CNT = "총대출건수"
COL_CREDIT_AGREE = "신용대출-총대출약정액"
COL_CREDIT_BAL = "신용대출-총대출잔액"
COL_MORT_AGREE = "주택담보대출-총대출약정액"
COL_MORT_BAL = "주택담보대출-총대출잔액"
COL_POLICY_AGREE = "정책자금대출-총대출약정액"
COL_POLICY_BAL = "정책자금대출-총대출잔액"
COL_REPAY_12M = "총 대출 상환금액 (최근 12개월)"
COL_CARD_CREDIT = "최근 12개월 신용카드소비금액"
COL_CARD_CHECK = "최근 12개월 체크카드소비금액"
COL_CARD_LUMP = "최근 12개월 일시불이용금액"
COL_CARD_INSTALL = "최근 12개월 할부이용금액"
COL_CASH_ADVANCE = "최근 12개월 현금서비스이용금액"
COL_DELINQ_LOAN_CNT = "대출연체건수"
COL_DELINQ_CARD_CNT = "카드연체건수"
COL_DELINQ_DAYS = "연체일수"
COL_DELINQ_LOAN_AMT = "대출연체금액"
COL_DELINQ_CARD_AMT = "카드연체금액"
COL_THIN = "Thin Filer 여부"
COL_BANKRUPT = "파산, 개인회생 신청 여부"
COL_TRADE_PRICE_2Y = "2년내 현거주지평균실거래가"
COL_JEONSE_2Y = "2년내 현거주지평균전세거래가"
COL_JOB_HIST = "2년내 직장명이력건수"
COL_JOB_CHANGE_INCOME = "2년내 이직후 소득 증감액"

RAW_COLUMNS: list[str] = [
    COL_GENDER, COL_AGE, COL_JOB, COL_REGION_HOME, COL_REGION_WORK,
    COL_INCOME_M, COL_INCOME_VERIFIED, COL_INCOME_Y, COL_INCOME_Y_PREV,
    COL_ASSET_TOTAL, COL_ASSET_NET, COL_OWNERSHIP, COL_IS_APT, COL_HOME_PRICE,
    COL_CAR, COL_LTV, COL_DTI, COL_SCORE, COL_LOAN_CNT,
    COL_CREDIT_AGREE, COL_CREDIT_BAL, COL_MORT_AGREE, COL_MORT_BAL,
    COL_POLICY_AGREE, COL_POLICY_BAL, COL_REPAY_12M,
    COL_CARD_CREDIT, COL_CARD_CHECK, COL_CARD_LUMP, COL_CARD_INSTALL,
    COL_CASH_ADVANCE, COL_DELINQ_LOAN_CNT, COL_DELINQ_CARD_CNT,
    COL_DELINQ_DAYS, COL_DELINQ_LOAN_AMT, COL_DELINQ_CARD_AMT,
    COL_THIN, COL_BANKRUPT, COL_TRADE_PRICE_2Y, COL_JEONSE_2Y,
    COL_JOB_HIST, COL_JOB_CHANGE_INCOME,
]

# 명목형(코드) 컬럼 — 분위수·평균 계산 대상이 아니다.
CATEGORICAL_COLUMNS = [COL_GENDER, COL_JOB, COL_REGION_HOME, COL_REGION_WORK, COL_OWNERSHIP]

# ---------------------------------------------------------------- §4.2 확정 제거 7열
EXCLUDED_COLUMNS: list[str] = [
    COL_INCOME_M,               # 추정 연소득과 중복
    COL_ASSET_NET,              # 순 > 총 35%, 생성 로직 부실
    COL_JOB_CHANGE_INCOME,      # 직장이력 0인데 값 존재
    COL_CREDIT_AGREE,           # 약정 0인데 잔액 존재
    COL_CARD_LUMP,              # 부분집합 관계 붕괴
    COL_CARD_INSTALL,           # 위와 동일
    COL_TRADE_PRICE_2Y,         # 매매가와 중복 + 71.1% 결측
]

EXCLUSION_REASONS: dict[str, str] = {
    COL_INCOME_M: "`추정 연소득`과 중복. 필요 시 연소득÷12로 대체",
    COL_ASSET_NET: "순자산 > 총자산 35%. 주담대 91.6%가 0인데 총자산과 불일치 → 생성 로직 부실",
    COL_JOB_CHANGE_INCOME: "직장이력 0인데 값 존재 10%. 이력과 독립 생성된 정황",
    COL_CREDIT_AGREE: "약정 0인데 잔액 존재",
    COL_CARD_LUMP: "신용+체크 소비 합 초과 (부분집합 관계 붕괴)",
    COL_CARD_INSTALL: "신용+체크 소비 합 초과 (부분집합 관계 붕괴)",
    COL_TRADE_PRICE_2Y: "`현 거주지의 매매가`와 중복 + 71.1% 결측",
}

# §4.4 보류 3열 — 아래 검사들의 합집합 위반율이 임계 초과 시 자동 제거
PROVISIONAL_EXCLUSIONS: dict[str, list[str]] = {
    COL_DELINQ_DAYS: ["D3", "D4"],
    COL_DTI: ["B7"],
    COL_MORT_AGREE: ["B4", "B5"],
}
PROVISIONAL_VIOLATION_THRESHOLD = 0.30

# ---------------------------------------------------------------- 임계값 파라미터
PC1_WEIGHT_THRESHOLD = 0.40        # §10.2 PCA 가중 채택 기준
GMM_SILHOUETTE_THRESHOLD = 0.25    # §11.4 GMM 주도 기준
GMM_K_RANGE = range(2, 9)
GMM_SILHOUETTE_SAMPLE = 10_000
GMM_FIT_SAMPLE = 30_000

SEGMENT_CUT_QUANTILE = 0.50        # §11.1 (2) 주 분류 컷 (train 중앙값)
H_FLAG_QUANTILE = 0.75             # §11.2 주거 부담 수정자
MIN_SEGMENT_SHARE = 0.05           # §11.3 규모 경고 기준
T5_MIN_COUNT = 100                 # §11.1 대안 정의 병기 기준

INCOME_BANDS = 5                   # §12.1 income_band 분위수
HOUSING_BANDS = 5                  # §12.1 housing_cost_band 분위수
DEBT_BANDS = 3                     # §12.1 대출 보유자 내부 분위수(무대출 밴드 0 별도)
TREE_MAX_DEPTHS = [4, 5]           # §12.2 DecisionTree 후보 깊이
CV_FOLDS = 5

ANOMALY_CONTAMINATION = 0.05       # §13

# ---------------------------------------------------------------- 세그먼트 정의
SEGMENT_NAMES: dict[str, str] = {
    "T1": "자산형성 준비군",
    "T2": "고정지출 압박군",
    "T3": "잠재 불안군",
    "T4": "복합 위기군",
    "T5": "신용 무이력군",
    "T6": "회생·파산 진행군",
}
SEGMENT_ORDER = ["T1", "T2", "T3", "T4", "T5", "T6"]

# T5·T6는 결정적 규칙(§11.1 (1))으로만 배정되고, 사용자가 문진에서 직접 답할 수 있는 사실이다.
# 따라서 축소 분류기(§12)의 학습·평가 대상에서 제외하고 사전 스크리닝으로 처리한다.
SPECIAL_SEGMENTS = ["T5", "T6"]
MAIN_SEGMENTS = ["T1", "T2", "T3", "T4"]

# 서비스 문진 앞단 스크리닝 (모델 호출 전에 먼저 묻는다)
SCREENING_QUESTIONS: dict[str, str] = {
    "T6": "최근 파산 또는 개인회생을 신청한 적이 있습니까? (예 → T6 회생·파산 진행군)",
    "T5": "신용카드·대출 등 신용거래 이력이 전혀 없습니까? (예 → T5 신용 무이력군)",
}

# ---------------------------------------------------------------- 축 정의 (§10.1)
# (변수명, 부호) — 부호 (-)는 방향 반전 대상("높을수록 나쁨"으로 통일)
FINANCIAL_AXIS: list[tuple[str, int]] = [
    ("dsr", +1),
    ("delinq_severity", +1),
    ("total_delinq_cnt", +1),
    ("cash_advance_flag", +1),
    ("consumption_ratio", +1),
    (COL_SCORE, -1),
]
EMPLOYMENT_AXIS: list[tuple[str, int]] = [
    ("job_turnover", +1),
    ("income_trajectory", -1),
    ("has_verified_income", -1),
    ("thin_filer", +1),
    ("credit_score_residual", -1),
]

FINANCIAL_SCORE = "financial_stress_score"
EMPLOYMENT_SCORE = "employment_instability_score"
