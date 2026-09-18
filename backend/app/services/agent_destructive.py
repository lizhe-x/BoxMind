"""破坏性操作:删物品/删箱/清空/合并。先 summarize 给用户确认,确认后 execute 落库。
执行前打快照,支持"撤销上一步"。所有用户可见文字按用户界面语言输出。"""
import json
import re

from sqlalchemy.orm import Session

from ..i18n import join, tr
from ..models import Box, Media, UndoSnapshot, User
from . import boxes_service
from .agent_tools import resolve_box


def _merge_qty(a: str, b: str, lang: str | None = None) -> str:
    """合并同名物品数量: ×2 + ×3 → ×5;×2 双 + ×1 双 → ×3 双;无法解析则保留其一。"""
    na, nb = re.search(r"\d+", a or ""), re.search(r"\d+", b or "")
    if na and nb:
        total = int(na.group()) + int(nb.group())
        # the unit is whatever follows the "×N" / "xN" marker ("×2 box" → "box"; do not eat the x in "box")
        unit_of = lambda s: re.sub(r"^\s*[×x]?\s*\d+\s*", "", s or "", count=1).strip()  # noqa: E731
        unit = unit_of(a) or unit_of(b)
        return f"×{total}{(' ' + unit) if unit else ''}"
    return a or b or tr(lang, "qty_some")


# ── 确认摘要(人话) ──────────────────────────
def summarize(db: Session, user: User, tool: str, args: dict) -> str:
    lang = user.lang
    if tool == "delete_item":
        return tr(lang, "sum_delete_item", box=args.get("box"), item=args.get("item_name"))
    if tool == "delete_box":
        box = resolve_box(db, user, args.get("box", ""))
        n = len(box.items) if box else 0
        return tr(lang, "sum_delete_box", box=args.get("box")) + (tr(lang, "sum_delete_box_n", n=n) if n else "")
    if tool == "empty_box":
        box = resolve_box(db, user, args.get("box", ""))
        n = len(box.items) if box else 0
        return tr(lang, "sum_empty_box", box=args.get("box"), n=n)
    if tool == "merge_boxes":
        return tr(lang, "sum_merge", srcs=join(lang, args.get("source_boxes", [])), target=args.get("target_box"))
    return tr(lang, "op_generic", tool=tool)


# ── 快照(撤销用) ────────────────────────────
def _op_label(lang: str | None, tool: str) -> str:
    key = f"op_{tool}"
    try:
        return tr(lang, key)
    except KeyError:
        return tr(lang, "op_generic", tool=tool)


def _affected_refs(tool: str, args: dict) -> list[str]:
    if tool == "merge_boxes":
        return [*args.get("source_boxes", []), args.get("target_box", "")]
    return [args.get("box", "")]


def _dump_box(box: Box) -> dict:
    return {
        "id": box.id, "label": box.label, "norm_label": box.norm_label, "name": box.name,
        "barcode": box.barcode, "photo_url": box.photo_url, "location_text": box.location_text,
        "gps_lat": box.gps_lat, "gps_lng": box.gps_lng, "color_a": box.color_a, "color_b": box.color_b,
        "source": box.source,
        "items": [{"name": it.name, "qty_text": it.qty_text, "note": it.note} for it in box.items],
        "media_ids": [m.id for m in box.media],
    }


def _snapshot_before(db: Session, user: User, tool: str, args: dict) -> None:
    seen: set[str] = set()
    boxes = []
    for ref in _affected_refs(tool, args):
        b = resolve_box(db, user, ref) if ref else None
        if b and b.id not in seen:
            seen.add(b.id)
            boxes.append(_dump_box(b))
    payload = json.dumps({"boxes": boxes}, ensure_ascii=False)
    label = _op_label(user.lang, tool)
    snap = db.get(UndoSnapshot, user.id)
    if snap:
        snap.label, snap.payload = label, payload
    else:
        db.add(UndoSnapshot(user_id=user.id, label=label, payload=payload))
    db.commit()


async def restore_last(db: Session, user: User) -> dict:
    snap = db.get(UndoSnapshot, user.id)
    if not snap:
        return {"ok": False, "error": tr(user.lang, "undo_none")}
    data = json.loads(snap.payload)
    # 1) 先把相关 media 摘出(置空 box_id),避免删箱时被级联删
    for bd in data["boxes"]:
        for mid in bd["media_ids"]:
            m = db.get(Media, mid)
            if m:
                m.box_id = None
    db.flush()
    # 2) 删旧箱、按原样重建箱 + 物品
    for bd in data["boxes"]:
        existing = db.get(Box, bd["id"])
        if existing:
            db.delete(existing)
            db.flush()
        box = Box(
            id=bd["id"], user_id=user.id, label=bd["label"], norm_label=bd["norm_label"],
            name=bd["name"], barcode=bd["barcode"], photo_url=bd["photo_url"],
            location_text=bd["location_text"], gps_lat=bd["gps_lat"], gps_lng=bd["gps_lng"],
            color_a=bd["color_a"], color_b=bd["color_b"], source=bd["source"],
        )
        db.add(box)
        db.flush()
        if bd["items"]:
            await boxes_service.add_items(db, box, bd["items"])  # 重新生成 embedding
    # 3) media 归位
    for bd in data["boxes"]:
        for mid in bd["media_ids"]:
            m = db.get(Media, mid)
            if m:
                m.box_id = bd["id"]
    label = snap.label
    db.delete(snap)
    db.commit()
    return {"ok": True, "summary": tr(user.lang, "undo_done", label=label)}


# ── 执行 ────────────────────────────────────
def execute(db: Session, user: User, tool: str, args: dict) -> dict:
    _snapshot_before(db, user, tool, args)  # 执行前打快照
    if tool == "delete_item":
        return _delete_item(db, user, args)
    if tool == "delete_box":
        return _delete_box(db, user, args)
    if tool == "empty_box":
        return _empty_box(db, user, args)
    if tool == "merge_boxes":
        return _merge_boxes(db, user, args)
    return {"ok": False, "error": tr(user.lang, "err_unknown_op", tool=tool)}


def _delete_item(db, user, args):
    box = resolve_box(db, user, args.get("box", ""))
    if not box:
        return {"ok": False, "error": tr(user.lang, "err_box_not_found")}
    target = (args.get("item_name") or "").strip()
    item = next((it for it in box.items if it.name == target), None) \
        or next((it for it in box.items if target and (target in it.name or it.name in target)), None)
    if not item:
        return {"ok": False, "error": tr(user.lang, "err_no_item", box=box.label, item=target)}
    name = item.name
    db.delete(item)
    db.commit()
    return {"ok": True, "summary": tr(user.lang, "res_deleted_item", box=box.name, item=name)}


def _delete_box(db, user, args):
    box = resolve_box(db, user, args.get("box", ""))
    if not box:
        return {"ok": False, "error": tr(user.lang, "err_box_not_found")}
    name = box.name
    db.delete(box)  # cascade 删除物品/媒体
    db.commit()
    return {"ok": True, "summary": tr(user.lang, "res_deleted_box", box=name)}


def _empty_box(db, user, args):
    box = resolve_box(db, user, args.get("box", ""))
    if not box:
        return {"ok": False, "error": tr(user.lang, "err_box_not_found")}
    n = len(box.items)
    for it in list(box.items):
        db.delete(it)
    db.commit()
    return {"ok": True, "summary": tr(user.lang, "res_emptied", box=box.name, n=n)}


def _merge_boxes(db, user, args):
    target = resolve_box(db, user, args.get("target_box", ""))
    if not target:
        return {"ok": False, "error": tr(user.lang, "err_target_not_found")}
    running = {it.name: it for it in target.items}
    merged_from = []
    for ref in args.get("source_boxes", []):
        src = resolve_box(db, user, ref)
        if not src or src.id == target.id:
            continue
        for it in list(src.items):
            if it.name in running:
                # 同名 → 数量相加;来源那条留在 src,随 src 删除而删
                running[it.name].qty_text = _merge_qty(running[it.name].qty_text, it.qty_text, user.lang)
            else:
                it.box = target  # 关系赋值:back_populates 会把它移出 src.items
                running[it.name] = it
        for m in list(src.media):  # 来源照片/音频并入目标
            m.box = target
        merged_from.append(src.name)
        db.delete(src)  # 删除来源箱(及其剩余同名物品)
    # 目标箱原本没封面 → 自动拿一张并入的照片当封面
    if not target.photo_url:
        photo = next((m for m in target.media if m.kind == "photo"), None)
        if photo:
            target.photo_url = photo.url
    db.commit()
    return {"ok": True, "summary": tr(user.lang, "res_merged", srcs=join(user.lang, merged_from), target=target.name)}
