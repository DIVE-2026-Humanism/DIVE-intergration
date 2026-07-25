from __future__ import annotations

TARGET_ROWS = 100_816
SENTINEL = -99_999_999

REQUIRED_COLUMNS = [
    "성별", "연령대", "직업군", "거주지 시군구 코드", "근무지 시군구 코드",
    "추정월소득", "증빙연소득", "추정 연소득", "2년전 추정 연소득 금액",
    "총자산평가금액(주택)", "순자산평가금액(주택)", "자가거주여부",
    "현 거주지의 아파트여부", "현 거주지의 매매가(국토부 실거래가) 또는 공시가격",
    "차량보유(국산/수입)", "추정 LTV", "추정DTI", "신용평점", "총대출건수",
    "신용대출-총대출약정액", "신용대출-총대출잔액", "주택담보대출-총대출약정액",
    "주택담보대출-총대출잔액", "정책자금대출-총대출약정액",
    "정책자금대출-총대출잔액", "총 대출 상환금액 (최근 12개월)",
    "최근 12개월 신용카드소비금액", "최근 12개월 체크카드소비금액",
    "최근 12개월 일시불이용금액", "최근 12개월 할부이용금액",
    "최근 12개월 현금서비스이용금액", "대출연체건수", "카드연체건수", "연체일수",
    "대출연체금액", "카드연체금액", "Thin Filer 여부", "파산, 개인회생 신청 여부",
    "2년내 현거주지평균실거래가", "2년내 현거주지평균전세거래가",
    "2년내 직장명이력건수", "2년내 이직후 소득 증감액",
]

EXCLUDED_COLUMNS = [
    "추정월소득", "순자산평가금액(주택)", "2년내 이직후 소득 증감액",
    "신용대출-총대출약정액", "최근 12개월 일시불이용금액",
    "최근 12개월 할부이용금액", "2년내 현거주지평균실거래가",
]

CONDITIONAL_EXCLUSIONS = {
    "연체일수": ("D3", "D4"),
    "추정DTI": ("B7",),
    "주택담보대출-총대출약정액": ("B4", "B5"),
}

FINANCIAL_AXIS = {
    "dsr": 1, "delinq_severity": 1, "total_delinq_cnt": 1,
    "cash_advance_flag": 1, "consumption_ratio": 1, "신용평점": -1,
}
EMPLOYMENT_AXIS = {
    "job_turnover": 1, "income_trajectory": -1, "has_verified_income": -1,
    "thin_filer": 1, "credit_score_residual": -1,
}

SEGMENT_NAMES = {
    "T1": "자산형성 준비군", "T2": "고정지출 압박군", "T3": "잠재 불안군",
    "T4": "복합 위기군", "T5": "신용 무이력군", "T6": "회생·파산 진행군",
}

DERIVED_FEATURES = [
    "has_verified_income", "income_trajectory", "income_declined", "job_turnover",
    "jeonse_income_multiple", "pir", "commute_mismatch", "dsr", "total_loan_balance",
    "avg_loan_balance", "multi_debt", "has_mortgage", "has_policy_loan", "is_owner",
    "consumption_ratio", "credit_dependency", "cash_advance_flag", "total_delinq_cnt",
    "delinq_severity", "score_floor", "thin_filer",
]
