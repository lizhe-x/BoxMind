"""Agent 工具注册表:模型可调用的底层操作(读/增量/修改)。

破坏性工具(删/合并/清空)在 agent_destructive.py,由 agent 暂停确认后再执行。
这里的执行器都是「直接执行」类。工具结果里的文字用用户界面语言(模型会照着转述)。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..i18n import tr
from ..models import Box, Item, User
from ..normalize import normalize_label
from . import boxes_service, embeddings


# ── 解析与去重 ────────────────────────────────
def resolve_box(db: Session, user: User, ref: str) -> Box | None:
    """按 编号/名字 解析箱子(norm_label 优先,再按 name 不区分大小写)。"""
    if not ref:
        return None
    norm, _, _ = normalize_label(ref)
    box = db.scalar(
        select(Box).options(selectinload(Box.items), selectinload(Box.media))
        .where(Box.user_id == user.id, Box.norm_label == norm)
    )
    if box:
        return box
    return db.scalar(
        select(Box).options(selectinload(Box.items), selectinload(Box.media))
        .where(Box.user_id == user.id, func.lower(Box.name) == ref.strip().lower())
    )


def dedup_name(db: Session, user: User, name: str) -> tuple[str, bool]:
    """重名则加后缀(Liam → Liam2),返回 (最终名, 是否重名过)。"""
    if not resolve_box(db, user, name):
        return name, False
    i = 2
    while resolve_box(db, user, f"{name}{i}"):
        i += 1
    return f"{name}{i}", True


def box_brief(box: Box) -> dict:
    return {
        "label": box.label,
        "name": box.name,
        "location": box.location_text or None,
        "items": [{"name": it.name, "qty": it.qty_text} for it in box.items],
    }


def all_boxes(db: Session, user: User) -> list[Box]:
    return db.scalars(
        select(Box).options(selectinload(Box.items), selectinload(Box.media))
        .where(Box.user_id == user.id).order_by(Box.updated_at.desc())
    ).all()


# ── 工具 schema(给模型) ──────────────────────
def _f(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required},
    }}

_S = {"type": "string"}
_SA = {"type": "array", "items": {"type": "string"}}
_BOX = {**_S, "description": "box label or name, e.g. 7, 7号, Liam, kitchen box"}

TOOLS = [
    _f("search_items", "Semantic search over all of the user's items; returns matching items and the box they are in",
       {"query": {**_S, "description": "what to look for"}}, ["query"]),
    _f("get_box", "Show one box: its items and location", {"box": _BOX}, ["box"]),
    _f("create_box", "Create a new empty box (optionally with a location)",
       {"name": {**_S, "description": "box label or name, e.g. 7 or Liam"},
        "location_text": {**_S, "description": "optional location description"}}, ["name"]),
    _f("add_items", "Add items to a box (the box is created if it does not exist); an item with the same name "
                    "is updated to the given quantity",
       {"box": _BOX, "items": {"type": "array", "items": {"type": "object", "properties": {
           "name": _S, "qty_text": {**_S, "description": "e.g. ×3, ×2 pairs, some"}}, "required": ["name"]}}},
       ["box", "items"]),
    _f("set_box_location", "Set or update the box's location description",
       {"box": _BOX, "location_text": _S}, ["box", "location_text"]),
    _f("set_box_gps", "Store the user's current GPS position on a box (when the user says 'remember where I am')",
       {"box": _BOX}, ["box"]),
    _f("rename_box", "Rename a box (a duplicate name gets a numeric suffix)",
       {"box": {**_S, "description": "current label or name"}, "new_name": {**_S, "description": "new name"}},
       ["box", "new_name"]),
    _f("update_item", "Change an item's name or quantity in a box (quantity is the final value; you compute "
                      "additions yourself)",
       {"box": _BOX, "item_name": _S, "new_name": _S, "qty_text": _S}, ["box", "item_name"]),
    _f("move_items", "Move items from one box to another",
       {"from_box": _BOX, "to_box": _BOX, "item_names": _SA}, ["from_box", "to_box", "item_names"]),
    _f("set_barcode", "Bind a barcode / QR code value to a box", {"box": _BOX, "code": _S}, ["box", "code"]),
    _f("undo_last", "Undo the last destructive operation (delete / merge / empty) and restore the data "
                    "(when the user says undo / revert / restore)", {}, []),
    # ── 破坏性(系统会向用户二次确认后才执行) ──
    _f("delete_item", "Delete one item from a box", {"box": _BOX, "item_name": _S}, ["box", "item_name"]),
    _f("delete_box", "Delete a whole box including its items", {"box": _BOX}, ["box"]),
    _f("empty_box", "Remove all items from a box but keep the box", {"box": _BOX}, ["box"]),
    _f("merge_boxes", "Merge source boxes into a target box (items move to the target, emptied sources are deleted)",
       {"source_boxes": _SA, "target_box": _BOX}, ["source_boxes", "target_box"]),
]

DESTRUCTIVE: set[str] = {"delete_item", "delete_box", "empty_box", "merge_boxes"}


# ── 执行器(直接执行类) ────────────────────────
async def execute(db: Session, user: User, name: str, args: dict, ctx: dict) -> dict:
    fn = _EXEC.get(name)
    if not fn:
        return {"ok": False, "error": tr(user.lang, "tool_unknown", name=name)}
    try:
        return await fn(db, user, args, ctx)
    except _ToolError as e:
        return {"ok": False, "error": str(e)}
    except KeyError as e:
        # 模型漏传/错传参数(或 arguments 不是合法 JSON)时,把问题回灌给模型而不是让整个请求 500
        return {"ok": False, "error": tr(user.lang, "tool_missing_arg", arg=e.args[0])}


class _ToolError(Exception):
    pass


def _need_box(db, user, ref):
    box = resolve_box(db, user, ref)
    if not box:
        raise _ToolError(tr(user.lang, "box_not_found", ref=ref))
    return box


async def _search_items(db, user, args, ctx):
    q = args.get("query", "")
    qvec = (await embeddings.embed([q]))[0]
    rows = db.execute(
        select(Item.name, Item.qty_text, Box.label, Box.name, Item.embedding.cosine_distance(qvec).label("d"))
        .join(Box, Item.box_id == Box.id)
        .where(Box.user_id == user.id, Item.embedding.is_not(None))
        .order_by("d").limit(8)
    ).all()
    return {"ok": True, "results": [
        {"item": r.name, "qty": r.qty_text, "box_label": r.label, "box_name": r[3], "similarity": round(1 - r.d, 2)}
        for r in rows
    ]}


async def _get_box(db, user, args, ctx):
    return {"ok": True, "box": box_brief(_need_box(db, user, args["box"]))}


async def _create_box(db, user, args, ctx):
    name, duped = dedup_name(db, user, args["name"].strip())
    box = boxes_service.create_box(db, user, name, location_text=args.get("location_text"))
    db.commit()
    return {"ok": True, "created": box.label, "renamed_to": name if duped else None,
            "note": tr(user.lang, "dup_created", name=name) if duped else None}


async def _add_items(db, user, args, ctx):
    box = resolve_box(db, user, args["box"])
    created = False
    if not box:
        name, _ = dedup_name(db, user, args["box"].strip())
        box = boxes_service.create_box(db, user, name, source="text")
        created = True
    some = tr(user.lang, "qty_some")
    items = [
        {"name": it["name"], "qty_text": it.get("qty_text") or some}
        for it in args.get("items", [])
        if it.get("name")
    ]
    if not items:
        raise _ToolError(tr(user.lang, "no_items"))
    await boxes_service.add_items(db, box, items)
    db.commit()
    return {"ok": True, "box": box.label, "created_box": created, "added": [i["name"] for i in items]}


async def _set_box_location(db, user, args, ctx):
    box = _need_box(db, user, args["box"])
    box.location_text = args["location_text"]
    db.commit()
    return {"ok": True, "box": box.label, "location": box.location_text}


async def _set_box_gps(db, user, args, ctx):
    gps = ctx.get("gps")
    if not gps or gps.get("lat") is None:
        return {"ok": False, "error": tr(user.lang, "gps_unavailable")}
    box = _need_box(db, user, args["box"])
    box.gps_lat, box.gps_lng = gps["lat"], gps["lng"]
    db.commit()
    return {"ok": True, "box": box.label, "gps_saved": True}


async def _rename_box(db, user, args, ctx):
    box = _need_box(db, user, args["box"])
    new_name, duped = dedup_name(db, user, args["new_name"].strip())
    norm, label, _ = normalize_label(new_name, user.lang)
    box.norm_label, box.label, box.name = norm, label, new_name
    db.commit()
    return {"ok": True, "box": new_name, "renamed_from": args["box"],
            "note": tr(user.lang, "dup_renamed", name=new_name) if duped else None}


async def _update_item(db, user, args, ctx):
    box = _need_box(db, user, args["box"])
    target = args["item_name"].strip()
    item = next((it for it in box.items if it.name == target), None)
    if not item:
        item = next((it for it in box.items if target in it.name or it.name in target), None)
    if not item:
        raise _ToolError(tr(user.lang, "item_not_found", item=target, box=box.label))
    if args.get("new_name"):
        item.name = args["new_name"]
    if args.get("qty_text"):
        item.qty_text = args["qty_text"]
    db.commit()
    return {"ok": True, "box": box.label, "item": item.name, "qty": item.qty_text}


async def _move_items(db, user, args, ctx):
    src = _need_box(db, user, args["from_box"])
    dst = _need_box(db, user, args["to_box"])
    names = args.get("item_names", [])
    moved = []
    for nm in names:
        it = next((x for x in src.items if x.name == nm or nm in x.name), None)
        if it:
            it.box_id = dst.id
            moved.append(it.name)
    db.commit()
    return {"ok": True, "from": src.label, "to": dst.label, "moved": moved} if moved \
        else {"ok": False, "error": tr(user.lang, "move_none")}


async def _set_barcode(db, user, args, ctx):
    box = _need_box(db, user, args["box"])
    box.barcode = args["code"]
    db.commit()
    return {"ok": True, "box": box.label, "barcode": box.barcode}


async def _undo_last(db, user, args, ctx):
    from . import agent_destructive
    return await agent_destructive.restore_last(db, user)


_EXEC = {
    "search_items": _search_items,
    "get_box": _get_box,
    "create_box": _create_box,
    "add_items": _add_items,
    "set_box_location": _set_box_location,
    "set_box_gps": _set_box_gps,
    "rename_box": _rename_box,
    "update_item": _update_item,
    "move_items": _move_items,
    "set_barcode": _set_barcode,
    "undo_last": _undo_last,
}
