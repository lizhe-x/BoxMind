from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..db import get_db
from ..i18n import tr
from ..models import Box, User
from ..schemas import IngestIn, IngestOut, InterpretIn, InterpretOut
from ..services import boxes_service
from ..services.llm import llm

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/interpret", response_model=InterpretOut)
async def interpret(body: InterpretIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """一段话 → 意图 + 结构化抽取。不入库、不计量。"""
    labels = db.scalars(select(Box.label).where(Box.user_id == user.id)).all()
    parsed = await llm.interpret(body.text, list(labels), user.lang)

    box = None
    box_label = parsed.get("box_label")
    if body.target_box_id:  # 「录入到此箱」模式锁定目标箱
        box = db.scalar(
            select(Box).options(selectinload(Box.items), selectinload(Box.media))
            .where(Box.id == body.target_box_id, Box.user_id == user.id)
        )
        if box:
            box_label = box.label
    elif box_label:
        box = boxes_service.find_box_by_label(db, user.id, box_label)

    some = tr(user.lang, "qty_some")
    return InterpretOut(
        intent=parsed["intent"],
        box_label=box_label,
        box=box,
        items=[
            {"name": it.get("name", ""), "qty_text": it.get("qty_text") or some}
            for it in parsed.get("items", [])
            if it.get("name")
        ],
        location_text=parsed.get("location_text"),
        language=parsed.get("language", user.lang),
        next_label=boxes_service.next_num_label(db, user),
    )


@router.post("/ingest", response_model=IngestOut)
async def ingest(body: IngestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """确认入库:找到/创建箱子,写入物品(含 embedding)。无限制使用。"""
    if not body.items:
        raise HTTPException(400, "no items")
    created = False
    box: Box | None = None
    if body.box_id:
        box = db.scalar(
            select(Box).options(selectinload(Box.items), selectinload(Box.media))
            .where(Box.id == body.box_id, Box.user_id == user.id)
        )
        if not box:
            raise HTTPException(404, "box not found")
    elif body.box_label:
        box = boxes_service.find_box_by_label(db, user.id, body.box_label)
        if not box:
            box = boxes_service.create_box(
                db, user, body.box_label,
                location_text=body.location_text,
                gps_lat=body.gps_lat, gps_lng=body.gps_lng,
                source=body.source,
            )
            created = True
    else:
        raise HTTPException(400, "box_id or box_label required")

    if not created:
        if body.location_text:
            box.location_text = body.location_text
        if body.gps_lat is not None:
            box.gps_lat, box.gps_lng = body.gps_lat, body.gps_lng

    boxes_service.log_usage(db, user, "ingest")
    await boxes_service.add_items(db, box, [it.model_dump() for it in body.items])
    db.commit()
    box = db.scalar(select(Box).options(selectinload(Box.items), selectinload(Box.media)).where(Box.id == box.id))
    return IngestOut(box=box, created=created, credits_left=-1)
