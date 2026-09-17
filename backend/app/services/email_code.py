"""邮箱验证码:生成/限频/校验,以及发送(SMTP 配了就真发,否则开发模式)。"""
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from ..config import settings
from ..models import EmailCode


def _now() -> datetime:
    return datetime.now(timezone.utc)


def dev_mode() -> bool:
    """未配置 SMTP 即开发模式(验证码经接口返回,不真发邮件)。"""
    return not settings.smtp_host


def issue(db: Session, email: str) -> str:
    """生成并保存验证码;若距上次发送过近则抛 ValueError('too_soon')。返回验证码。"""
    email = email.strip().lower()
    rec = db.get(EmailCode, email)
    now = _now()
    if rec and (now - rec.last_sent_at).total_seconds() < settings.code_resend_seconds:
        raise ValueError("too_soon")
    code = f"{secrets.randbelow(1000000):06d}"
    expires = now + timedelta(seconds=settings.code_ttl_seconds)
    if rec:
        rec.code, rec.expires_at, rec.attempts, rec.last_sent_at = code, expires, 0, now
    else:
        db.add(EmailCode(email=email, code=code, expires_at=expires, attempts=0, last_sent_at=now))
    db.commit()
    return code


def send_email(email: str, code: str) -> None:
    """真实发送(仅在配置了 SMTP 时调用)。"""
    msg = EmailMessage()
    msg["Subject"] = "BoxMind 登录验证码"
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = email
    msg.set_content(f"你的 BoxMind 登录验证码是:{code}\n\n{settings.code_ttl_seconds // 60} 分钟内有效。若非本人操作请忽略。")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
        s.starttls()
        s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


def verify(db: Session, email: str, code: str) -> bool:
    """校验验证码;失败抛 ValueError(code_invalid/code_expired/too_many)。成功删除并返回 True。"""
    email = email.strip().lower()
    rec = db.get(EmailCode, email)
    if not rec:
        raise ValueError("code_invalid")
    if _now() > rec.expires_at:
        db.delete(rec)
        db.commit()
        raise ValueError("code_expired")
    if rec.attempts >= settings.code_max_attempts:
        db.delete(rec)
        db.commit()
        raise ValueError("too_many")
    if code.strip() != rec.code:
        rec.attempts += 1
        db.commit()
        raise ValueError("code_invalid")
    db.delete(rec)
    db.commit()
    return True
