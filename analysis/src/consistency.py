"""STEP 0 — 논리 정합성 검증 + 열 제거 적용 (method.md §4).

검사 26종 / 심각도 3단계(FATAL·MAJOR·MINOR)를 전수 실행하고,
§4.2 확정 제거 7열에 더해 §4.4 보류 3열을 위반율 기준으로 자동 추가한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from . import config as C


@dataclass(frozen=True)
class Check:
    id: str
    group: str
    severity: str
    desc: str
    fn: Callable[[pd.DataFrame], pd.Series]


def _num(df: pd.DataFrame) -> pd.DataFrame:
    """센티널을 NaN으로 바꾼 수치 프레임. NaN 과의 비교는 항상 False가 되어 안전하다."""
    out = df.copy()
    for col in out.columns:
        if col in C.CATEGORICAL_COLUMNS:
            continue
        s = pd.to_numeric(out[col], errors="coerce")
        out[col] = s.where(s != C.SENTINEL)
    return out


def _loan_balance_sum(d: pd.DataFrame) -> pd.Series:
    return (
        d[C.COL_CREDIT_BAL].fillna(0)
        + d[C.COL_MORT_BAL].fillna(0)
        + d[C.COL_POLICY_BAL].fillna(0)
    )


def _agreement_sum(d: pd.DataFrame) -> pd.Series:
    return (
        d[C.COL_CREDIT_AGREE].fillna(0)
        + d[C.COL_MORT_AGREE].fillna(0)
        + d[C.COL_POLICY_AGREE].fillna(0)
    )


def _delinq_cnt(d: pd.DataFrame) -> pd.Series:
    return d[C.COL_DELINQ_LOAN_CNT].fillna(0) + d[C.COL_DELINQ_CARD_CNT].fillna(0)


def _delinq_amt(d: pd.DataFrame) -> pd.Series:
    return d[C.COL_DELINQ_LOAN_AMT].fillna(0) + d[C.COL_DELINQ_CARD_AMT].fillna(0)


CHECKS: list[Check] = [
    # ---------------------------------------------------------------- A. 자산
    Check("A1", "A.자산", "FATAL", "순자산평가금액 > 총자산평가금액",
          lambda d: d[C.COL_ASSET_NET] > d[C.COL_ASSET_TOTAL]),
    Check("A2", "A.자산", "MAJOR", "총자산 > 0 인데 현 거주지 매매가가 0·결측",
          lambda d: (d[C.COL_ASSET_TOTAL] > 0) & ~(d[C.COL_HOME_PRICE] > 0)),
    # ---------------------------------------------------------------- B. 대출
    Check("B1", "B.대출", "FATAL", "총대출건수 = 0 인데 대출잔액 합 > 0",
          lambda d: (d[C.COL_LOAN_CNT] == 0) & (_loan_balance_sum(d) > 0)),
    Check("B2", "B.대출", "MAJOR", "총대출건수 > 0 인데 약정·잔액이 모두 0",
          lambda d: (d[C.COL_LOAN_CNT] > 0) & (_loan_balance_sum(d) == 0) & (_agreement_sum(d) == 0)),
    Check("B3", "B.대출", "FATAL", "신용대출 약정 = 0 인데 잔액 > 0",
          lambda d: (d[C.COL_CREDIT_AGREE].fillna(0) == 0) & (d[C.COL_CREDIT_BAL] > 0)),
    Check("B4", "B.대출", "FATAL", "주택담보대출 잔액 > 약정",
          lambda d: d[C.COL_MORT_BAL] > d[C.COL_MORT_AGREE]),
    Check("B5", "B.대출", "FATAL", "주택담보대출 약정 = 0 인데 잔액 > 0",
          lambda d: (d[C.COL_MORT_AGREE].fillna(0) == 0) & (d[C.COL_MORT_BAL] > 0)),
    Check("B6", "B.대출", "FATAL", "정책자금대출 잔액 > 약정",
          lambda d: d[C.COL_POLICY_BAL] > d[C.COL_POLICY_AGREE]),
    Check("B7", "B.대출", "MAJOR", "총대출건수 = 0 인데 추정DTI > 0",
          lambda d: (d[C.COL_LOAN_CNT] == 0) & (d[C.COL_DTI] > 0)),
    Check("B8", "B.대출", "MAJOR", "총대출건수 = 0 인데 12개월 상환금액 > 0",
          lambda d: (d[C.COL_LOAN_CNT] == 0) & (d[C.COL_REPAY_12M] > 0)),
    # ---------------------------------------------------------------- C. 카드
    Check("C1", "C.카드", "MAJOR", "일시불 + 할부 > 신용 + 체크 소비 합",
          lambda d: (d[C.COL_CARD_LUMP].fillna(0) + d[C.COL_CARD_INSTALL].fillna(0))
                    > (d[C.COL_CARD_CREDIT].fillna(0) + d[C.COL_CARD_CHECK].fillna(0))),
    Check("C2", "C.카드", "MAJOR", "현금서비스 > 0 인데 신용카드 소비 = 0",
          lambda d: (d[C.COL_CASH_ADVANCE] > 0) & (d[C.COL_CARD_CREDIT].fillna(0) == 0)),
    Check("C3", "C.카드", "MAJOR", "일시불 > 신용카드 소비금액 (부분집합 위반)",
          lambda d: d[C.COL_CARD_LUMP] > d[C.COL_CARD_CREDIT]),
    # ---------------------------------------------------------------- D. 연체
    Check("D1", "D.연체", "MAJOR", "연체건수 > 0 인데 연체금액 합 = 0",
          lambda d: (_delinq_cnt(d) > 0) & (_delinq_amt(d) == 0)),
    Check("D2", "D.연체", "MAJOR", "연체금액 합 > 0 인데 연체건수 = 0",
          lambda d: (_delinq_amt(d) > 0) & (_delinq_cnt(d) == 0)),
    Check("D3", "D.연체", "MAJOR", "연체건수 > 0 인데 연체일수 = 0",
          lambda d: (_delinq_cnt(d) > 0) & (d[C.COL_DELINQ_DAYS].fillna(0) == 0)),
    Check("D4", "D.연체", "MAJOR", "연체일수 > 0 인데 연체건수 = 0",
          lambda d: (d[C.COL_DELINQ_DAYS] > 0) & (_delinq_cnt(d) == 0)),
    Check("D5", "D.연체", "MAJOR", "연체금액 합 > 총대출잔액 합",
          lambda d: (_delinq_amt(d) > 0) & (_delinq_amt(d) > _loan_balance_sum(d))),
    # ---------------------------------------------------------------- E. 소득
    Check("E1", "E.소득", "FATAL", "추정 연소득 <= 0",
          lambda d: ~(d[C.COL_INCOME_Y] > 0)),
    Check("E2", "E.소득", "MINOR", "|추정월소득×12 − 추정 연소득| / 추정 연소득 > 20%",
          lambda d: ((d[C.COL_INCOME_M] * 12 - d[C.COL_INCOME_Y]).abs()
                     / d[C.COL_INCOME_Y].where(d[C.COL_INCOME_Y] > 0)) > 0.20),
    Check("E3", "E.소득", "MINOR", "증빙연소득 > 추정 연소득 × 2 (괴리)",
          lambda d: d[C.COL_INCOME_VERIFIED] > d[C.COL_INCOME_Y] * 2),
    Check("E4", "E.소득", "MAJOR", "2년전 추정 연소득 <= 0",
          lambda d: ~(d[C.COL_INCOME_Y_PREV] > 0)),
    # ---------------------------------------------------------------- F. Thin Filer
    Check("F1", "F.ThinFiler", "MAJOR", "Thin Filer = 1 인데 대출·카드 금융활동 존재",
          lambda d: (d[C.COL_THIN] == 1)
                    & ((d[C.COL_LOAN_CNT].fillna(0) > 0)
                       | (_loan_balance_sum(d) > 0)
                       | (d[C.COL_CARD_CREDIT].fillna(0) > 0))),
    # ---------------------------------------------------------------- G. 고용
    Check("G1", "G.고용", "MAJOR", "2년내 직장이력 = 0 인데 이직후 소득 증감액 ≠ 0",
          lambda d: (d[C.COL_JOB_HIST].fillna(0) == 0) & (d[C.COL_JOB_CHANGE_INCOME].fillna(0) != 0)),
    # ---------------------------------------------------------------- H. 주거
    Check("H1", "H.주거", "MAJOR", "2년내 평균전세가 > 현 거주지 매매가",
          lambda d: d[C.COL_JEONSE_2Y] > d[C.COL_HOME_PRICE]),
    Check("H2", "H.주거", "MAJOR", "자가거주(코드 ≠ 3) 인데 총자산평가금액 = 0",
          lambda d: (d[C.COL_OWNERSHIP] != 3) & ~(d[C.COL_ASSET_TOTAL] > 0)),
]


@dataclass
class ConsistencyResult:
    table: pd.DataFrame
    flags: pd.DataFrame
    provisional_added: list[str] = field(default_factory=list)
    provisional_rates: dict[str, float] = field(default_factory=dict)

    @property
    def excluded_columns(self) -> list[str]:
        return list(C.EXCLUDED_COLUMNS) + self.provisional_added


def run_checks(raw: pd.DataFrame) -> ConsistencyResult:
    d = _num(raw)
    n = len(d)

    flags = pd.DataFrame(index=raw.index)
    rows = []
    for chk in CHECKS:
        mask = chk.fn(d).fillna(False).astype(bool)
        flags[chk.id] = mask.astype("int8")
        rows.append(
            {
                "id": chk.id,
                "group": chk.group,
                "severity": chk.severity,
                "check": chk.desc,
                "violations": int(mask.sum()),
                "rate": float(mask.mean()),
            }
        )
    table = pd.DataFrame(rows)

    # §4.4 보류 3열: 판정 검사들의 합집합 위반율이 임계 초과면 자동 제거
    added, rates = [], {}
    for col, ids in C.PROVISIONAL_EXCLUSIONS.items():
        union = np.zeros(n, dtype=bool)
        for cid in ids:
            union |= flags[cid].to_numpy().astype(bool)
        rate = float(union.mean())
        rates[col] = rate
        if rate > C.PROVISIONAL_VIOLATION_THRESHOLD:
            added.append(col)

    return ConsistencyResult(table=table, flags=flags, provisional_added=added, provisional_rates=rates)


def write_report(res: ConsistencyResult, outdir: Path, n_rows: int) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    res.flags.to_csv(outdir / "consistency_flags.csv", index_label="row_id")

    t = res.table.copy()
    t["rate_pct"] = (t["rate"] * 100).round(2)

    lines: list[str] = []
    lines.append("# consistency_report.md — 논리 정합성 전수 검증 (STEP 0)\n")
    lines.append(f"- 검사 대상: **{n_rows:,}행 × {len(C.RAW_COLUMNS)}열**")
    lines.append(f"- 검사 항목: **{len(CHECKS)}종** (FATAL / MAJOR / MINOR)")
    lines.append("- 센티널 `-99999999`는 결측으로 간주하고, 결측 행은 검사에서 위반으로 세지 않는다.\n")

    lines.append("## 심각도별 요약\n")
    summary = t.groupby("severity", as_index=False).agg(
        검사수=("id", "count"), 위반합=("violations", "sum")
    )
    lines.append("| 심각도 | 검사 수 | 위반 건수 합 |")
    lines.append("|---|---:|---:|")
    for sev in ["FATAL", "MAJOR", "MINOR"]:
        sub = summary[summary["severity"] == sev]
        if len(sub):
            lines.append(f"| {sev} | {int(sub['검사수'].iloc[0])} | {int(sub['위반합'].iloc[0]):,} |")
    lines.append("")

    lines.append("## 검사 26종 상세\n")
    lines.append("| ID | 그룹 | 심각도 | 검사 | 위반 건수 | 위반율 |")
    lines.append("|---|---|---|---|---:|---:|")
    for _, r in t.iterrows():
        lines.append(
            f"| {r['id']} | {r['group']} | {r['severity']} | {r['check']} | "
            f"{int(r['violations']):,} | {r['rate_pct']:.2f}% |"
        )
    lines.append("")

    lines.append("## 열 제거 결정\n")
    lines.append("### 확정 제거 7열 (§4.2, 승인 대기 없이 즉시 적용)\n")
    lines.append("| # | 삭제 열 | 사유 |")
    lines.append("|---:|---|---|")
    for i, col in enumerate(C.EXCLUDED_COLUMNS, start=1):
        lines.append(f"| {i} | `{col}` | {C.EXCLUSION_REASONS[col]} |")
    lines.append("")

    lines.append(f"### 보류 3열 (§4.4, 위반율 {C.PROVISIONAL_VIOLATION_THRESHOLD:.0%} 초과 시 자동 추가)\n")
    lines.append("| 열 | 판정 검사 | 합집합 위반율 | 결정 |")
    lines.append("|---|---|---:|---|")
    for col, ids in C.PROVISIONAL_EXCLUSIONS.items():
        rate = res.provisional_rates.get(col, float("nan"))
        decided = "**제거**" if col in res.provisional_added else "유지"
        lines.append(f"| `{col}` | {' + '.join(ids)} | {rate * 100:.2f}% | {decided} |")
    lines.append("")

    lines.append("### 삭제하지 않은 희소 열 (§4.3)\n")
    lines.append("분산이 낮은 것과 정보가 없는 것은 다르다. 0이 대부분이라는 건 \"해당 없음\"이라는 정보이며, "
                 "희소한 쪽이 오히려 강한 신호다. 완전 상수 열만 삭제 대상이다.\n")
    lines.append(f"**최종 제거 열 {len(res.excluded_columns)}개** → "
                 f"{len(C.RAW_COLUMNS)}열 → {len(C.RAW_COLUMNS) - len(res.excluded_columns)}열\n")

    (outdir / "consistency_report.md").write_text("\n".join(lines), encoding="utf-8")
