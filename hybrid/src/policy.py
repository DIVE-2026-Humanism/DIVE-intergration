"""정책 연결 — 기준 중위소득 등급과 사각지대를 E1~E6 위에 얹는다.

소득 등급은 정부 고시 절대 기준이라 라벨 체계와 독립적으로 성립한다(순환논리 없음).
사각지대 = 소득 기준으로는 지원 대상이 아닌데(중위 100% 초과) 종합점수는 하위인 집단.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.src import config as AC

from . import config as C


def apply_policy(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    train = out[out["split"] == "train"]
    score_cut = float(train["stability_score"].quantile(C.BLINDSPOT_SCORE_QUANTILE))

    above = out["income_to_median"] > C.BLINDSPOT_INCOME_RATIO
    blind = above & (out["stability_score"] <= score_cut)
    out["policy_blindspot"] = blind.astype("int8")
    out["R_flag"] = out["no_housing_record"].astype("int8")

    info = {
        "median_income_source": AC.MEDIAN_INCOME_SOURCE,
        "score_cut": score_cut,
        "blindspot_count": int(blind.sum()),
        "blindspot_share": float(blind.mean()),
        "blindspot_share_of_above_median": float(blind.sum() / above.sum()) if above.any() else float("nan"),
        "eligible_by_income": int(out["policy_eligible_by_income"].sum()),
        "grade_counts": {str(k): int(v) for k, v in
                         out["income_grade"].value_counts().reindex(AC.INCOME_GRADE_LABELS).fillna(0).items()},
    }
    for col, label in [("cash_advance_flag", "현금서비스"), ("dsr", "dsr"),
                       (AC.COL_SCORE, "신용평점"), ("multi_debt", "다중채무"),
                       ("stability_score", "종합점수"), (AC.COL_INCOME_Y, "추정 연소득")]:
        info[f"blindspot_{label}"] = float(pd.to_numeric(out.loc[blind, col], errors="coerce").mean())
        info[f"overall_{label}"] = float(pd.to_numeric(out[col], errors="coerce").mean())

    # 사각지대의 유형 분포 — 어느 E유형에 몰리는지
    info["blindspot_by_etype"] = {
        str(k): int(v) for k, v in out.loc[blind, "etype"].value_counts().items()
    }
    return out, info
