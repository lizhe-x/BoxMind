"""语音合成:转发到网关 OpenAI 兼容 /v1/audio/speech(qwen3-tts-flash)。返回音频字节 + MIME。"""
import httpx

from ..config import settings


async def synthesize(text: str, voice: str | None = None) -> tuple[bytes, str]:
    payload = {
        "model": settings.tts_model,
        "input": text,
        "voice": voice or settings.tts_voice,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{settings.llm_base_url}/audio/speech",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "audio/wav")
