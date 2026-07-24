"""정밀 진단용 KCB 샘플 로더.

정밀 진단은 실제 휴대폰 인증·마이데이터 연동을 하지 않는다. 대신 프론트가
`sampleId`만 보내면 여기서 KCB 43필드 레코드를 붙여 ai-server로 전달한다
(API명세_v0.1.md §3-3).

실제 KCB 샘플 데이터는 아직 준비되지 않았다 (AGENTS.md 4장 / 핸드오프 §8
미확정 항목). 43개 필드를 지어내면 그럴듯한 자리표시자가 그대로 데모에
나갈 위험이 있으므로(AGENTS.md 2장), 여기서는 절대 하지 않는다 — 샘플이
없으면 명확한 에러로 실패시킨다.

샘플 준비 방법: `app/data/kcb_samples.json`에
    { "sample-01": { <KCB 43필드, 필드명 공백까지 원본 그대로> }, ... }
형태로 실데이터를 채워 넣는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.common import AppError

_SAMPLES_PATH = Path(__file__).resolve().parent.parent / "data" / "kcb_samples.json"
DEFAULT_SAMPLE_ID = "sample-01"


def _load() -> dict[str, dict]:
    if not _SAMPLES_PATH.exists():
        return {}
    return json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))


def get_kcb_record(sample_id: str | None) -> dict:
    sid = sample_id or DEFAULT_SAMPLE_ID
    record = _load().get(sid)
    if record is None:
        raise AppError(
            "KCB_SAMPLE_NOT_READY",
            f"KCB 샘플 데이터가 아직 준비되지 않았습니다 ({sid}).",
            503,
            "sampleId",
        )
    return record
