import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..db import get_db
from ..models import Box, Item, User
from ..schemas import MeOut, SettingsIn
from ..services import boxes_service

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
            w.writerow([b.label, b.name, b.location_text or "", it.name, it.qty_text, it.note or "", b.updated_at.isoformat()])
    return Response(
        "﻿" + buf.getvalue(),  # BOM,Excel 中文不乱码
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=boxmind-export.csv"},
    )
