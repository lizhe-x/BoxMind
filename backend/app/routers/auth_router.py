from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import make_token
from ..db import get_db
from ..models import User
from ..schemas import DeviceAuthIn, RequestCodeIn, TokenOut, VerifyCodeIn
from ..services import email_code

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/device", response_model=TokenOut)
def device_auth(body: DeviceAuthIn, db: Session = Depends(get_db)):
    """匿名设备登录(保留,主流程已改为邮箱验证码)。"""
    user = db.scalar(select(User).where(User.device_id == body.device_id))
    if not user:
        user = User(device_id=body.device_id)
        db.add(user)
        db.commit()
    return TokenOut(token=make_token(user.id), user_id=user.id, email=user.email)


def _norm_email(raw: str) -> str:
    email = raw.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "invalid_email")
    return email


@router.post("/request-code")
def request_code(body: RequestCodeIn, db: Session = Depends(get_db)):
    """请求邮箱验证码。开发模式(未配 SMTP)直接返回验证码。"""
    email = _norm_email(body.email)
    try:
        code = email_code.issue(db, email)
    except ValueError:
        raise HTTPException(429, "请求过于频繁,请稍后再试") from None
    if email_code.dev_mode():
        return {"sent": True, "dev_mode": True, "dev_code": code}
    try:
        email_code.send_email(email, code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"邮件发送失败: {e}") from e
    return {"sent": True, "dev_mode": False}


@router.post("/verify-code", response_model=TokenOut)
def verify_code(body: VerifyCodeIn, db: Session = Depends(get_db)):
    """校验验证码 → 按邮箱建/找用户 → 签发 token。"""
    email = _norm_email(body.email)
    try:
        email_code.verify(db, email, body.code)
    except ValueError as e:
        msg = {"code_invalid": "验证码错误", "code_expired": "验证码已过期", "too_many": "尝试次数过多,请重新获取"}
        raise HTTPException(400, msg.get(str(e), "验证失败")) from e
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(device_id=f"email:{email}", email=email)
        db.add(user)
        db.commit()
    return TokenOut(token=make_token(user.id), user_id=user.id, email=user.email)
