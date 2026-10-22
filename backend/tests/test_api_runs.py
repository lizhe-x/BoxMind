"""Production traces: every model-backed endpoint records a run; confirm/undo and thumbs feed back into it."""
import json

from conftest import ScriptedLLM, assistant_msg, tool_call


def _runs(client, auth, **params):
    r = client.get("/api/runs", params=params, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()["runs"]


def _run(client, auth, run_id):
    return next(r for r in _runs(client, auth, limit=200) if r["id"] == run_id)


def test_agent_message_records_a_run_and_returns_its_id(client, auth, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg("Which box?"))
    r = client.post("/api/agent", json={"message": "move the lamp"}, headers=auth)
    assert r.status_code == 200 and r.json()["run_id"]
    run = _run(client, auth, r.json()["run_id"])
    assert run["kind"] == "agent" and run["outcome"] == "message" and run["model"] == "scripted"
    assert run["input"] == "move the lamp" and run["prompt"]["agent"].startswith("v")
    assert run["tool_calls"] == [] and run["feedback"] == 0 and not run["undone"]


def test_confirm_then_execute_then_undo_marks_the_run(client, auth, llm: ScriptedLLM) -> None:
    client.post("/api/ingest", json={"box_label": "9", "items": [{"name": "lamp", "qty_text": "×1"}]}, headers=auth)
    llm.script(assistant_msg(None, [tool_call("delete_box", {"box": "9"})]))
    r = client.post("/api/agent", json={"message": "delete box 9"}, headers=auth)
    assert r.json()["type"] == "confirm"
    run_id = r.json()["run_id"]
    assert _run(client, auth, run_id)["outcome"] == "confirm" and not _run(client, auth, run_id)["confirmed"]

    r = client.post("/api/agent/execute", json={"tool": "delete_box", "args": {"box": "9"}}, headers=auth)
    assert r.status_code == 200, r.text
    assert _run(client, auth, run_id)["confirmed"] and not _run(client, auth, run_id)["undone"]

    llm.script(assistant_msg(None, [tool_call("undo_last", {})]), assistant_msg("Restored box 9."))
    r = client.post("/api/agent", json={"message": "undo"}, headers=auth)
    assert r.status_code == 200 and r.json()["type"] == "message"
    assert _run(client, auth, run_id)["undone"], "undo is implicit negative feedback on the confirmed run"
    assert [x["id"] for x in _runs(client, auth, failed=True)] == [run_id]


def test_thumbs_feedback(client, auth, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg("ok"))
    run_id = client.post("/api/agent", json={"message": "hi"}, headers=auth).json()["run_id"]
    r = client.post(f"/api/runs/{run_id}/feedback", json={"value": -1, "note": "wrong box"}, headers=auth)
    assert r.status_code == 200 and r.json()["feedback"] == -1
    run = _run(client, auth, run_id)
    assert run["feedback"] == -1 and run["feedback_note"] == "wrong box"
    assert [x["id"] for x in _runs(client, auth, failed=True)] == [run_id]
    assert client.post(f"/api/runs/{run_id}/feedback", json={"value": 2}, headers=auth).status_code == 422
    assert client.post("/api/runs/nope/feedback", json={"value": 1}, headers=auth).status_code == 404
    client.post(f"/api/runs/{run_id}/feedback", json={"value": 0}, headers=auth)
    assert _runs(client, auth, failed=True) == []


def test_feedback_is_scoped_to_the_owner(client, auth, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg("ok"))
    run_id = client.post("/api/agent", json={"message": "hi"}, headers=auth).json()["run_id"]
    r = client.post("/api/auth/request-code", json={"email": "other@example.com"})
    r = client.post("/api/auth/verify-code", json={"email": "other@example.com", "code": r.json()["dev_code"]})
    other = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.post(f"/api/runs/{run_id}/feedback", json={"value": 1}, headers=other).status_code == 404
    assert _runs(client, other) == []


def test_interpret_ask_and_recognize_record_runs(client, auth, llm: ScriptedLLM) -> None:
    llm.interpret_reply = {"intent": "ingest", "box_label": "1", "items": [{"name": "tent", "qty_text": "×1"}],
                           "location_text": None, "language": "en"}
    r = client.post("/api/interpret", json={"text": "box 1 has a tent"}, headers=auth)
    assert r.status_code == 200 and r.json()["run_id"]
    run = _run(client, auth, r.json()["run_id"])
    assert run["kind"] == "interpret" and run["output"]["parsed"]["intent"] == "ingest"

    llm.answer_chunks = ["In ", "box 1."]
    with client.stream("POST", "/api/ask", json={"question": "where is the tent"}, headers=auth) as r:
        events = [line for line in r.iter_lines() if line.startswith("data:")]
    done = json.loads(events[-1][5:])
    assert done["run_id"]
    run = _run(client, auth, done["run_id"])
    assert run["kind"] == "ask" and run["outcome"] == "ok" and run["output"]["text"] == "In box 1."

    llm.vision_reply = {"box_label": "2", "items": [{"name": "lamp", "qty_text": "×1", "confidence": "high"}]}
    r = client.post("/api/recognize", files={"file": ("a.jpg", b"\xff\xd8\xff", "image/jpeg")}, headers=auth)
    assert r.status_code == 200 and r.json()["run_id"]
    assert _run(client, auth, r.json()["run_id"])["kind"] == "recognize"


def test_ask_error_is_a_failed_run(client, auth, llm: ScriptedLLM) -> None:
    llm.answer_error = RuntimeError("gateway down")
    with client.stream("POST", "/api/ask", json={"question": "x"}, headers=auth) as r:
        events = [line for line in r.iter_lines() if line.startswith("event:")]
    assert "event: error" in events
    failed = _runs(client, auth, failed=True)
    assert len(failed) == 1 and failed[0]["outcome"] == "error" and "gateway down" in failed[0]["error"]
