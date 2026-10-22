import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..db import get_db
from ..models import Box, EmailCode, Item, Media, UndoSnapshot, UsageLog, User
from ..schemas import MeOut, SettingsIn
from ..services import boxes_service, media

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    box_count = db.scalar(select(func.count(Box.id)).where(Box.user_id == user.id)) or 0
    item_count = db.scalar(
        select(func.count(Item.id)).join(Box).where(Box.user_id == user.id)
    ) or 0
    return MeOut(
        user_id=user.id,
        email=user.email,
        lang=user.lang,
        gps_enabled=bool(user.gps_enabled),
        credit_balance=user.credit_balance,
        used=boxes_service.usage_count(db, user.id),
        box_count=box_count,
        item_count=item_count,
    )


@router.patch("", response_model=MeOut)
def update_settings(body: SettingsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.lang is not None:
        user.lang = body.lang
    if body.gps_enabled is not None:
        user.gps_enabled = 1 if body.gps_enabled else 0
    db.commit()
    return me(user, db)


@router.delete("", status_code=204)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除账号及其全部数据(App Store 5.1.1(v) 要求应用内可删号)。

    顺序按外键依赖:媒体 → 物品 → 箱子 → 快照/用量/验证码 → 用户。文件在事务提交后再删,
    避免提交失败却已丢文件。
    """
    filenames = list(db.scalars(select(Media.filename).where(Media.user_id == user.id)))
    box_ids = select(Box.id).where(Box.user_id == user.id)
    db.execute(delete(Media).where(Media.user_id == user.id))
    db.execute(delete(Item).where(Item.box_id.in_(box_ids)))
    db.execute(delete(Box).where(Box.user_id == user.id))
    db.execute(delete(UndoSnapshot).where(UndoSnapshot.user_id == user.id))
    db.execute(delete(UsageLog).where(UsageLog.user_id == user.id))
    if user.email:
        db.execute(delete(EmailCode).where(EmailCode.email == user.email))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    for name in filenames:
        media.delete(name)
    return Response(status_code=204)


def _all_boxes(db: Session, user: User) -> list[Box]:
    return db.scalars(
        select(Box).options(selectinload(Box.items)).where(Box.user_id == user.id)
    ).all()


@router.get("/export.json")
def export_json(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = [
        {
            "label": b.label, "name": b.name, "barcode": b.barcode,
            "location_text": b.location_text, "gps_lat": b.gps_lat, "gps_lng": b.gps_lng,
            "updated_at": b.updated_at.isoformat(),
            "items": [{"name": it.name, "qty": it.qty_text, "note": it.note} for it in b.items],
        }
        for b in _all_boxes(db, user)
    ]
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=boxmind-export.json"},
    )


@router.get("/export.csv")
def export_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["box_label", "box_name", "location", "item_name", "qty", "note", "updated_at"])
    for b in _all_boxes(db, user):
        if not b.items:
            w.writerow([b.label, b.name, b.location_text or "", "", "", "", b.updated_at.isoformat()])
        for it in b.items:
            w.writerow(
                [b.label, b.name, b.location_text or "", it.name, it.qty_text, it.note or "", b.updated_at.isoformat()]
            )
    return Response(
        "﻿" + buf.getvalue(),  # BOM,Excel 中文不乱码
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=boxmind-export.csv"},
    )
