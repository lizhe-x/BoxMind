"""/api/ask: streaming RAG answer as server-sent events."""
import json
from datetime import datetime

from app.i18n import fmt_time
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
    b6 = client.post("/api/boxes", json={"label": "6", "location_text": "hallway cabinet, top"}, headers=auth).json()
    b7 = client.post("/api/boxes", json={"label": "7"}, headers=auth).json()
    client.post(f"/api/boxes/{b6['id']}/items", json={"name": "backpack", "qty_text": "×1"}, headers=auth)
    client.post(f"/api/boxes/{b7['id']}/items", json={"name": "tent", "qty_text": "×1"}, headers=auth)
    return b6, b7


def test_ask_streams_deltas_and_box_cards(client, auth, llm: ScriptedLLM) -> None:
    b6, _ = _seed(client, auth)
    llm.answer_chunks = ["The backpack is in box 6", ", hallway cabinet, top."]
    with client.stream("POST", "/api/ask", json={"question": "backpack"}, headers=auth) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        events = _events(r.read().decode())

    assert events[:2] == [("delta", {"t": "The backpack is in box 6"}), ("delta", {"t": ", hallway cabinet, top."})]
    ev, done = events[-1]
    assert ev == "done" and done["credits_left"] == -1
    assert [b["id"] for b in done["boxes"]] == [b6["id"]]  # only the box mentioned in the answer
    assert done["boxes"][0]["location_text"] == "hallway cabinet, top"

    question, context, hint = llm.answer_calls[0]
    assert question == "backpack"
    ctx = json.loads(context)
    assert {b["label"] for b in ctx} == {"6", "7"}
    assert {b["name"] for b in ctx} == {"Box 6", "Box 7"}
    assert ctx[0]["items"] and ctx[0]["updated"].startswith("today ")
    assert hint.startswith("backpack (in 6, similarity 1.00)")  # exact-name vector hit ranks first

    assert client.get("/api/me", headers=auth).json()["used"] == 1  # usage logged after a successful stream


def test_box_cards_match_labels_as_whole_numbers(client, auth, llm: ScriptedLLM) -> None:
    b1 = client.post("/api/boxes", json={"label": "1"}, headers=auth).json()
    b12 = client.post("/api/boxes", json={"label": "12"}, headers=auth).json()
    client.post(f"/api/boxes/{b12['id']}/items", json={"name": "x"}, headers=auth)
    llm.answer_chunks = ["It is in box 12."]
    with client.stream("POST", "/api/ask", json={"question": "x"}, headers=auth) as r:
        done = _events(r.read().decode())[-1][1]
    assert [b["id"] for b in done["boxes"]] == [b12["id"]]  # "12" must not also light up box 1
    assert b1["id"] not in [b["id"] for b in done["boxes"]]


def test_context_language_follows_user(client, auth, llm: ScriptedLLM) -> None:
    client.patch("/api/me", json={"lang": "zh"}, headers=auth)
    _seed(client, auth)
    with client.stream("POST", "/api/ask", json={"question": "backpack"}, headers=auth) as r:
        r.read()
    _, context, hint = llm.answer_calls[0]
    ctx = json.loads(context)
    assert ctx[0]["updated"].startswith("今天 ") and ctx[0]["gps"] == "未记录"
    assert hint.startswith("backpack(在6号, 相似度1.00)")  # boxes were created after the switch → zh labels


def test_fmt_time_buckets() -> None:
    # naive datetimes are interpreted in the machine's local zone, so the local dates are deterministic
    now = datetime(2026, 9, 17, 12, 0).astimezone()
    assert fmt_time(now, "en", now) == "today 12:00"
    assert fmt_time(datetime(2026, 3, 4, 12, 0).astimezone(), "en", now) == "Mar 4"
    assert fmt_time(datetime(2025, 3, 4, 12, 0).astimezone(), "en", now) == "Mar 4, 2025"
    assert fmt_time(now, "zh", now) == "今天 12:00"
    assert fmt_time(datetime(2026, 3, 4, 12, 0).astimezone(), "zh", now) == "3月4日"
    assert fmt_time(datetime(2025, 3, 4, 12, 0).astimezone(), "zh", now) == "2025年3月4日"


def test_ask_with_no_items_skips_vector_search(client, auth, llm: ScriptedLLM) -> None:
    client.post("/api/boxes", json={"label": "1"}, headers=auth)
    with client.stream("POST", "/api/ask", json={"question": "anything"}, headers=auth) as r:
        events = _events(r.read().decode())
    assert events[-1][0] == "done"
    assert llm.answer_calls[0][2] == "none"


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
