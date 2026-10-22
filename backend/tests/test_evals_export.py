"""Failed production runs → eval-case stubs (pure part of app.evals.export)."""
import json
from datetime import UTC, datetime

import pytest

from app.evals import export, harness, score


def _run(kind, **kw):
    base = {"id": "0123456789abcdef", "kind": kind, "model": "claude_code / sonnet", "prompt": {"agent": "v1 (x)"},
            "input": "把电钻移到5号箱", "lang": "zh", "tool_calls": [], "confirm": [], "steps": 1, "tokens": 0,
            "latency_ms": 10, "outcome": "message", "error": None, "output": {}, "confirmed": False,
            "undone": False, "feedback": 0, "feedback_note": None, "created_at": "2026-10-22T00:00:00+00:00"}
    return {**base, **kw}


def test_reason_classification() -> None:
    assert export.reason(_run("agent")) is None
    assert export.reason(_run("agent", feedback=-1)) == "thumbs_down"
    assert export.reason(_run("agent", undone=True)) == "undone"
    assert export.reason(_run("ask", outcome="error")) == "error"
    assert export.reason(_run("agent", outcome="step_cap")) == "step_cap"


def test_agent_stub_prefills_what_happened_and_validates_as_a_tools_case() -> None:
    run = _run("agent", feedback=-1, feedback_note="moved the wrong one",
               tool_calls=[{"name": "get_box", "args": {"box": "3"}, "ok": True, "ms": 1, "error": None},
                           {"name": "move_items", "args": {"from_box": "3", "to_box": "5", "item_names": ["钳子"]},
                            "ok": True, "ms": 2, "error": None}],
               output={"text": "已移动。"})
    set_name, case = export.stub(run)
    assert set_name == "tools"
    assert case["expect"]["tools"] == ["move_items"] and case["expect"]["args"]["move_items"]["item_names"] == ["钳子"]
    assert case["_source"]["reason"] == "thumbs_down" and case["_source"]["note"] == "moved the wrong one"
    assert case["_source"]["reply"] == "已移动。"
    assert score.validate_case("tools", case) == []


def test_interpret_stub_goes_to_extraction_or_routing() -> None:
    ingest = _run("interpret", outcome="ok", feedback=-1, input="box 1 has a tent", lang="en",
                  output={"parsed": {"intent": "ingest", "box_label": "1", "items": [{"name": "tent", "qty_text": "×1"}],
                                     "location_text": None, "language": "en"}})
    set_name, case = export.stub(ingest)
    assert set_name == "extraction" and case["expect"]["items"] == [{"name": "tent", "qty_text": "×1"}]
    assert score.validate_case("extraction", case) == []
    query = _run("interpret", feedback=-1, output={"parsed": {"intent": "query"}})
    set_name, case = export.stub(query)
    assert set_name == "routing" and case["expect"] == {"intent": "query"}
    assert score.validate_case("routing", case) == []


def test_unsupported_kinds_are_kept_for_the_record() -> None:
    set_name, case = export.stub(_run("ask", outcome="error", error="boom", output={"text": ""}))
    assert set_name == "ask" and case["_review"].startswith("no golden set")
    assert export.stub(_run("ask")) is None


def test_export_writes_one_file_per_set_and_the_harness_can_load_it(tmp_path) -> None:
    runs = [_run("interpret", feedback=-1, output={"parsed": {"intent": "query"}}),
            _run("agent", id="fedcba9876543210", undone=True, output={"text": "done"})]
    written = export.export(runs, tmp_path, "stamp")
    assert set(written) == {"routing", "tools"}
    cases = harness.load_cases("routing", written["routing"])
    assert cases[0]["id"] == "inbox-01234567" and cases[0]["_source"]["reason"] == "thumbs_down"
    lines = written["tools"].read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["expect"]["tools"] == []


def test_parse_since() -> None:
    now = datetime(2026, 10, 22, tzinfo=UTC)
    assert export.parse_since("all") is None
    assert (now - export.parse_since("7d", now)).days == 7
    assert (now - export.parse_since("24h", now)).total_seconds() == 86400
    with pytest.raises(ValueError):
        export.parse_since("soon")
