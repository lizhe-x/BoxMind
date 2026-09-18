"""Auth endpoints and the bearer-token dependency."""
import jwt

from app import auth as auth_mod
from app.config import settings


def test_health(client) -> None:
    assert client.get("/api/health").json() == {"ok": True}


def test_request_code_dev_mode_returns_code(client) -> None:
    r = client.post("/api/auth/request-code", json={"email": "a@b.co"})
    body = r.json()
    assert r.status_code == 200 and body["dev_mode"] is True and len(body["dev_code"]) == 6


def test_request_code_rate_limited(client) -> None:
    client.post("/api/auth/request-code", json={"email": "a@b.co"})
    assert client.post("/api/auth/request-code", json={"email": "A@B.CO"}).status_code == 429


def test_request_code_rejects_bad_email(client) -> None:
    assert client.post("/api/auth/request-code", json={"email": "not-an-email"}).status_code == 400
    assert client.post("/api/auth/request-code", json={"email": "ab@cd"}).status_code == 400  # no dot in domain
    assert client.post("/api/auth/request-code", json={"email": "a@b"}).status_code == 422  # schema min length


def test_verify_code_creates_then_reuses_user(client) -> None:
    def login():
        code = client.post("/api/auth/request-code", json={"email": "x@y.io"}).json()["dev_code"]
        # cooldown: move the record back so a second request is allowed
        from datetime import timedelta

        from app.db import SessionLocal
        from app.models import EmailCode

        with SessionLocal() as s:
            rec = s.get(EmailCode, "x@y.io")
            rec.last_sent_at -= timedelta(seconds=settings.code_resend_seconds + 1)
            s.commit()
        return client.post("/api/auth/verify-code", json={"email": "x@y.io", "code": code}).json()

    first, second = login(), login()
    assert first["email"] == "x@y.io"
    assert first["user_id"] == second["user_id"]
    assert first["token"] != "" and second["token"] != ""


def test_verify_code_wrong(client) -> None:
    client.post("/api/auth/request-code", json={"email": "x@y.io"})
    r = client.post("/api/auth/verify-code", json={"email": "x@y.io", "code": "999999"})
    assert r.status_code == 400 and r.json()["detail"] == "code_invalid"  # stable code, translated by the UI


def test_device_login_still_works(client) -> None:
    a = client.post("/api/auth/device", json={"device_id": "device-abcdef-1"}).json()
    b = client.post("/api/auth/device", json={"device_id": "device-abcdef-1"}).json()
    assert a["user_id"] == b["user_id"] and a["email"] is None
    assert client.post("/api/auth/device", json={"device_id": "short"}).status_code == 422


def test_protected_routes_reject_bad_tokens(client) -> None:
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    ghost = jwt.encode({"sub": "no-such-user"}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {ghost}"}).status_code == 401
    forged = jwt.encode({"sub": "x"}, "wrong-secret-0123456789abcdef0123456789", algorithm="HS256")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_round_trip() -> None:
    tok = auth_mod.make_token("user-1")
    payload = jwt.decode(tok, settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == "user-1" and "exp" in payload


def test_authenticated_me(client, auth) -> None:
    r = client.get("/api/me", headers=auth)
    assert r.status_code == 200 and r.json()["email"] == "tester@example.com"
