"""ClaudeCodeLLM: the `claude -p` provider, with the CLI stubbed out (argv + stdin recorded, stdout scripted)."""
import json

import pytest

from app.services import agent_tools
from app.services.llm_claude import ClaudeCodeError, ClaudeCodeLLM, _transcript


class FakeCLI:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, stdout: str = "", lines: list[str] | None = None):
        self.runs: list[tuple[list[str], str]] = []
        self.stdout = stdout
        self.lines = lines or []

        async def run(_self, args, prompt, timeout):
            self.runs.append((args, prompt))
            return self.stdout

        async def stream(_self, args, prompt, timeout=120):
            self.runs.append((args, prompt))
            for line in self.lines:
                yield line

        monkeypatch.setattr(ClaudeCodeLLM, "_run", run)
        monkeypatch.setattr(ClaudeCodeLLM, "_stream_lines", stream)

    def flag(self, name: str) -> str:
        args = self.runs[-1][0]
        return args[args.index(name) + 1]


def _result(structured=None, **extra) -> str:
    d = {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(structured or {}),
         "usage": {"input_tokens": 10, "output_tokens": 5}}
    if structured is not None:
        d["structured_output"] = structured
    d.update(extra)
    return json.dumps(d)


@pytest.fixture
def provider(tmp_path, monkeypatch) -> ClaudeCodeLLM:
    monkeypatch.setattr("app.services.llm_claude.settings.media_dir", str(tmp_path))
    return ClaudeCodeLLM()


async def test_interpret_uses_structured_output_and_fills_defaults(provider, monkeypatch) -> None:
    cli = FakeCLI(monkeypatch, stdout=_result({"intent": "ingest", "box_label": "3",
                                                "items": [{"name": "lamp", "qty_text": "×2"}]}))
    parsed = await provider.interpret("box 3 has two lamps", ["1", "2"], "en")
    assert parsed["intent"] == "ingest" and parsed["box_label"] == "3"
    assert parsed["location_text"] is None and parsed["language"] == "en"
    assert parsed["_tokens"] == 15
    args, prompt = cli.runs[0]
    assert args[1:3] == ["-p", "--no-session-persistence"] and "--strict-mcp-config" in args
    assert cli.flag("--tools") == "" and cli.flag("--output-format") == "json"
    assert "existing box labels: 1, 2" in prompt and prompt.endswith("User said: box 3 has two lamps")
    assert "parsing engine of BoxMind" in cli.flag("--system-prompt")
    assert json.loads(cli.flag("--json-schema"))["properties"]["intent"]["enum"] == ["ingest", "query", "operation"]


async def test_interpret_falls_back_to_parsing_the_text_result(provider, monkeypatch) -> None:
    FakeCLI(monkeypatch, stdout=json.dumps({"type": "result", "subtype": "success", "is_error": False,
                                            "result": 'Sure: {"intent": "query", "box_label": null}'}))
    parsed = await provider.interpret("where is the tent", [], "zh")
    assert parsed["intent"] == "query" and parsed["items"] == [] and parsed["language"] == "zh"


async def test_cli_errors_surface_as_claude_code_error(provider, monkeypatch) -> None:
    FakeCLI(monkeypatch, stdout=json.dumps({"type": "result", "subtype": "error_during_execution",
                                            "is_error": True, "errors": ["Not logged in"]}))
    with pytest.raises(ClaudeCodeError, match="Not logged in"):
        await provider.interpret("x", [], "en")
    FakeCLI(monkeypatch, stdout="garbage")
    with pytest.raises(ClaudeCodeError, match="unreadable"):
        await provider.interpret("x", [], "en")


async def test_chat_with_tools_converts_to_openai_tool_calls(provider, monkeypatch) -> None:
    cli = FakeCLI(monkeypatch, stdout=_result({"content": None, "tool_calls": [
        {"name": "move_items", "arguments": {"from_box": "2", "to_box": "5", "item_names": ["drill"]}},
        {"name": "not_a_tool", "arguments": {}},
    ]}))
    msg = await provider.chat_with_tools([
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "move the drill to box 5"},
    ], agent_tools.TOOLS)
    assert msg["role"] == "assistant" and msg["content"] is None
    assert len(msg["tool_calls"]) == 1  # unknown tool names are dropped
    tc = msg["tool_calls"][0]
    assert tc["type"] == "function" and tc["function"]["name"] == "move_items"
    assert json.loads(tc["function"]["arguments"]) == {"from_box": "2", "to_box": "5", "item_names": ["drill"]}
    system = cli.flag("--system-prompt")
    assert system.startswith("SYS") and '"name": "move_items"' in system
    schema = json.loads(cli.flag("--json-schema"))
    assert "delete_box" in schema["properties"]["tool_calls"]["items"]["properties"]["name"]["enum"]
    assert cli.runs[0][1].startswith("User: move the drill to box 5")


async def test_chat_with_tools_plain_reply_has_no_tool_calls_key(provider, monkeypatch) -> None:
    FakeCLI(monkeypatch, stdout=_result({"content": "Which box?", "tool_calls": []}))
    msg = await provider.chat_with_tools([{"role": "user", "content": "hi"}], agent_tools.TOOLS)
    assert msg == {"role": "assistant", "content": "Which box?"}


def test_transcript_replays_tool_calls_and_results() -> None:
    text = _transcript([
        {"role": "system", "content": "ignored here"},
        {"role": "user", "content": "move the drill"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "search_items", "arguments": '{"query": "drill"}'}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": '{"ok": true, "hits": []}'},
    ])
    assert text.splitlines() == [
        "User: move the drill",
        'Assistant called search_items({"query": "drill"}) [id call_1]',
        'Tool result [id call_1]: {"ok": true, "hits": []}',
        "Continue as the assistant: output the next JSON object.",
    ]


async def test_answer_stream_yields_text_deltas(provider, monkeypatch) -> None:
    def delta(t):
        return json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
                                                             "delta": {"type": "text_delta", "text": t}}})
    cli = FakeCLI(monkeypatch, lines=[
        json.dumps({"type": "system", "subtype": "init"}), delta("In "), "not json\n", delta("box 1."),
        json.dumps({"type": "assistant"}), _result(result="In box 1."),
    ])
    out = [d async for d in provider.answer_stream("where", "[]", "none")]
    assert out == ["In ", "box 1."]
    assert cli.flag("--output-format") == "stream-json" and "--include-partial-messages" in cli.runs[0][0]
    assert cli.runs[0][1].endswith("Question: where")


async def test_answer_stream_without_partials_yields_the_final_text_once(provider, monkeypatch) -> None:
    FakeCLI(monkeypatch, lines=[_result(result="Box 2.")])
    assert [d async for d in provider.answer_stream("q", "[]", "")] == ["Box 2."]


async def test_answer_stream_raises_on_error_result(provider, monkeypatch) -> None:
    FakeCLI(monkeypatch, lines=[json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True})])
    with pytest.raises(ClaudeCodeError, match="error_max_turns"):
        async for _ in provider.answer_stream("q", "[]", ""):
            pass


async def test_recognize_image_writes_the_photo_and_allows_only_read(provider, monkeypatch, tmp_path) -> None:
    seen: dict = {}

    async def run(_self, args, prompt, timeout):
        seen["args"], seen["prompt"] = args, prompt
        seen["files"] = [p.name for p in (tmp_path / ".claude-work").iterdir()]
        return _result({"box_label": "2", "items": [{"name": "tent", "qty_text": "×1", "confidence": "high"}]})

    monkeypatch.setattr(ClaudeCodeLLM, "_run", run)
    import base64
    parsed = await provider.recognize_image(base64.b64encode(b"\xff\xd8jpeg").decode(), "image/jpeg", "en")
    assert parsed["box_label"] == "2" and parsed["items"][0]["confidence"] == "high"
    assert len(seen["files"]) == 1 and seen["files"][0].startswith("photo-") and seen["files"][0].endswith(".jpg")
    assert seen["files"][0] in seen["prompt"]
    args = seen["args"]
    assert args[args.index("--tools") + 1] == "Read" and args[args.index("--allowedTools") + 1] == "Read"
    assert list((tmp_path / ".claude-work").iterdir()) == []  # cleaned up afterwards
