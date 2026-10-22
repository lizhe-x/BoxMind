"""Traces: what the model layer records about each request."""
import asyncio

import pytest
from conftest import ScriptedLLM, assistant_msg, tool_call
from sqlalchemy.orm import Session

from app.models import User
from app.services import agent, trace
from app.services.llm import LLM


def test_prompt_id_is_stable_and_short() -> None:
    assert trace.prompt_id("abc") == trace.prompt_id("abc")
    assert trace.prompt_id("abc") != trace.prompt_id("abd")
    assert len(trace.prompt_id("x")) == 10


def test_collect_gathers_traces_started_inside_only() -> None:
    trace.start("agent")  # outside: not collected
    with trace.collect() as traces:
        t = trace.start("interpret", model="m")
        assert trace.current() is t
        t.tool("get_box", {"box": "1"}, {"ok": False, "error": "nope"}, 3)
        t.finish("ok", parsed={"intent": "query"})
    assert [x.kind for x in traces] == ["interpret"]
    d = traces[0].to_dict()
    assert d["tool_calls"] == [{"name": "get_box", "args": {"box": "1"}, "ok": False, "ms": 3, "error": "nope"}]
    assert d["outcome"] == "ok" and d["output"] == {"parsed": {"intent": "query"}} and "_t0" not in d


async def test_collect_sees_traces_from_tasks_created_inside() -> None:
    with trace.collect() as traces:
        await asyncio.gather(*(asyncio.create_task(_traced(k)) for k in ("a", "b")))
    assert sorted(t.kind for t in traces) == ["a", "b"]


async def _traced(kind: str) -> None:
    trace.start(kind)


async def test_interpret_wrapper_traces_and_fills_defaults(monkeypatch) -> None:
    class Fake(LLM):
        async def _interpret(self, text, known_labels, lang):
            return {"intent": "ingest", "_tokens": 42}

    with trace.collect() as traces:
        parsed = await Fake().interpret("box 1 has a tent", ["1"], "zh")
    assert parsed["items"] == [] and parsed["box_label"] is None and parsed["language"] == "zh"
    t = traces[0]
    assert t.kind == "interpret" and t.tokens == 42 and t.outcome == "ok" and t.input == "box 1 has a tent"
    assert t.output["parsed"] == {"intent": "ingest", "box_label": None, "items": [], "location_text": None,
                                  "language": "zh"}
    assert "_tokens" not in t.output["parsed"]
    assert t.prompts["interpret"] and t.model


async def test_interpret_wrapper_records_provider_errors() -> None:
    class Broken(LLM):
        async def _interpret(self, text, known_labels, lang):
            raise RuntimeError("gateway down")

    with trace.collect() as traces, pytest.raises(RuntimeError):
        await Broken().interpret("x", [], None)
    assert traces[0].outcome == "error" and traces[0].error == "gateway down"


async def test_agent_run_traces_steps_tools_and_outcome(db: Session, user: User, llm: ScriptedLLM) -> None:
    llm.script(
        assistant_msg(None, [tool_call("add_items", {"box": "1", "items": [{"name": "tent"}]})]),
        assistant_msg("Added the tent to box 1."),
    )
    with trace.collect() as traces:
        out = await agent.run(db, user, [], "put a tent in box 1", None)
    assert out["type"] == "message"
    t = traces[0]
    assert t.kind == "agent" and t.model == "scripted" and t.steps == 2 and t.outcome == "message"
    assert [c.name for c in t.tool_calls] == ["add_items"] and t.tool_calls[0].ok
    assert t.output["text"] == "Added the tent to box 1." and t.latency_ms >= 0


async def test_agent_run_traces_confirm_gate_and_failed_tool(db: Session, user: User, llm: ScriptedLLM) -> None:
    llm.script(
        assistant_msg(None, [tool_call("get_box", {"box": "77"}, "c1"), tool_call("delete_box", {"box": "77"}, "c2")]),
    )
    with trace.collect() as traces:
        out = await agent.run(db, user, [], "delete box 77", None)
    assert out["type"] == "confirm"
    t = traces[0]
    assert t.outcome == "confirm" and t.confirm == ["delete_box"]
    assert [(c.name, c.ok) for c in t.tool_calls] == [("get_box", False)]  # box 77 does not exist
    assert t.tool_calls[0].error
    assert t.output["actions"] == [{"tool": "delete_box", "args": {"box": "77"}}]
