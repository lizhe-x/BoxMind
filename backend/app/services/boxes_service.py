from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..i18n import tr
from ..models import Box, Item, UsageLog, User
from ..normalize import KRAFT_PALETTE, extract_number, normalize_label
from . import embeddings


def find_box_by_label(db: Session, user_id: str, raw_label: str) -> Box | None:
    norm, _, _ = normalize_label(raw_label)
    return db.scalar(select(Box).where(Box.user_id == user_id, Box.norm_label == norm))


def next_num_label(db: Session, user: User) -> str:
    """下一个空闲的数字编号,按用户界面语言显示("4" / "4号")。"""
    labels = db.scalars(select(Box.label).where(Box.user_id == user.id)).all()
    nums = [n for n in (extract_number(lb) for lb in labels) if n]
    return tr(user.lang, "label_num", n=(max(nums) if nums else 0) + 1)


def create_box(
    db: Session,
    user: User,
    raw_label: str,
    name: str | None = None,
    location_text: str | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    source: str = "text",
) -> Box:
    norm, label, default_name = normalize_label(raw_label, user.lang)
    count = db.scalar(select(func.count(Box.id)).where(Box.user_id == user.id)) or 0
    color_a, color_b = KRAFT_PALETTE[count % len(KRAFT_PALETTE)]
    box = Box(
        user_id=user.id,
        label=label,
        norm_label=norm,
        name=name or default_name,
        location_text=location_text,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        color_a=color_a,
        color_b=color_b,
        source=source,
    )
    db.add(box)
    db.flush()
    return box


async def add_items(db: Session, box: Box, items: list[dict]) -> None:
    """新增物品;同名物品覆盖数量而不是重复一行。"""
    if not items:
        return
    vectors = await embeddings.embed([it["name"] for it in items])
    existing = {it.name: it for it in box.items}
    for it, vec in zip(items, vectors, strict=True):
        if it["name"] in existing:
            old = existing[it["name"]]
            old.qty_text = it.get("qty_text") or old.qty_text
            old.embedding = vec
        else:
            # 通过关系 append,保证 box.items 内存集合与数据库一致
            # (expire_on_commit=False 时,直接 db.add 不会刷新已加载的集合)
            box.items.append(
                Item(
                    name=it["name"],
                    qty_text=it.get("qty_text") or "×1",
                    note=it.get("note"),
                    embedding=vec,
                )
            )


def log_usage(db: Session, user: User, action: str, tokens: int = 0) -> None:
    """记录一次用量(用于统计)。无限制使用:不扣额度、不阻断。"""
    db.add(UsageLog(user_id=user.id, action_type=action, tokens_used=tokens))


def usage_count(db: Session, user_id: str) -> int:
    return db.scalar(select(func.count(UsageLog.id)).where(UsageLog.user_id == user_id)) or 0
