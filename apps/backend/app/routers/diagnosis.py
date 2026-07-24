from fastapi import APIRouter

from app.schemas.diagnosis import DiagnoseRequest
from app.services import ai_client, kcb_samples

router = APIRouter(tags=["diagnosis"])


@router.post("/diagnose")
async def diagnose(req: DiagnoseRequest) -> dict:
    """라이트/정밀 진단 relay. ai-server 응답을 그대로 전달한다(passthrough)."""
    payload: dict = {
        "mode": req.mode,
        "user_inputs": req.user_inputs.model_dump(),
    }
    if req.mode == "precise":
        payload["kcb_record"] = kcb_samples.get_kcb_record(req.sampleId)

    return await ai_client.diagnose(payload)
