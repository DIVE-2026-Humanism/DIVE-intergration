from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from .config import CONDITIONAL_EXCLUSIONS, EXCLUDED_COLUMNS


def _checks(df: pd.DataFrame) -> list[tuple[str, str, str, Callable[[pd.DataFrame], pd.Series]]]:
    loan_bal = df[["신용대출-총대출잔액", "주택담보대출-총대출잔액", "정책자금대출-총대출잔액"]].sum(axis=1)
    loan_commit = df[["신용대출-총대출약정액", "주택담보대출-총대출약정액", "정책자금대출-총대출약정액"]].sum(axis=1)
    dc = df["대출연체건수"] + df["카드연체건수"]
    da = df["대출연체금액"] + df["카드연체금액"]
    return [
        ("A1", "MAJOR", "순자산 > 총자산", lambda x: x["순자산평가금액(주택)"] > x["총자산평가금액(주택)"]),
        ("A2", "MINOR", "자산 있으나 매매가 0", lambda x: (x["총자산평가금액(주택)"] > 0) & x["현 거주지의 매매가(국토부 실거래가) 또는 공시가격"].fillna(0).eq(0)),
        ("B1", "MAJOR", "대출 0건인데 잔액 존재", lambda x: x["총대출건수"].eq(0) & loan_bal.gt(0)),
        ("B2", "MAJOR", "대출 건수 있는데 잔액·약정 없음", lambda x: x["총대출건수"].gt(0) & loan_bal.eq(0) & loan_commit.eq(0)),
        ("B3", "MAJOR", "총 잔액 > 총 약정", lambda x: loan_bal > loan_commit),
        ("B4", "MAJOR", "주담대 잔액 > 약정", lambda x: x["주택담보대출-총대출잔액"] > x["주택담보대출-총대출약정액"]),
        ("B5", "MAJOR", "주담대 약정 0인데 잔액 존재", lambda x: x["주택담보대출-총대출약정액"].eq(0) & x["주택담보대출-총대출잔액"].gt(0)),
        ("B6", "MINOR", "대출 0건인데 상환액 존재", lambda x: x["총대출건수"].eq(0) & x["총 대출 상환금액 (최근 12개월)"].gt(0)),
        ("B7", "MAJOR", "대출 0건인데 DTI 존재", lambda x: x["총대출건수"].eq(0) & x["추정DTI"].gt(0)),
        ("C1", "MAJOR", "일시불+할부 > 신용+체크 소비", lambda x: (x["최근 12개월 일시불이용금액"] + x["최근 12개월 할부이용금액"]) > (x["최근 12개월 신용카드소비금액"] + x["최근 12개월 체크카드소비금액"])),
        ("C2", "MINOR", "현금서비스 > 신용카드 소비", lambda x: x["최근 12개월 현금서비스이용금액"] > x["최근 12개월 신용카드소비금액"]),
        ("C3", "MINOR", "카드 소비 0인데 일시불·할부 존재", lambda x: (x["최근 12개월 신용카드소비금액"] + x["최근 12개월 체크카드소비금액"]).eq(0) & (x["최근 12개월 일시불이용금액"] + x["최근 12개월 할부이용금액"]).gt(0)),
        ("D1", "MAJOR", "연체 건수 0인데 금액 존재", lambda x: dc.eq(0) & da.gt(0)),
        ("D2", "MAJOR", "연체 건수 있는데 금액 0", lambda x: dc.gt(0) & da.eq(0)),
        ("D3", "MAJOR", "연체 건수 0인데 일수 존재", lambda x: dc.eq(0) & x["연체일수"].gt(0)),
        ("D4", "MAJOR", "연체 건수 있는데 일수 0", lambda x: dc.gt(0) & x["연체일수"].fillna(0).eq(0)),
        ("D5", "MINOR", "연체금액 > 총대출잔액", lambda x: da > loan_bal),
        ("E1", "MINOR", "증빙소득이 추정소득의 2배 초과", lambda x: x["증빙연소득"] > x["추정 연소득"] * 2),
        ("E2", "MAJOR", "월소득×12와 연소득 50% 이상 괴리", lambda x: ((x["추정월소득"] * 12 - x["추정 연소득"]).abs() / x["추정 연소득"]).gt(.5)),
        ("E3", "FATAL", "추정 연소득 0", lambda x: x["추정 연소득"].fillna(0).eq(0)),
        ("F1", "MINOR", "Thin Filer인데 대출 존재", lambda x: x["Thin Filer 여부"].eq(1) & x["총대출건수"].gt(0)),
        ("F2", "MINOR", "Thin Filer인데 카드소비 존재", lambda x: x["Thin Filer 여부"].eq(1) & (x["최근 12개월 신용카드소비금액"] + x["최근 12개월 체크카드소비금액"]).gt(0)),
        ("G1", "MAJOR", "직장이력 0인데 이직소득 증감 존재", lambda x: x["2년내 직장명이력건수"].eq(0) & x["2년내 이직후 소득 증감액"].ne(0)),
        ("H1", "MINOR", "전세가 > 매매가", lambda x: x["2년내 현거주지평균전세거래가"] > x["현 거주지의 매매가(국토부 실거래가) 또는 공시가격"]),
        ("H2", "MAJOR", "자가인데 주택자산 0", lambda x: x["자가거주여부"].ne(3) & x["총자산평가금액(주택)"].fillna(0).eq(0)),
        ("H3", "MINOR", "주담대 있는데 주택자산 0", lambda x: x["주택담보대출-총대출잔액"].gt(0) & x["총자산평가금액(주택)"].fillna(0).eq(0)),
    ]


def check_consistency(df: pd.DataFrame, outdir: Path) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    rows = []
    masks = {}
    for code, severity, description, function in _checks(df):
        mask = function(df).fillna(False)
        count = int(mask.sum())
        rate = count / len(df)
        rows.append({"code": code, "severity": severity, "description": description, "count": count, "rate": rate})
        masks[code] = mask
    report = pd.DataFrame(rows)
    excluded = list(EXCLUDED_COLUMNS)
    for column, codes in CONDITIONAL_EXCLUSIONS.items():
        # A row violating multiple related checks must count only once.
        combined = pd.concat([masks[code] for code in codes], axis=1).any(axis=1)
        if float(combined.mean()) > .30:
            excluded.append(column)
    flags = pd.DataFrame({"row_id": df["row_id"]})
    for code, mask in masks.items():
        flags[code] = mask.astype("int8")
    flags.to_csv(outdir / "consistency_flags.csv", index=False)
    lines = ["# 논리 정합성 검증", "", f"- 검사: {len(report)}종", f"- 확정·조건부 제거 열: {len(excluded)}개", "", "|코드|심각도|검사|건수|위반율|", "|---|---|---|---:|---:|"]
    lines += [f"|{r.code}|{r.severity}|{r.description}|{r.count:,}|{r.rate:.2%}|" for r in report.itertuples()]
    lines += ["", "## 적용된 제거 열", "", *[f"- `{c}`" for c in excluded]]
    (outdir / "consistency_report.md").write_text("\n".join(lines), encoding="utf-8")
    return df.drop(columns=excluded, errors="ignore"), excluded, report
