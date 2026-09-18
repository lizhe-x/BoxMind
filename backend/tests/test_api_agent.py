"""/api/agent and /api/agent/execute end to end (HTTP → agent loop → DB), with a scripted model."""
import httpx

from tests.conftest import ScriptedLLM, assistant_msg, tool_call


def _create(client, auth, label, items=()):
    box = client.post("/api/boxes", json={"label": label}, headers=auth).json()
    for name, qty in items:
        client.post(f"/api/boxes/{box['id']}/items", json={"name": name, "qty_text": qty}, headers=auth)
    return box


def test_agent_requires_auth(client) -> None:
    assert client.post("/api/agent", json={"message": "hi"}).status_code == 401


def test_agent_executes_and_replies(client, auth, llm: ScriptedLLM) -> None:
    box = _create(client, auth, "7")
    llm.script(
        assistant_msg(None, [tool_call("set_box_location", {"box": "7", "location_text": "balcony"})]),
        assistant_msg("Box 7 is now on the balcony."),
    )
    r = client.post("/api/agent", json={"message": "box 7 is on the balcony", "history": [], "gps": None}, headers=auth)
    assert r.status_code == 200 and r.json() == {"type": "message", "text": "Box 7 is now on the balcony."}
    assert client.get(f"/api/boxes/{box['id']}", headers=auth).json()["location_text"] == "balcony"


def test_agent_forwards_history_and_gps(client, auth, llm: ScriptedLLM) -> None:
    _create(client, auth, "7")
    llm.script(assistant_msg(None, [tool_call("set_box_gps", {"box": "7"})]), assistant_msg("ok"))
    body = {
        "message": "remember this spot for box 7",
        "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        "gps": {"lat": 30.0, "lng": 120.0},
    }
    assert client.post("/api/agent", json=body, headers=auth).status_code == 200
    roles = [m["role"] for m in llm.calls[0]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    box = client.get("/api/boxes/by-label/7", headers=auth).json()
    assert (box["gps_lat"], box["gps_lng"]) == (30.0, 120.0)


def test_agent_confirm_then_execute_then_undo(client, auth, llm: ScriptedLLM) -> None:
    box = _create(client, auth, "5", [("headlamp", "×2")])
    llm.script(assistant_msg(None, [tool_call("delete_box", {"box": "5"})]))
    r = client.post("/api/agent", json={"message": "delete box 5"}, headers=auth).json()
    assert r["type"] == "confirm"
    action = r["actions"][0]
    assert action["summary"] == "Delete box “5” (with 1 item types)"
    assert client.get(f"/api/boxes/{box['id']}", headers=auth).status_code == 200  # still there

    r = client.post("/api/agent/execute", json={"tool": action["tool"], "args": action["args"]}, headers=auth)
    assert r.status_code == 200 and r.json() == {"ok": True, "summary": "Deleted box “Box 5”"}
    assert client.get(f"/api/boxes/{box['id']}", headers=auth).status_code == 404

    llm.script(assistant_msg(None, [tool_call("undo_last", {})]), assistant_msg("Undone."))
    r = client.post("/api/agent", json={"message": "undo"}, headers=auth).json()
    assert r == {"type": "message", "text": "Undone."}
    restored = client.get(f"/api/boxes/{box['id']}", headers=auth).json()
    assert [i["name"] for i in restored["items"]] == ["headlamp"]


def test_confirm_summary_in_users_language(client, auth, llm: ScriptedLLM) -> None:
    client.patch("/api/me", json={"lang": "zh"}, headers=auth)
    _create(client, auth, "5")
    llm.script(assistant_msg(None, [tool_call("delete_box", {"box": "5"})]))
    r = client.post("/api/agent", json={"message": "删掉5号"}, headers=auth).json()
    assert r["actions"][0]["summary"] == "删除整个箱子「5」"


def test_execute_refuses_non_destructive_tools(client, auth) -> None:
    r = client.post("/api/agent/execute", json={"tool": "create_box", "args": {"name": "x"}}, headers=auth)
    assert r.status_code == 400
    r = client.post("/api/agent/execute", json={"tool": "made_up", "args": {}}, headers=auth)
    assert r.status_code == 400


def test_execute_reports_missing_box_gracefully(client, auth) -> None:
    r = client.post("/api/agent/execute", json={"tool": "delete_box", "args": {"box": "42"}}, headers=auth)
    assert r.status_code == 200 and r.json() == {"ok": False, "error": "box not found"}


def test_gateway_errors_become_502(client, auth, llm: ScriptedLLM, monkeypatch) -> None:
    async def boom(messages, tools):
        req = httpx.Request("POST", "http://gateway.invalid/v1/chat/completions")
        raise httpx.HTTPStatusError("upstream", request=req, response=httpx.Response(503, text="No available channel", request=req))

    monkeypatch.setattr(llm, "chat_with_tools", boom)
    r = client.post("/api/agent", json={"message": "x"}, headers=auth)
    assert r.status_code == 502 and "No available channel" in r.json()["detail"]
