"""语音转写:转发到网关的 OpenAI 兼容 /v1/audio/transcriptions。

模型由 settings.asr_model 配置(默认 qwen3-asr-flash-realtime)。网关开通对应
通道后即可生效,无需改代码。
"""
import httpx

from ..config import settings


async def transcribe(audio: bytes, filename: str, content_type: str, language: str | None = None) -> str:
    """把音频转成文字。失败时抛 httpx.HTTPStatusError(由路由转成可读错误)。"""
    data = {"model": settings.asr_model}
    if language:
        data["language"] = language
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{settings.llm_base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            files={"file": (filename or "audio.webm", audio, content_type or "audio/webm")},
            data=data,
        )
        r.raise_for_status()
        body = r.json()
    # OpenAI 兼容格式: {"text": "..."}
    return (body.get("text") or "").strip()
