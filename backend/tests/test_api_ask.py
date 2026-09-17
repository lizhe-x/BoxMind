"""/api/ask: streaming RAG answer as server-sent events."""
import json

from tests.conftest import ScriptedLLM


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        ev = data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                ev = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        out.append((ev, data))
    return out


def _seed(client, auth):
    b6 = client.post("/api/boxes", json={"label": "6号", "location_text": "玄关柜顶"}, headers=auth).json()
    b7 = client.post("/api/boxes", json={"label": "7号"}, headers=auth).json()
    client.post(f"/api/boxes/{b6['id']}/items", json={"name": "登山包", "qty_text": "×1"}, headers=auth)
    client.post(f"/api/boxes/{b7['id']}/items", json={"name": "帐篷", "qty_text": "×1"}, headers=auth)
    return b6, b7


def test_ask_streams_deltas_and_box_cards(client, auth, llm: ScriptedLLM) -> None:
    b6, _ = _seed(client, auth)
    llm.answer_chunks = ["登山包在 6号", "箱,玄关柜顶。"]
    with client.stream("POST", "/api/ask", json={"question": "登山包"}, headers=auth) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        events = _events(r.read().decode())

    assert events[:2] == [("delta", {"t": "登山包在 6号"}), ("delta", {"t": "箱,玄关柜顶。"})]
    ev, done = events[-1]
    assert ev == "done" and done["credits_left"] == -1
    assert [b["id"] for b in done["boxes"]] == [b6["id"]]  # only the box mentioned in the answer
    assert done["boxes"][0]["location_text"] == "玄关柜顶"

    question, context, hint = llm.answer_calls[0]
    assert question == "登山包"
    ctx = json.loads(context)
    assert {b["箱子编号"] for b in ctx} == {"6号", "7号"}
    assert ctx[0]["物品"] and "更新时间" in ctx[0]
    assert hint.startswith("登山包(在6号, 相似度1.00)")  # exact-name vector hit ranks first

    assert client.get("/api/me", headers=auth).json()["used"] == 1  # usage logged after a successful stream


def test_ask_with_no_items_skips_vector_search(client, auth, llm: ScriptedLLM) -> None:
    client.post("/api/boxes", json={"label": "1号"}, headers=auth)
    with client.stream("POST", "/api/ask", json={"question": "有什么"}, headers=auth) as r:
        events = _events(r.read().decode())
    assert events[-1][0] == "done"
    assert llm.answer_calls[0][2] == "无"


def test_ask_upstream_failure_emits_error_event(client, auth, llm: ScriptedLLM) -> None:
    _seed(client, auth)
    llm.answer_error = RuntimeError("gateway down")
    with client.stream("POST", "/api/ask", json={"question": "x"}, headers=auth) as r:
        events = _events(r.read().decode())
    assert events == [("error", {"message": "gateway down"})]
    assert client.get("/api/me", headers=auth).json()["used"] == 0  # failed answers are not counted


def test_ask_validates_input(client, auth) -> None:
    assert client.post("/api/ask", json={"question": ""}, headers=auth).status_code == 422
    assert client.post("/api/ask", json={"question": "x"}).status_code == 401
