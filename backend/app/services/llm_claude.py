"""LLM provider backed by the Claude Code CLI (`claude -p`), billed to the Claude subscription the CLI is
logged into instead of a gateway API key.

Meant for the personal test server only: every request spawns one `claude` process (~1–2 s of overhead),
there is no ASR/TTS (the iOS app does both on-device), and a subscription is not a production backend.
Select it with BOXMIND_LLM_PROVIDER=claude_code; the gateway provider stays the default.

Mapping onto the gateway interface:
- interpret / recognize_image  → `--json-schema` structured output (the CLI validates the JSON)
- chat_with_tools              → tools described in the system prompt, the model answers with
                                 {content, tool_calls:[{name, arguments}]}; converted to the OpenAI shape
                                 the agent loop already understands. Each turn is a fresh process, so the
                                 whole conversation (incl. tool results) is replayed as a transcript.
- answer_stream                → `--output-format stream-json --include-partial-messages`, text deltas
- recognize_image              → image written to the work dir, the model reads it with the Read tool
"""
import asyncio
import base64
import json
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from ..config import settings
from ..i18n import lang_name, tr
from .llm import _ANSWER_SYSTEM, _INTERPRET_SYSTEM, _VISION_SYSTEM, LLM, _parse_json


class ClaudeCodeError(RuntimeError):
    """The CLI failed (not installed, not logged in, rate limited, timed out...)."""


_INTERPRET_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["ingest", "query", "operation"]},
        "box_label": {"type": ["string", "null"]},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "qty_text": {"type": "string"}}, "required": ["name", "qty_text"]}},
        "location_text": {"type": ["string", "null"]},
        "language": {"type": "string", "enum": ["zh", "en", "es"]},
    },
    "required": ["intent", "box_label", "items", "location_text", "language"],
}

_VISION_SCHEMA = {
    "type": "object",
    "properties": {
        "box_label": {"type": ["string", "null"]},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "qty_text": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]}},
            "required": ["name", "qty_text", "confidence"]}},
    },
    "required": ["box_label", "items"],
}

_TOOL_PROTOCOL = """

Tools
-----
You cannot run anything yourself. To act, return tool calls and the app executes them and shows you the
results in the next turn. Available tools (arguments are JSON objects following these schemas):
{tools}

Respond with exactly one JSON object:
{{"content": string | null, "tool_calls": [{{"name": string, "arguments": object}}]}}
- Need to act → fill tool_calls (several per turn are fine when they are independent); content may be null.
- Nothing left to do, or a clarifying question → put the sentence in content and send an empty tool_calls array.
- Never invent tool results; wait for them."""

_MIME_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic", "image/gif": "gif"}


class ClaudeCodeLLM(LLM):
    def __init__(self) -> None:
        super().__init__()
        self._bin = settings.claude_bin or shutil.which("claude") or str(Path.home() / ".local/bin/claude")
        self._sem = asyncio.Semaphore(max(1, settings.claude_concurrency))
        # Empty cwd: no CLAUDE.md / project settings leak into the prompts, and uploaded photos land here.
        self._work = Path(settings.media_dir).resolve() / ".claude-work"
        self._work.mkdir(parents=True, exist_ok=True)

    # ── public interface (same as LLM) ─────────────────────────────────
    async def interpret(self, text: str, known_labels: list[str], lang: str | None = None) -> dict:
        hint = f"The user's existing box labels: {', '.join(known_labels)}" if known_labels \
            else "The user has no boxes yet"
        system = _INTERPRET_SYSTEM.format(some=tr(lang, "qty_some"))
        parsed, tokens = await self._json(system, f"{hint}\n\nUser said: {text}", _INTERPRET_SCHEMA,
                                          settings.claude_model)
        parsed.setdefault("intent", "query")
        parsed.setdefault("box_label", None)
        parsed.setdefault("items", [])
        parsed.setdefault("location_text", None)
        parsed.setdefault("language", lang or "en")
        parsed["_tokens"] = tokens
        return parsed

    async def recognize_image(self, image_b64: str, mime: str = "image/jpeg", lang: str | None = None) -> dict:
        system = _VISION_SYSTEM.format(lang=lang_name(lang), some=tr(lang, "qty_some"))
        path = self._work / f"photo-{uuid.uuid4().hex}.{_MIME_EXT.get(mime, 'jpg')}"
        path.write_bytes(base64.b64decode(image_b64))
        prompt = (f"Use the Read tool to look at the photo {path.name} in the current directory. Then identify "
                  "the items and the handwritten label in this photo of a storage box. Output JSON as instructed.")
        try:
            parsed, _ = await self._json(system, prompt, _VISION_SCHEMA, settings.claude_vision_model,
                                         tools=["Read"], timeout=180)
        finally:
            path.unlink(missing_ok=True)
        parsed.setdefault("box_label", None)
        parsed.setdefault("items", [])
        return parsed

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        names = [t["function"]["name"] for t in tools]
        system += _TOOL_PROTOCOL.format(tools=json.dumps([t["function"] for t in tools], ensure_ascii=False))
        schema = {
            "type": "object",
            "properties": {
                "content": {"type": ["string", "null"]},
                "tool_calls": {"type": "array", "items": {"type": "object", "properties": {
                    "name": {"type": "string", "enum": names}, "arguments": {"type": "object"}},
                    "required": ["name", "arguments"]}},
            },
            "required": ["content", "tool_calls"],
        }
        reply, _ = await self._json(system, _transcript(messages), schema, settings.claude_model)
        msg: dict = {"role": "assistant", "content": reply.get("content")}
        calls = [c for c in reply.get("tool_calls") or [] if isinstance(c, dict) and c.get("name") in names]
        if calls:
            msg["tool_calls"] = [{
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {"name": c["name"], "arguments": json.dumps(c.get("arguments") or {}, ensure_ascii=False)},
            } for c in calls]
        return msg

    async def answer_stream(self, question: str, context_json: str, relevant_hint: str) -> AsyncIterator[str]:
        prompt = (f"Box data:\n{context_json}\n\n"
                  f"Relevance hints (top vector-search hits): {relevant_hint}\n\n"
                  f"Question: {question}")
        args = self._args(settings.claude_model) + ["--output-format", "stream-json", "--verbose",
                                                    "--include-partial-messages", "--system-prompt", _ANSWER_SYSTEM]
        streamed = False
        final: dict | None = None
        async for line in self._stream_lines(args, prompt):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "stream_event":
                inner = event.get("event") or {}
                delta = inner.get("delta") or {}
                is_text = inner.get("type") == "content_block_delta" and delta.get("type") == "text_delta"
                if is_text and delta.get("text"):
                    streamed = True
                    yield delta["text"]
            elif kind == "result":
                final = event
        if final is None:
            raise ClaudeCodeError("claude exited without a result")
        if final.get("is_error") or final.get("subtype") != "success":
            raise ClaudeCodeError(_error_text(final))
        if not streamed and final.get("result"):
            yield str(final["result"])

    # ── plumbing ───────────────────────────────────────────────────────
    def _args(self, model: str, tools: list[str] | None = None) -> list[str]:
        tools = tools or []
        args = [self._bin, "-p", "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
                "--model", model, "--tools", ",".join(tools)]
        if tools:
            args += ["--allowedTools", ",".join(tools)]
        return args

    async def _json(self, system: str, prompt: str, schema: dict, model: str, *, tools: list[str] | None = None,
                    timeout: float = 120) -> tuple[dict, int]:
        args = self._args(model, tools) + ["--output-format", "json", "--system-prompt", system,
                                           "--json-schema", json.dumps(schema)]
        out = await self._run(args, prompt, timeout)
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            raise ClaudeCodeError(f"unreadable claude output: {out[:200]!r}") from e
        if data.get("is_error") or data.get("subtype") != "success":
            raise ClaudeCodeError(_error_text(data))
        usage = data.get("usage") or {}
        tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        parsed = data.get("structured_output")
        if not isinstance(parsed, dict):
            parsed = _parse_json(str(data.get("result") or ""))
        return parsed, tokens

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDECODE") and k != "CLAUDE_CODE_ENTRYPOINT"}
        env.setdefault("HOME", str(Path.home()))
        return env

    async def _run(self, args: list[str], prompt: str, timeout: float) -> str:
        """One-shot: feed the prompt on stdin, return the whole stdout."""
        async with self._sem:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, cwd=self._work, env=self._env())
            except FileNotFoundError as e:
                raise ClaudeCodeError(f"claude CLI not found at {self._bin}") from e
            try:
                out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout)
            except TimeoutError as e:
                proc.kill()
                raise ClaudeCodeError(f"claude timed out after {timeout:.0f}s") from e
        if proc.returncode != 0 and not out.strip():
            raise ClaudeCodeError(f"claude exited {proc.returncode}: {err.decode(errors='replace')[-300:].strip()}")
        return out.decode(errors="replace")

    async def _stream_lines(self, args: list[str], prompt: str, timeout: float = 120) -> AsyncIterator[str]:
        """Streaming: feed the prompt on stdin, yield stdout line by line."""
        async with self._sem:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, cwd=self._work, env=self._env())
            except FileNotFoundError as e:
                raise ClaudeCodeError(f"claude CLI not found at {self._bin}") from e
            assert proc.stdin and proc.stdout
            proc.stdin.write(prompt.encode())
            await proc.stdin.drain()
            proc.stdin.close()
            try:
                while True:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout)
                    if not line:
                        break
                    yield line.decode(errors="replace")
                await asyncio.wait_for(proc.wait(), 10)
            except TimeoutError as e:
                proc.kill()
                raise ClaudeCodeError(f"claude timed out after {timeout:.0f}s") from e
            finally:
                if proc.returncode is None:
                    proc.kill()


def _transcript(messages: list[dict]) -> str:
    """Replay the OpenAI-style conversation as text; the model continues it with one JSON object."""
    lines: list[str] = []
    for m in messages:
        role = m.get("role")
        if role == "user":
            lines.append(f"User: {m.get('content')}")
        elif role == "assistant":
            if m.get("content"):
                lines.append(f"Assistant: {m['content']}")
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                lines.append(f"Assistant called {fn.get('name')}({fn.get('arguments') or '{}'}) [id {tc.get('id')}]")
        elif role == "tool":
            lines.append(f"Tool result [id {m.get('tool_call_id')}]: {m.get('content')}")
    lines.append("Continue as the assistant: output the next JSON object.")
    return "\n".join(lines)


def _error_text(result: dict) -> str:
    errs = result.get("errors")
    if isinstance(errs, list) and errs:
        return "; ".join(str(e) for e in errs)[:300]
    return str(result.get("result") or result.get("subtype") or "claude error")[:300]
