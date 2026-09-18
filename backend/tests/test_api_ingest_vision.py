"""/api/interpret (intent router), /api/ingest (confirmed write), /api/recognize (photo intake)."""
import io

import httpx

from tests.conftest import ScriptedLLM


def test_interpret_ingest_intent_matches_existing_box(client, auth, llm: ScriptedLLM) -> None:
    b1 = client.post("/api/boxes", json={"label": "1"}, headers=auth).json()
    llm.interpret_reply = {
        "intent": "ingest", "box_label": "box 1",
        "items": [{"name": "down jacket", "qty_text": "×3"}, {"name": "", "qty_text": "×1"}, {"name": "scarf"}],
        "location_text": "attic", "language": "en",
    }
    r = client.post("/api/interpret", json={"text": "box 1 has three down jackets and a scarf"}, headers=auth)
    body = r.json()
    assert r.status_code == 200
    assert body["intent"] == "ingest" and body["box"]["id"] == b1["id"]
    assert body["items"] == [
        {"name": "down jacket", "qty_text": "×3", "note": None},
        {"name": "scarf", "qty_text": "some", "note": None},  # unknown quantity → language-aware placeholder
    ]
    assert body["location_text"] == "attic" and body["next_label"] == "2"
    assert llm.interpret_calls[0] == ("box 1 has three down jackets and a scarf", ["1"], "en")  # labels + language
    assert client.get("/api/boxes", headers=auth).json()[0]["items"] == []  # interpret never writes


def test_interpret_uses_users_language(client, auth, llm: ScriptedLLM) -> None:
    client.patch("/api/me", json={"lang": "zh"}, headers=auth)
    llm.interpret_reply = {"intent": "ingest", "box_label": "1", "items": [{"name": "围巾"}], "location_text": None, "language": "zh"}
    body = client.post("/api/interpret", json={"text": "1号放了围巾"}, headers=auth).json()
    assert body["items"][0]["qty_text"] == "若干" and body["next_label"] == "1号"
    assert llm.interpret_calls[0][2] == "zh"


def test_interpret_target_box_overrides_label(client, auth, llm: ScriptedLLM) -> None:
    b1 = client.post("/api/boxes", json={"label": "1"}, headers=auth).json()
    llm.interpret_reply = {"intent": "ingest", "box_label": "9", "items": [{"name": "x"}], "location_text": None, "language": "en"}
    body = client.post("/api/interpret", json={"text": "...", "target_box_id": b1["id"]}, headers=auth).json()
    assert body["box_label"] == "1" and body["box"]["id"] == b1["id"]


def test_interpret_query_and_operation_pass_through(client, auth, llm: ScriptedLLM) -> None:
    llm.interpret_reply = {"intent": "operation", "box_label": None, "items": [], "location_text": None, "language": "en"}
    body = client.post("/api/interpret", json={"text": "merge box 6 into 7"}, headers=auth).json()
    assert body["intent"] == "operation" and body["box"] is None and body["language"] == "en"


def test_ingest_creates_box_and_reports_created(client, auth) -> None:
    payload = {
        "box_label": "Box 5", "items": [{"name": "trekking poles", "qty_text": "×2"}, {"name": "headlamp"}],
        "location_text": "garage", "gps_lat": 31.0, "gps_lng": 121.0, "source": "voice",
    }
    r = client.post("/api/ingest", json=payload, headers=auth)
    body = r.json()
    assert r.status_code == 200 and body["created"] is True and body["credits_left"] == -1
    box = body["box"]
    assert (box["label"], box["name"], box["source"], box["location_text"], box["gps_lat"]) == ("5", "Box 5", "voice", "garage", 31.0)
    assert [(i["name"], i["qty_text"]) for i in box["items"]] == [("trekking poles", "×2"), ("headlamp", "×1")]
    assert client.get("/api/me", headers=auth).json()["used"] == 1


def test_ingest_into_existing_box_updates_location_and_upserts(client, auth) -> None:
    first = client.post("/api/ingest", json={"box_label": "5", "items": [{"name": "headlamp", "qty_text": "×1"}]}, headers=auth).json()
    second = client.post(
        "/api/ingest",
        json={"box_id": first["box"]["id"], "items": [{"name": "headlamp", "qty_text": "×3"}], "location_text": "attic"},
        headers=auth,
    ).json()
    assert second["created"] is False and second["box"]["id"] == first["box"]["id"]
    assert second["box"]["location_text"] == "attic"
    assert [(i["name"], i["qty_text"]) for i in second["box"]["items"]] == [("headlamp", "×3")]
    # by label variant also lands in the same box
    third = client.post("/api/ingest", json={"box_label": "五号箱", "items": [{"name": "tent"}]}, headers=auth).json()
    assert third["created"] is False and len(third["box"]["items"]) == 2


def test_ingest_validation(client, auth) -> None:
    assert client.post("/api/ingest", json={"box_label": "1", "items": []}, headers=auth).status_code == 400
    assert client.post("/api/ingest", json={"items": [{"name": "x"}]}, headers=auth).status_code == 400
    assert client.post("/api/ingest", json={"box_id": "nope", "items": [{"name": "x"}]}, headers=auth).status_code == 404


def _png() -> dict:
    return {"file": ("shot.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")}


def test_recognize_returns_items_and_box_status(client, auth, llm: ScriptedLLM) -> None:
    client.post("/api/boxes", json={"label": "2"}, headers=auth)
    llm.vision_reply = {
        "box_label": "2",
        "items": [
            {"name": "backpack", "qty_text": "×1", "confidence": "high"},
            {"name": "tent", "confidence": "low"},
            {"name": "", "qty_text": "×1"},
            {"name": "gloves"},
        ],
    }
    r = client.post("/api/recognize", files=_png(), headers=auth)
    body = r.json()
    assert r.status_code == 200
    assert body["box_label"] == "2" and body["box_exists"] is True and body["next_label"] == "3"
    assert body["items"] == [
        {"name": "backpack", "qty_text": "×1", "confidence": "high"},
        {"name": "tent", "qty_text": "some", "confidence": "low"},
        {"name": "gloves", "qty_text": "some", "confidence": "medium"},
    ]
    b64, mime, lang = llm.vision_calls[0]
    assert mime == "image/png" and lang == "en" and b64.startswith("iVBORw0KG")  # PNG magic, base64-encoded


def test_recognize_unknown_label_and_empty(client, auth, llm: ScriptedLLM) -> None:
    llm.vision_reply = {"box_label": "9", "items": []}
    body = client.post("/api/recognize", files=_png(), headers=auth).json()
    assert body["box_exists"] is False and body["items"] == [] and body["next_label"] == "1"
    r = client.post("/api/recognize", files={"file": ("e.png", io.BytesIO(b""), "image/png")}, headers=auth)
    assert r.status_code == 400


def test_recognize_upstream_errors_become_502(client, auth, llm: ScriptedLLM, monkeypatch) -> None:
    async def http_fail(image_b64, mime="image/jpeg", lang=None):
        req = httpx.Request("POST", "http://gateway.invalid/v1/chat/completions")
        raise httpx.HTTPStatusError("x", request=req, response=httpx.Response(429, text="rate limited", request=req))

    monkeypatch.setattr(llm, "recognize_image", http_fail)
    r = client.post("/api/recognize", files=_png(), headers=auth)
    assert r.status_code == 502 and r.json()["detail"].startswith("vision_upstream_error")

    async def other_fail(image_b64, mime="image/jpeg", lang=None):
        raise ValueError("bad image")

    monkeypatch.setattr(llm, "recognize_image", other_fail)
    r = client.post("/api/recognize", files=_png(), headers=auth)
    assert r.status_code == 502 and r.json()["detail"] == "vision_error: bad image"
