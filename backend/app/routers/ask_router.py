import json
import re

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..db import get_db
from ..i18n import fmt_time, tr
from ..models import Box, User
from ..schemas import AskIn
from ..services import boxes_service, runs, search, trace
from ..services.llm import llm
from ..services.prompts import ANSWER

router = APIRouter(prefix="/api", tags=["ask"])

MAX_CONTEXT_ITEMS = 400  # MVP 数据量小,整库上下文;超限时仅保留向量命中


def _build_context(boxes: list[Box], lang: str) -> str:
    data = []
    for b in boxes:
        data.append({
            "label": b.label,
            "name": b.name,
            "location": b.location_text or tr(lang, "not_recorded"),
            "gps": tr(lang, "recorded") if b.gps_lat is not None else tr(lang, "not_recorded"),
            "code": b.barcode or None,
            "updated": fmt_time(b.updated_at, lang),
            "items": [{"name": it.name, "qty": it.qty_text} for it in b.items],
        })
    return json.dumps(data, ensure_ascii=False)


@router.post("/ask")
async def ask(body: AskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    boxes = db.scalars(
        select(Box).options(selectinload(Box.items))
        .where(Box.user_id == user.id).order_by(Box.updated_at.desc())
    ).all()

    # 检索(向量 + 三元组融合):跨语言语义命中提示
    hint = tr(user.lang, "hint_none")
    total_items = sum(len(b.items) for b in boxes)
    hits = []
    if total_items:
        hits = await search.search_items(db, user, body.question, limit=8)
        hint = "; ".join(tr(user.lang, "hint_item", name=h["item"], label=h["box_label"],
                            sim=h["similarity"] if h["similarity"] is not None else 1.0) for h in hits) or hint

    if total_items > MAX_CONTEXT_ITEMS:
        hit_labels = {h["box_label"] for h in hits}
        boxes = [b for b in boxes if b.label in hit_labels]

    context = _build_context(boxes, user.lang)
    user_id = user.id
    t = trace.start("ask", model=llm.model_name, prompts={"answer": ANSWER.ref}, input=body.question, lang=user.lang)

    async def gen():
        full = ""
        try:
            async for delta in llm.answer_stream(body.question, context, hint):
                full += delta
                yield f"event: delta\ndata: {json.dumps({'t': delta}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001 — 把错误下发给前端展示
            t.error = str(e)
            t.finish("error", text=full)
            with _fresh_session() as s:
                runs.record(s, s.get(User, user_id), t)
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
            return
        t.finish("ok", text=full[:2000])
        # 回答中提到的箱子 → 可点卡片
        refs = []
        for b in boxes:
            if _mentions(full, b):
                refs.append({
                    "id": b.id, "label": b.label, "name": b.name,
                    "location_text": b.location_text, "color_a": b.color_a, "color_b": b.color_b,
                    "gps_lat": b.gps_lat, "gps_lng": b.gps_lng,
                })
        # 计量(流式结束后再记,生成失败不计;无限制使用,不扣额度)
        with _fresh_session() as s:
            u = s.get(User, user_id)
            boxes_service.log_usage(s, u, "query")
            s.commit()
            run_id = runs.record(s, u, t).id
        yield (f"event: done\ndata: "
               f"{json.dumps({'boxes': refs, 'credits_left': -1, 'run_id': run_id}, ensure_ascii=False)}\n\n")

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _mentions(answer: str, box: Box) -> bool:
    """箱子被回答提到:名字或编号出现,且不是更长数字的一部分("box 12" 不能命中 "Box 1" / "1")。"""
    low = answer.lower()
    return any(
        re.search(rf"(?<!\d)(?<!\d\.){re.escape(t)}(?!\d)(?!\.\d)", low) is not None
        for t in (box.name.lower(), box.label.lower())
    )


def _fresh_session():
    from ..db import SessionLocal

    return SessionLocal()
