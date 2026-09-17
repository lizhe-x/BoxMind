import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..models import User
from ..services import tts

router = APIRouter(prefix="/api", tags=["tts"])


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str | None = None


@router.post("/tts")
async def synthesize(body: TTSIn, user: User = Depends(get_current_user)):
    """文字 → 语音音频(无限制使用,不计次)。"""
    try:
        audio, mime = await tts.synthesize(body.text, body.voice)
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:300] if e.response is not None else str(e)
        raise HTTPException(502, f"tts_upstream_error: {detail}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"tts_error: {e}")
    return Response(content=audio, media_type=mime, headers={"Cache-Control": "no-store"})
