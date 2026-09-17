"""/api/transcribe and /api/tts: thin proxies to the gateway; verify wiring and error translation."""
import io

import httpx
import pytest

from app.routers import asr_router, tts_router


def _upstream_error(status: int, text: str) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "http://gateway.invalid/v1/audio")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, text=text, request=req))


def test_transcribe_forwards_audio_and_language(client, auth, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    async def fake(audio, filename, content_type, language=None):
        seen.update(audio=audio, filename=filename, content_type=content_type, language=language)
        return "  五号箱放了登山杖  "

    monkeypatch.setattr(asr_router.asr, "transcribe", fake)
    r = client.post(
        "/api/transcribe",
        files={"file": ("clip.webm", io.BytesIO(b"OggS"), "audio/webm")},
        data={"language": "zh"},
        headers=auth,
    )
    assert r.status_code == 200 and r.json() == {"text": "  五号箱放了登山杖  "}
    assert seen == {"audio": b"OggS", "filename": "clip.webm", "content_type": "audio/webm", "language": "zh"}


def test_transcribe_errors(client, auth, monkeypatch: pytest.MonkeyPatch) -> None:
    r = client.post("/api/transcribe", files={"file": ("c.webm", io.BytesIO(b""), "audio/webm")}, headers=auth)
    assert r.status_code == 400

    async def channel_closed(*a, **k):
        raise _upstream_error(503, "No available channel for model qwen3-asr-flash-realtime")

    monkeypatch.setattr(asr_router.asr, "transcribe", channel_closed)
    r = client.post("/api/transcribe", files={"file": ("c.webm", io.BytesIO(b"x"), "audio/webm")}, headers=auth)
    assert r.status_code == 502 and "No available channel" in r.json()["detail"]

    async def network(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(asr_router.asr, "transcribe", network)
    r = client.post("/api/transcribe", files={"file": ("c.webm", io.BytesIO(b"x"), "audio/webm")}, headers=auth)
    assert r.status_code == 502 and r.json()["detail"].startswith("asr_error")


def test_tts_returns_audio_bytes_with_mime(client, auth, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(text, voice=None):
        assert (text, voice) == ("在6号箱", "cherry")
        return b"RIFFwav", "audio/x-wav"

    monkeypatch.setattr(tts_router.tts, "synthesize", fake)
    r = client.post("/api/tts", json={"text": "在6号箱", "voice": "cherry"}, headers=auth)
    assert r.status_code == 200 and r.content == b"RIFFwav"
    assert r.headers["content-type"] == "audio/x-wav" and r.headers["cache-control"] == "no-store"


def test_tts_validation_and_errors(client, auth, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.post("/api/tts", json={"text": ""}, headers=auth).status_code == 422
    assert client.post("/api/tts", json={"text": "x" * 2001}, headers=auth).status_code == 422

    async def fail(text, voice=None):
        raise _upstream_error(500, "boom")

    monkeypatch.setattr(tts_router.tts, "synthesize", fail)
    r = client.post("/api/tts", json={"text": "hi"}, headers=auth)
    assert r.status_code == 502 and r.json()["detail"].startswith("tts_upstream_error")
