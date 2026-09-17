"""/api/me: profile, settings, JSON/CSV export."""
import csv
import io
import json


def _seed(client, auth):
    b1 = client.post("/api/boxes", json={"label": "1号", "location_text": "车库"}, headers=auth).json()
    client.post("/api/boxes", json={"label": "2号"}, headers=auth)  # empty box
    client.post(f"/api/boxes/{b1['id']}/items", json={"name": "帐篷", "qty_text": "×1", "note": "绿色"}, headers=auth)
    client.post(f"/api/boxes/{b1['id']}/items", json={"name": "头灯", "qty_text": "×2"}, headers=auth)


def test_me_counts(client, auth) -> None:
    _seed(client, auth)
    me = client.get("/api/me", headers=auth).json()
    assert (me["box_count"], me["item_count"], me["used"]) == (2, 2, 0)
    assert me["lang"] == "zh" and me["gps_enabled"] is True and me["email"] == "tester@example.com"


def test_update_settings(client, auth) -> None:
    me = client.patch("/api/me", json={"lang": "en", "gps_enabled": False}, headers=auth).json()
    assert me["lang"] == "en" and me["gps_enabled"] is False
    me = client.patch("/api/me", json={}, headers=auth).json()  # no-op keeps values
    assert me["lang"] == "en" and me["gps_enabled"] is False
    me = client.patch("/api/me", json={"gps_enabled": True}, headers=auth).json()
    assert me["gps_enabled"] is True


def test_export_json(client, auth) -> None:
    _seed(client, auth)
    r = client.get("/api/me/export.json", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = json.loads(r.content)
    by_label = {b["label"]: b for b in data}
    assert set(by_label) == {"1号", "2号"}
    assert by_label["1号"]["location_text"] == "车库"
    assert {(i["name"], i["qty"], i["note"]) for i in by_label["1号"]["items"]} == {("帐篷", "×1", "绿色"), ("头灯", "×2", None)}
    assert by_label["2号"]["items"] == []


def test_export_csv(client, auth) -> None:
    _seed(client, auth)
    r = client.get("/api/me/export.csv", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")  # BOM so Excel opens Chinese correctly
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows[0] == ["box_label", "box_name", "location", "item_name", "qty", "note", "updated_at"]
    body = rows[1:]
    assert len(body) == 3  # 2 items + 1 row for the empty box
    assert ["2号", "2号箱", "", "", "", ""] in [r[:6] for r in body]
    assert ["1号", "1号箱", "车库", "帐篷", "×1", "绿色"] in [r[:6] for r in body]
