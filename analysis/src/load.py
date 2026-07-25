"""STEP 1 — 로딩 및 전처리 (method.md §5).

센티널을 결측으로 바꾸되 결측 자체를 신호로 보존하고(`{col}__missing`),
STEP 0에서 확정된 열 제거를 적용한다. 결측 행은 절대 삭제하지 않는다.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C


def read_raw(path: str | Path) -> pd.DataFrame:
    """utf-8-sig → 실패 시 cp949 폴백."""
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except UnicodeDecodeError as exc:  # pragma: no cover - 환경 의존
            last_err = exc
    else:  # pragma: no cover
        raise RuntimeError(f"CSV 인코딩 판별 실패: {path}") from last_err

    df.columns = [c.strip() for c in df.columns]
    missing = [c for c in C.RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    if len(df) != C.EXPECTED_ROWS:
        warnings.warn(
            f"행 수 불일치: expected {C.EXPECTED_ROWS:,} / actual {len(df):,} — 경고 후 진행",
            stacklevel=2,
        )
    df = df.reset_index(drop=True)
    df.index.name = "row_id"
    return df


def load(raw: pd.DataFrame, excluded_columns: list[str]) -> tuple[pd.DataFrame, dict]:
    """센티널 처리 · 결측 플래그 생성 · 열 제거 적용."""
    df = raw.copy()
    info: dict = {}

    # 1) 센티널 → NaN + 컬럼별 결측 플래그 (결측 자체가 신호)
    sentinel_cols: dict[str, int] = {}
    for col in C.RAW_COLUMNS:
        if col in C.CATEGORICAL_COLUMNS:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        miss = (s == C.SENTINEL) | s.isna()
        if miss.any():
            sentinel_cols[col] = int(miss.sum())
            df[f"{col}__missing"] = miss.astype("int8")
        df[col] = s.where(~miss)
    info["sentinel_missing_counts"] = sentinel_cols

    # 2) 단위 검증 — 추정월소득×12 ÷ 추정 연소득 (제거 전에 계산)
    ratio = (df[C.COL_INCOME_M] * 12) / df[C.COL_INCOME_Y].where(df[C.COL_INCOME_Y] > 0)
    info["income_unit_check"] = {
        "월소득×12 / 연소득 중앙값": float(ratio.median()),
        "p05": float(ratio.quantile(0.05)),
        "p95": float(ratio.quantile(0.95)),
        "±20% 이내 비율": float(((ratio - 1).abs() <= 0.20).mean()),
    }
    inc = df[C.COL_INCOME_Y]
    info["income_summary"] = {
        "min": float(inc.min()), "p25": float(inc.quantile(0.25)),
        "median": float(inc.median()), "p75": float(inc.quantile(0.75)),
        "max": float(inc.max()), "mean": float(inc.mean()),
    }

    # 3) 열 제거 적용
    drop = [c for c in excluded_columns if c in df.columns]
    drop += [f"{c}__missing" for c in excluded_columns if f"{c}__missing" in df.columns]
    df = df.drop(columns=drop)
    info["dropped_columns"] = [c for c in excluded_columns]
    info["n_columns_after"] = len([c for c in df.columns if not c.endswith("__missing")])

    # 4) 상수·준상수 탐지 (기록만, 자동 삭제 금지)
    quasi = {}
    for col in df.columns:
        if col.endswith("__missing"):
            continue
        vc = df[col].value_counts(dropna=True)
        if len(vc) <= 1:
            quasi[col] = {"unique": int(len(vc)), "top_share": 1.0, "constant": True}
        elif vc.iloc[0] / len(df) >= 0.99:
            quasi[col] = {
                "unique": int(len(vc)),
                "top_share": float(vc.iloc[0] / len(df)),
                "constant": False,
            }
    info["quasi_constant"] = quasi

    return df, info


def write_caveats(info: dict, outdir: Path, consistency_rates: dict[str, float]) -> None:
    """§2.4 미해결 항목 + 실행 시 관측된 가정을 `data_caveats.md`로 기록."""
    outdir.mkdir(parents=True, exist_ok=True)
    unit = info["income_unit_check"]
    inc = info["income_summary"]

    lines = [
        "# data_caveats.md — 가정 · 한계 · 발제사 확인 필요 항목\n",
        "> 이 파이프라인의 유형 라벨은 **개인 신용 판정이 아니라 정책 아웃리치 우선순위**다. "
        "개인에 대한 낙인으로 사용해서는 안 된다.\n",
        "## 1. 미해결 항목 (§2.4)\n",
        "1. **`추정가구원수` 컬럼 부재.** 발제자료는 1인가구 필터 기준으로 명시하나 실제 CSV에 없다. "
        "데이터가 이미 1인가구로 필터링되어 배포된 것으로 **확정**하고 진행했다.",
        "2. **KCB 직업군 코드북 확보 완료** (`데이터사용컬럼정의서.xlsx` [코드] 시트). "
        "410 대기업급여소득 / 420 일반급여소득 / 430 전문직급여소득 / 440 대표 / "
        "510 일반자영업 / 520 전문직자영업 / 910 무직·기타. "
        "method.md §16-4의 \"의미 부여 금지\" 전제가 해소되어 고용형태 3분류로 사용한다.",
        f"3. **금액 단위.** `추정월소득×12 ÷ 추정 연소득` 중앙값 {unit['월소득×12 / 연소득 중앙값']:.3f} "
        f"(p05 {unit['p05']:.3f} / p95 {unit['p95']:.3f}, ±20% 이내 {unit['±20% 이내 비율']:.1%}). "
        f"추정 연소득 중앙값 {inc['median']:,.0f} — **천원 단위 확정**(발제팀 확인, 2026-07-26).",
        "4. **발제 자료의 \"거주지 행정동\"과 실제 \"시군구 코드\" 불일치.** 동 단위 분석 불가.",
        "5. **연령대 15·20 구간에 재학생 혼입.** 학력 컬럼이 없어 분리 불가 — 25세 이상 민감도 분석을 병기한다.\n",
        "## 2. 결측 처리\n",
        f"- 센티널 `{C.SENTINEL}`을 NaN으로 치환하고 컬럼별 `__missing` 플래그를 생성했다. "
        "결측 행은 삭제하지 않았다(결측 자체가 취약주거 프록시일 수 있음).\n",
        "| 컬럼 | 결측 건수 | 결측률 |",
        "|---|---:|---:|",
    ]
    n_rows = int(info.get("n_rows", 0))
    for col, cnt in sorted(info["sentinel_missing_counts"].items(), key=lambda x: -x[1]):
        rate = f"{cnt / n_rows:.2%}" if n_rows else "-"
        lines.append(f"| `{col}` | {cnt:,} | {rate} |")

    lines += [
        "",
        "## 3. 상수 · 준상수 컬럼 (기록만, 자동 삭제 금지)\n",
        "| 컬럼 | 고유값 수 | 최빈값 비중 | 완전상수 |",
        "|---|---:|---:|---|",
    ]
    if info["quasi_constant"]:
        for col, meta in sorted(info["quasi_constant"].items(), key=lambda x: -x[1]["top_share"]):
            lines.append(
                f"| `{col}` | {meta['unique']} | {meta['top_share']:.2%} | "
                f"{'예' if meta['constant'] else '아니오'} |"
            )
    else:
        lines.append("| (해당 없음) | - | - | - |")

    lines += [
        "",
        "> 0이 대부분인 열은 \"값이 비었다\"가 아니라 \"해당 없음\"이라는 정보다. "
        "완전 상수 열만 삭제 대상이며, 준상수 열은 유지했다.\n",
        "## 4. 정합성 검증에 따른 보류 열 판정 (§4.4)\n",
        "| 열 | 합집합 위반율 | 결정 |",
        "|---|---:|---|",
    ]
    for col, rate in consistency_rates.items():
        decided = "제거" if col in info["dropped_columns"] else "유지"
        lines.append(f"| `{col}` | {rate:.2%} | {decided} |")
    lines.append("")

    (outdir / "data_caveats.md").write_text("\n".join(lines), encoding="utf-8")
