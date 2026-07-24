from __future__ import annotations

from copy import deepcopy
from datetime import date
import os

import pytest

from src.io_load import load_config
from src.policy_db.ingest import database_counts, ingest, load_transformed_policies, parse_application_dates, split_multi, transform_policy


def test_real_source_excludes_all_closed_and_parses_arrays() -> None:
    policies, stats = load_transformed_policies(load_config())
    assert stats == {"source": 534, "excluded_closed": 221, "loaded": 313}
    assert all(policy["aply_prd_se_cd"] != "0057003" for policy in policies)
    assert all(isinstance(policy["zip_cd"], list) for policy in policies)


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("DIVE_TEST_DATABASE_URL"), reason="PostgreSQL integration DSN not configured")
def test_postgresql_database_is_built_idempotently() -> None:
    config = deepcopy(load_config())
    config["policy_db"]["dsn_env"] = "DIVE_TEST_DATABASE_URL"
    assert ingest(config)["loaded"] == 313
    assert ingest(config)["loaded"] == 313
    assert database_counts(config) == {"policies": 313, "code_labels": 69}


def test_multi_values_dates_and_category_normalization() -> None:
    assert split_multi("A, B,A,,") == ["A", "B"]
    assert parse_application_dates("20260707 ~ 20261231") == (date(2026, 7, 7), date(2026, 12, 31))
    assert parse_application_dates("형식 이상") == (None, None)
    codebook = {
        "lclsfNm": {
            "_normalize": {
                "교육･직업훈련": "교육",
                "금융･복지･문화": "복지문화",
                "참여･기반": "참여권리",
            }
        }
    }
    base = {
        "plcyNo": "P1", "plcyAprvSttsCd": "0044002", "aplyPrdSeCd": "0057002",
        "plcyKywdNm": "대출,금리혜택", "zipCd": "26110", "jobCd": "0013010",
        "schoolCd": None, "plcyMajorCd": "0011009", "sbizCd": "0014010",
    }
    expected = {
        "일자리": "일자리", "주거": "주거", "교육･직업훈련": "교육",
        "금융･복지･문화": "복지문화", "참여･기반": "참여권리",
    }
    for source, normalized in expected.items():
        row = transform_policy({**base, "lclsfNm": source}, codebook)
        assert row["lclsf_nm"] == normalized
        assert row["school_cd"] == []
        assert row["earn_min_amt"] is None

    numeric = transform_policy({**base, "lclsfNm": "주거", "earnMinAmt": "0", "earnMaxAmt": 0}, codebook)
    assert numeric["earn_min_amt"] == 0
    assert numeric["earn_max_amt"] == 0
