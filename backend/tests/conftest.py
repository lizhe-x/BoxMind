"""Shared fixtures.

The suite runs against a real PostgreSQL + pgvector database (a throwaway
`boxmind_test` database, created on demand) so that vector search, cascades
and undo snapshots are exercised for real. Two things are faked:

* embeddings -- a deterministic hash-based 384-d vector, so tests never
  download the fastembed model and identical strings always match;
* the LLM gateway -- a scripted client that returns pre-programmed
  tool calls / messages and records every request it received.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# ── environment must be set before the app is imported ────────────────
TEST_DB_URL = os.environ.get(
    "BOXMIND_TEST_DATABASE_URL",
    "postgresql+psycopg://boxmind:boxmind@127.0.0.1:5434/boxmind_test",
)
os.environ["BOXMIND_DATABASE_URL"] = TEST_DB_URL
os.environ["BOXMIND_EMBEDDING_PROVIDER"] = "remote"  # keeps warmup() a no-op; embed() is patched below
os.environ["BOXMIND_EMBEDDING_DIM"] = "384"
os.environ["BOXMIND_LLM_API_KEY"] = "test-key"
os.environ["BOXMIND_LLM_BASE_URL"] = "http://gateway.invalid/v1"
os.environ["BOXMIND_SMTP_HOST"] = ""  # dev mode: login code returned by the API
os.environ["BOXMIND_JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"  # ≥32 bytes for HS256
os.environ["BOXMIND_MEDIA_DIR"] = tempfile.mkdtemp(prefix="boxmind-media-")
os.environ["BOXMIND_FRONTEND_DIST"] = os.path.join(tempfile.gettempdir(), "boxmind-no-dist")


def _ensure_test_database() -> None:
    """Create the test database if it does not exist yet."""
    admin_url = TEST_DB_URL.rsplit("/", 1)[0] + "/postgres"
    dbname = TEST_DB_URL.rsplit("/", 1)[1]
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin.dispose()


_ensure_test_database()

from app import db as app_db  # noqa: E402
from app import models  # noqa: E402
from app.services import embeddings  # noqa: E402

DIM = 384


def fake_vector(text_: str) -> list[float]:
    """Deterministic unit vector derived from the text hash."""
    seed = int.from_bytes(hashlib.sha256(text_.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    v = [rng.gauss(0, 1) for _ in range(DIM)]
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


async def fake_embed(texts: list[str]) -> list[list[float]]:
    return [fake_vector(t) for t in texts]


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    app_db.init_db()
    yield


@pytest.fixture(autouse=True)
def _patch_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    # every module does `from . import embeddings` and calls embeddings.embed → one patch covers all
    monkeypatch.setattr(embeddings, "embed", fake_embed)


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with app_db.engine.begin() as conn:
        names = ", ".join(t.name for t in reversed(app_db.Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture
def db() -> Iterator[Session]:
    s = app_db.SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def user(db: Session) -> models.User:
    u = models.User(device_id="test-device-0001", email="tester@example.com")
    db.add(u)
    db.commit()
    return u


# ── scripted LLM ───────────────────────────────────────────────────────
def tool_call(name: str, args: dict[str, Any] | str, call_id: str = "call_1") -> dict:
    """Build an OpenAI-style tool_call entry. `args` may be a raw string to simulate bad JSON."""
    arguments = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def assistant_msg(content: str | None = None, tool_calls: list[dict] | None = None) -> dict:
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


class ScriptedLLM:
    """Stand-in for app.services.llm.LLM: replays scripted responses and records requests."""

    def __init__(self) -> None:
        self.tool_replies: list[dict] = []
        self.interpret_reply: dict = {
            "intent": "query", "box_label": None, "items": [], "location_text": None, "language": "zh",
        }
        self.vision_reply: dict = {"box_label": None, "items": []}
        self.answer_chunks: list[str] = ["好的", "。"]
        self.answer_error: Exception | None = None
        self.calls: list[dict] = []  # every chat_with_tools request: {"messages": [...], "tools": [...]}
        self.interpret_calls: list[tuple[str, list[str]]] = []
        self.vision_calls: list[tuple[str, str]] = []
        self.answer_calls: list[tuple[str, str, str]] = []

    def script(self, *replies: dict) -> ScriptedLLM:
        self.tool_replies.extend(replies)
        return self

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        if not self.tool_replies:
            raise AssertionError("ScriptedLLM: no scripted reply left for chat_with_tools")
        return self.tool_replies.pop(0)

    async def interpret(self, text_: str, known_labels: list[str], lang: str | None = None) -> dict:
        self.interpret_calls.append((text_, list(known_labels), lang))
        return dict(self.interpret_reply)

    async def recognize_image(self, image_b64: str, mime: str = "image/jpeg", lang: str | None = None) -> dict:
        self.vision_calls.append((image_b64, mime, lang))
        return dict(self.vision_reply)

    async def answer_stream(self, question: str, context_json: str, relevant_hint: str):
        self.answer_calls.append((question, context_json, relevant_hint))
        if self.answer_error:
            raise self.answer_error
        for c in self.answer_chunks:
            yield c


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> ScriptedLLM:
    """Patch the shared `llm` singleton everywhere it was imported by name."""
    from app.routers import ask_router, ingest_router, vision_router
    from app.services import agent

    fake = ScriptedLLM()
    for mod in (agent, ask_router, ingest_router, vision_router):
        monkeypatch.setattr(mod, "llm", fake)
    return fake


# ── HTTP client ────────────────────────────────────────────────────────
@pytest.fixture
def client(llm: ScriptedLLM):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client) -> dict[str, str]:
    """Log in through the real email-code flow (dev mode) and return auth headers."""
    r = client.post("/api/auth/request-code", json={"email": "Tester@Example.com"})
    assert r.status_code == 200, r.text
    code = r.json()["dev_code"]
    r = client.post("/api/auth/verify-code", json={"email": "tester@example.com", "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
