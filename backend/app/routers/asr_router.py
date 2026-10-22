import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..auth import get_current_user
from ..models import User
from ..services import asr

router = APIRouter(prefix="/api", tags=["asr"])


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    user: User = Depends(get_current_user),
):
    """音频 → 文字。无限制使用,不计次。"""
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "empty audio")
    try:
        text = await asr.transcribe(audio, file.filename or "audio.webm", file.content_type or "audio/webm", language)
    except httpx.HTTPStatusError as e:
        # 把网关错误透传成可读信息(如模型通道未开通的 503)
        detail = e.response.text[:300] if e.response is not None else str(e)
        raise HTTPException(502, f"asr_upstream_error: {detail}") from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"asr_error: {e}") from e
    return {"text": text}
