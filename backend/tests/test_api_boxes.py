"""REST surface for boxes, items, media and barcode resolution."""
import io

from app.config import settings


def _create(client, auth, label, **extra):
    r = client.post("/api/boxes", json={"label": label, **extra}, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_create_list_get(client, auth) -> None:
    b = _create(client, auth, "Box 2", location_text="车库")
    assert (b["label"], b["name"], b["location_text"], b["source"]) == ("2号", "2号箱", "车库", "text")
    assert b["items"] == [] and b["photos"] == [] and b["audios"] == []
    assert [x["id"] for x in client.get("/api/boxes", headers=auth).json()] == [b["id"]]
    assert client.get(f"/api/boxes/{b['id']}", headers=auth).json()["id"] == b["id"]
    assert client.get("/api/boxes/by-label/二号", headers=auth).json()["id"] == b["id"]
    assert client.get("/api/boxes/by-label/9号", headers=auth).status_code == 404
    assert client.get("/api/boxes/next-label", headers=auth).json() == {"next_label": "3号"}


def test_duplicate_label_conflict(client, auth) -> None:
    _create(client, auth, "1号")
    assert client.post("/api/boxes", json={"label": "Box 1"}, headers=auth).status_code == 409


def test_boxes_are_isolated_per_user(client, auth) -> None:
    b = _create(client, auth, "1号")
    other = client.post("/api/auth/device", json={"device_id": "other-device-9999"}).json()
    other_auth = {"Authorization": f"Bearer {other['token']}"}
    assert client.get("/api/boxes", headers=other_auth).json() == []
    assert client.get(f"/api/boxes/{b['id']}", headers=other_auth).status_code == 404
    assert client.delete(f"/api/boxes/{b['id']}", headers=other_auth).status_code == 404


def test_patch_label_renormalises_and_checks_conflicts(client, auth) -> None:
    a = _create(client, auth, "1号")
    _create(client, auth, "2号")
    r = client.patch(f"/api/boxes/{a['id']}", json={"label": "box 5"}, headers=auth)
    assert (r.json()["label"], r.json()["name"]) == ("5号", "5号箱")
    r = client.patch(f"/api/boxes/{a['id']}", json={"label": "7号", "name": "露营"}, headers=auth)
    assert (r.json()["label"], r.json()["name"]) == ("7号", "露营")
    assert client.patch(f"/api/boxes/{a['id']}", json={"label": "2号"}, headers=auth).status_code == 409
    r = client.patch(f"/api/boxes/{a['id']}", json={"barcode": "QR-1", "gps_lat": 1.0, "gps_lng": 2.0}, headers=auth)
    assert (r.json()["barcode"], r.json()["gps_lat"]) == ("QR-1", 1.0)


def test_items_crud_and_reembed_on_rename(client, auth) -> None:
    b = _create(client, auth, "1号")
    r = client.post(f"/api/boxes/{b['id']}/items", json={"name": "帐篷", "qty_text": "×1"}, headers=auth)
    assert r.status_code == 200 and r.json()["name"] == "帐篷"
    item = r.json()
    r = client.patch(f"/api/boxes/{b['id']}/items/{item['id']}", json={"name": "双人帐篷", "qty_text": "×2"}, headers=auth)
    assert (r.json()["name"], r.json()["qty_text"]) == ("双人帐篷", "×2")

    from app.db import SessionLocal
    from app.models import Item
    from tests.conftest import fake_vector

    with SessionLocal() as s:
        vec = list(s.get(Item, item["id"]).embedding)
    assert abs(sum(a * b for a, b in zip(vec, fake_vector("双人帐篷"), strict=True)) - 1.0) < 1e-4

    assert client.delete(f"/api/boxes/{b['id']}/items/{item['id']}", headers=auth).json() == {"ok": True}
    assert client.delete(f"/api/boxes/{b['id']}/items/{item['id']}", headers=auth).status_code == 404
    assert client.get(f"/api/boxes/{b['id']}", headers=auth).json()["items"] == []


def test_item_endpoints_check_box_ownership_of_item(client, auth) -> None:
    a = _create(client, auth, "1号")
    b = _create(client, auth, "2号")
    item = client.post(f"/api/boxes/{a['id']}/items", json={"name": "x"}, headers=auth).json()
    assert client.patch(f"/api/boxes/{b['id']}/items/{item['id']}", json={"qty_text": "×9"}, headers=auth).status_code == 404
    assert client.delete(f"/api/boxes/{b['id']}/items/{item['id']}", headers=auth).status_code == 404


def test_delete_box(client, auth) -> None:
    b = _create(client, auth, "1号")
    assert client.delete(f"/api/boxes/{b['id']}", headers=auth).json() == {"ok": True}
    assert client.get(f"/api/boxes/{b['id']}", headers=auth).status_code == 404


def test_photo_and_audio_upload_and_cover(client, auth) -> None:
    b = _create(client, auth, "1号")
    r = client.post(
        f"/api/boxes/{b['id']}/photo", files={"file": ("p.png", io.BytesIO(b"\x89PNG"), "image/png")}, headers=auth
    )
    url1 = r.json()["url"]
    assert url1.startswith("/media/") and url1.endswith(".png")
    r = client.post(
        f"/api/boxes/{b['id']}/photo?set_cover=false",
        files={"file": ("p.jpg", io.BytesIO(b"\xff\xd8"), "image/jpeg")}, headers=auth,
    )
    url2 = r.json()["url"]
    r = client.post(
        f"/api/boxes/{b['id']}/audio", files={"file": ("a.webm", io.BytesIO(b"webm"), "audio/webm")}, headers=auth
    )
    audio = r.json()["url"]

    box = client.get(f"/api/boxes/{b['id']}", headers=auth).json()
    assert box["photo_url"] == url1 and box["photos"] == [url1, url2] and box["audios"] == [audio]
    assert client.get(url1).status_code == 200  # served statically
    assert client.get(url1).content == b"\x89PNG"

    assert client.post(f"/api/boxes/{b['id']}/cover", json={"url": url2}, headers=auth).json()["photo_url"] == url2
    assert client.post(f"/api/boxes/{b['id']}/cover", json={"url": "/media/nope.jpg"}, headers=auth).status_code == 400
    assert settings.media_dir  # sanity: media dir is the temp dir from conftest


def test_empty_upload_rejected(client, auth) -> None:
    b = _create(client, auth, "1号")
    r = client.post(f"/api/boxes/{b['id']}/photo", files={"file": ("p.png", io.BytesIO(b""), "image/png")}, headers=auth)
    assert r.status_code == 400


def test_resolve_by_code_label_and_create(client, auth) -> None:
    b = _create(client, auth, "1号")
    # unknown code, no fallback → 404
    assert client.post("/api/boxes/resolve", json={"code": "BX-1"}, headers=auth).status_code == 404
    # unknown code + handwritten label → binds the code to that box
    r = client.post("/api/boxes/resolve", json={"code": "BX-1", "label": "一号"}, headers=auth).json()
    assert r["created"] is False and r["box"]["id"] == b["id"] and r["box"]["barcode"] == "BX-1"
    # known code alone now resolves
    assert client.post("/api/boxes/resolve", json={"code": "BX-1"}, headers=auth).json()["box"]["id"] == b["id"]
    # a second code does not overwrite the first
    r = client.post("/api/boxes/resolve", json={"code": "BX-9", "label": "1号"}, headers=auth).json()
    assert r["box"]["barcode"] == "BX-1"
    # create on miss
    r = client.post("/api/boxes/resolve", json={"code": "BX-2", "label": "2号", "create": True}, headers=auth).json()
    assert r["created"] is True and (r["box"]["label"], r["box"]["barcode"], r["box"]["source"]) == ("2号", "BX-2", "scan")
    r = client.post("/api/boxes/resolve", json={"code": "QR-XYZ", "create": True}, headers=auth).json()
    assert r["created"] is True and r["box"]["label"] == "QR-X"  # code used as label when no label given
    assert client.post("/api/boxes/resolve", json={"create": True}, headers=auth).status_code == 404
