import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import get_current_user
from ..db import get_db
from ..models import Box, Item, User
from ..schemas import AskIn
from ..services import boxes_service, embeddings
from ..services.llm import llm

router = APIRouter(prefix="/api", tags=["ask"])

MAX_CONTEXT_ITEMS = 400  # MVP 数据量小,整库上下文;超限时仅保留向量命中


def _fmt_time(dt: datetime) -> str:
    local = dt.astimezone()
    today = datetime.now(timezone.utc).astimezone().date()
    d = local.date()
    if d == today:
        return "今天 " + local.strftime("%H:%M")
    if d.year == today.year:
        return f"{d.month}月{d.day}日"
    return f"{d.year}年{d.month}月{d.day}日"


def _build_context(boxes: list[Box]) -> str:
    data = []
    for b in boxes:
        data.append({
            "箱子编号": b.label,
            "箱子名": b.name,
            "位置描述": b.location_text or "未记录",
            "GPS": "已记录" if b.gps_lat is not None else "未记录",
            "绑定的码": b.barcode or None,
            "更新时间": _fmt_time(b.updated_at),
            "物品": [{"名称": it.name, "数量": it.qty_text} for it in b.items],
        })
    return json.dumps(data, ensure_ascii=False)


@router.post("/ask")
async def ask(body: AskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    boxes = db.scalars(
        select(Box).options(selectinload(Box.items))
        .where(Box.user_id == user.id).order_by(Box.updated_at.desc())
    ).all()

    # 向量检索:跨语言语义命中提示
    hint = "无"
    total_items = sum(len(b.items) for b in boxes)
    if total_items:
        qvec = (await embeddings.embed([body.question]))[0]
        rows = db.execute(
            select(Item.name, Box.label, Item.embedding.cosine_distance(qvec).label("d"))
            .join(Box, Item.box_id == Box.id)
            .where(Box.user_id == user.id, Item.embedding.is_not(None))
            .order_by("d").limit(8)
        ).all()
        hint = "; ".join(f"{r.name}(在{r.label}, 相似度{1 - r.d:.2f})" for r in rows) or "无"

    if total_items > MAX_CONTEXT_ITEMS:
        hit_labels = {r.label for r in rows}
        boxes = [b for b in boxes if b.label in hit_labels]

    context = _build_context(boxes)
    user_id = user.id

    async def gen():
        full = ""
        try:
            async for delta in llm.answer_stream(body.question, context, hint):
                full += delta
                yield f"event: delta\ndata: {json.dumps({'t': delta}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001 — 把错误下发给前端展示
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
            return
        # 回答中提到的箱子 → 可点卡片
        refs = []
        for b in boxes:
            if b.label in full or b.name in full:
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
        yield f"event: done\ndata: {json.dumps({'boxes': refs, 'credits_left': -1}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _fresh_session():
    from ..db import SessionLocal

    return SessionLocal()
