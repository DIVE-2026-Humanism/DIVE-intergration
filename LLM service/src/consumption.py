from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .benchmarks import age_to_band, load_credit_benchmarks
from .external import parse_debt, parse_income_card
from .io_load import ROOT, load_config, read_csv_fallback

LOGGER = logging.getLogger(__name__)


def _number(record: dict[str, Any], key: str, sentinel: float) -> float | None:
    try:
        value = float(str(record.get(key, "")).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value) or value == sentinel:
        return None
    return value


def _gap(value: float, average: float) -> float:
    return round(100.0 * (value - average) / average, 1)


def _item(name: str, value: float, average: float, unit: str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    gap = _gap(value, average)
    direction = "높음" if gap > 0 else "낮음" if gap < 0 else "같음"
    ending = {"높음": "높습니다", "낮음": "낮습니다", "같음": "같습니다"}[direction]
    sentence = f"당신의 {name}이 또래 평균보다 {abs(gap):.1f}% {ending}"
    payload: dict[str, Any] = {
        "지표": name,
        "값": round(value, 1),
        "또래평균": round(average, 1),
        "격차%": gap,
        "단위": unit,
        "문장": sentence,
    }
    if extra:
        payload.update(extra)
    return payload


def _rent_benchmarks(config: dict[str, Any]) -> dict[str, float]:
    configured = config.get("consumption", {}).get("rent_csv") or config.get("paths", {}).get("rent_csv")
    if not configured:
        return {}
    path = Path(configured)
    if not path.is_absolute():
        path = ROOT / config["project"]["dataset_dir"] / path
    if not path.exists():
        return {}
    frame, _ = read_csv_fallback(path, config["io"]["csv_encodings"])
    gu_column = next((key for key in ("구군", "구·군", "시군구", "사는곳") if key in frame), None)
    rent_column = next((key for key in ("평균월세만원", "평균 월세(만원)", "월세") if key in frame), None)
    if not gu_column or not rent_column:
        return {}
    rent = pd.to_numeric(frame[rent_column], errors="coerce")
    return {str(gu).strip(): float(value) for gu, value in zip(frame[gu_column], rent) if pd.notna(value)}


def _housing_feedback(record: dict[str, Any], gu: str | None, config: dict[str, Any], sentinel: float) -> dict[str, Any]:
    rents = _rent_benchmarks(config)
    if gu and gu in rents:
        monthly = round(rents[gu], 1)
        return {
            "상태": "지역평균_연결됨",
            "평균월세만원": monthly,
            "출처": config.get("consumption", {}).get("rent_source") or "설정된 지역별 월세 CSV",
            "문장": f"당신은 1인 가구 청년입니다. 거주지 {gu} 평균 월세는 {monthly:g}만원입니다. 현재 주거비가 평균보다 높지 않은지 점검해 보세요.",
        }
    conversion = config.get("consumption", {}).get("jeonse_conversion_rate")
    jeonse = _number(record, "2년내 현거주지평균전세거래가", sentinel)
    if conversion is not None and jeonse is not None and float(conversion) > 0:
        # KCB 천원 × 연 전환율 ÷ 12 ÷ 10 = 월 만원
        monthly = round(jeonse * float(conversion) / 12.0 / 10.0, 1)
        return {
            "상태": "전세가_근사",
            "평균월세만원": monthly,
            "출처": "KCB 현 거주지 평균 전세가와 설정된 전월세전환율",
            "문장": f"당신은 1인 가구 청년입니다. 현 거주지 평균 전세가와 설정된 전월세전환율로 환산한 월세는 약 {monthly:g}만원입니다. 실측 월세가 아닌 근사값입니다.",
        }
    return {
        "상태": "데이터_미확보",
        "평균월세만원": None,
        "출처": None,
        "문장": "당신은 1인 가구 청년입니다. 검증된 부산 구·군별 월세 데이터가 연결되지 않아 월세 평균이나 격차를 표시하지 않습니다.",
    }


def _external_values(config: dict[str, Any]) -> tuple[dict[int, dict[str, float]], dict[int, float], str | None]:
    try:
        return parse_income_card(config), parse_debt(config), None
    except (FileNotFoundError, UnicodeError, ValueError, IndexError, TypeError) as exc:
        LOGGER.warning("외부 비교통계를 사용할 수 없습니다: %s", type(exc).__name__)
        return {}, {}, "EXTERNAL_STATS_UNAVAILABLE"


def _one_person_guides(items: list[dict[str, Any]], housing: dict[str, Any]) -> list[str]:
    guides = [housing["문장"]]
    by_name = {item["지표"]: item for item in items}
    income = by_name.get("연소득")
    if income:
        guides.append(
            "1인가구는 소득 변동을 혼자 감당하므로, 또래 평균과의 차이와 별개로 월 필수비와 비상자금 목표를 함께 점검해 보세요."
        )
    card = by_name.get("월 카드소비")
    if card:
        guides.append(
            f"월 카드소비는 또래 평균 대비 {abs(card['격차%']):.1f}% {('높습니다' if card['격차%'] > 0 else '낮습니다' if card['격차%'] < 0 else '같습니다')}. 최근 3개월 명세에서 주거·식비 같은 고정성 지출과 조정 가능한 지출을 나눠 보세요."
        )
    debt = by_name.get("대출잔액")
    if debt:
        guides.append(
            "대출잔액은 평균보다 높거나 낮다는 사실만으로 위험을 뜻하지 않습니다. 1인가구라면 대출별 금리·월 상환액·만기를 함께 확인하세요."
        )
    guides.append("또래 평균은 비교 기준일 뿐이며, 평균보다 높거나 낮다는 이유만으로 경제적 위험·안정을 단정하지 않습니다.")
    return guides

def feedback(
    record: dict[str, Any] | None,
    *,
    user_inputs: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    credit_benchmarks: dict[int, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """KCB 정밀모드 또는 사용자 입력 라이트모드의 비교 피드백을 만든다."""
    config = config or load_config()
    sentinel = float(config["io"]["sentinel"])
    user_inputs = user_inputs or {}
    items: list[dict[str, Any]] = []
    income_stats, debt_stats, external_error = _external_values(config)
    sources = config.get("external", {}).get("sources", {})

    if record is None:
        annual_income = float(user_inputs["연소득"]) / 1000.0  # 원 → KCB 천원
        band = age_to_band(user_inputs.get("나이"))
        if band is not None and band in income_stats:
            average = income_stats[band]["inc"] * 10.0
            note = "입력 나이에 해당하는 2023년 부산 청년 연령대 평균"
        else:
            average = None
            note = "입력 나이에 대응하는 외부 소득통계를 찾지 못해 비교하지 않음"
        if average is not None:
            items.append(_item(
                "연소득", annual_income, average, "천원/년",
                extra={"기준설명": note, "출처": sources.get("income_card")},
            ))
        return {
            "items": items,
            "1인가구여부": None,
            "1인가구확인상태": "라이트진단_미확인",
            "주거피드백": None,
            "주거지원_우선": False,
            "분석모드": "light",
            "외부데이터오류": external_error,
            "1인가구상세가이드": [],
        }

    band = age_to_band(_number(record, "연령대", sentinel))
    gu = str(user_inputs.get("사는곳") or "").strip() or None
    income = _number(record, "추정 연소득", sentinel)
    if band is not None and band in income_stats and income is not None:
        items.append(_item(
            "연소득", income, income_stats[band]["inc"] * 10.0, "천원/년",
            extra={"기준설명": "2023년 부산 청년 연령대 평균", "출처": sources.get("income_card")},
        ))

    credit_card = _number(record, "최근 12개월 신용카드소비금액", sentinel)
    check_card = _number(record, "최근 12개월 체크카드소비금액", sentinel)
    if band is not None and band in income_stats and credit_card is not None and check_card is not None:
        items.append(_item(
            "월 카드소비", (credit_card + check_card) / 12.0,
            income_stats[band]["card"] * 10.0 / 12.0, "천원/월",
            extra={"기준설명": "2023년 부산 청년 연령대 연간 카드이용금액의 월 환산", "출처": sources.get("income_card")},
        ))

    loan_count = _number(record, "총대출건수", sentinel)
    balances = [_number(record, key, sentinel) for key in ("신용대출-총대출잔액", "주택담보대출-총대출잔액", "정책자금대출-총대출잔액")]
    if band is not None and band in debt_stats and loan_count is not None and loan_count >= 1 and all(value is not None for value in balances):
        debt_sum = sum(value for value in balances if value is not None)
        if debt_sum > 0:
            items.append(_item(
                "대출잔액", debt_sum, debt_stats[band] * 10.0, "천원",
                extra={"기준설명": "2023년 부산 청년 연령대 채무보유자 평균", "출처": sources.get("debt")},
            ))

    thin = _number(record, "Thin Filer 여부", sentinel) == 1
    score = _number(record, "신용평점", sentinel)
    if credit_benchmarks is None:
        credit_path = ROOT / config["project"]["artifacts_dir"] / "credit_benchmarks.json"
        if credit_path.exists():
            credit_benchmarks = load_credit_benchmarks(credit_path)
    if not thin and band is not None and score is not None and credit_benchmarks and band in credit_benchmarks:
        benchmark = credit_benchmarks[band]
        items.append(_item(
            "신용평점", score, benchmark["mean"], "점",
            extra={
                "또래분위": {key: round(value, 1) for key, value in benchmark.items() if key.startswith("q")},
                "기준설명": "대회 당일 학습에 사용한 부산 청년 KCB 표본 평균",
                "출처": sources.get("credit"),
            },
        ))

    household_size = _number(record, "추정가구원수", sentinel)
    one_person = household_size == 1 if household_size is not None else None
    housing = _housing_feedback(record, gu, config, sentinel) if one_person else None
    return {
        "items": items,
        "1인가구여부": one_person,
        "1인가구확인상태": "확인" if household_size is not None else "입력컬럼_없음",
        "주거피드백": housing,
        "주거지원_우선": bool(one_person),
        "분석모드": "precise",
        "외부데이터오류": external_error,
        "1인가구상세가이드": _one_person_guides(items, housing) if one_person and housing else [],
    }
