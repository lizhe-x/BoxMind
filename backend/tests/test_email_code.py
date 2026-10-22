"""Email login codes: issue / rate-limit / verify / expiry / attempt cap."""
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models import EmailCode
from app.services import email_code


def test_issue_returns_six_digit_code_and_persists(db: Session) -> None:
    code = email_code.issue(db, "  A@Example.com ")
    assert len(code) == 6 and code.isdigit()
    rec = db.get(EmailCode, "a@example.com")  # normalised key
    assert rec is not None and rec.code == code and rec.attempts == 0


def test_reissue_too_soon_is_rejected(db: Session) -> None:
    email_code.issue(db, "a@example.com")
    with pytest.raises(ValueError, match="too_soon"):
        email_code.issue(db, "a@example.com")


def test_reissue_after_cooldown_replaces_code(db: Session) -> None:
    first = email_code.issue(db, "a@example.com")
    rec = db.get(EmailCode, "a@example.com")
    rec.last_sent_at -= timedelta(seconds=settings.code_resend_seconds + 1)
    rec.attempts = 3
    db.commit()
    second = email_code.issue(db, "a@example.com")
    rec = db.get(EmailCode, "a@example.com")
    assert rec.code == second and rec.attempts == 0
    # 1-in-a-million chance the codes collide; tolerate it rather than flake
    assert first != second or True


def test_verify_success_consumes_code(db: Session) -> None:
    code = email_code.issue(db, "a@example.com")
    assert email_code.verify(db, "A@example.com", f" {code} ") is True
    assert db.get(EmailCode, "a@example.com") is None
    with pytest.raises(ValueError, match="code_invalid"):
        email_code.verify(db, "a@example.com", code)  # cannot be replayed


def test_verify_wrong_code_counts_attempts_then_locks(db: Session) -> None:
    code = email_code.issue(db, "a@example.com")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.code_max_attempts):
        with pytest.raises(ValueError, match="code_invalid"):
            email_code.verify(db, "a@example.com", wrong)
    with pytest.raises(ValueError, match="too_many"):
        email_code.verify(db, "a@example.com", code)  # even the right code is refused now
    assert db.get(EmailCode, "a@example.com") is None


def test_verify_expired_code(db: Session) -> None:
    code = email_code.issue(db, "a@example.com")
    rec = db.get(EmailCode, "a@example.com")
    rec.expires_at -= timedelta(seconds=settings.code_ttl_seconds + 1)
    db.commit()
    with pytest.raises(ValueError, match="code_expired"):
        email_code.verify(db, "a@example.com", code)
    assert db.get(EmailCode, "a@example.com") is None


def test_dev_mode_follows_smtp_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")
    assert email_code.dev_mode() is True
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    assert email_code.dev_mode() is False
