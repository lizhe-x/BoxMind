"""Agent 工具注册表:模型可调用的底层操作(读/增量/修改)。

破坏性工具(删/合并/清空)在 agent_destructive.py,由 agent 暂停确认后再执行。
这里的执行器都是「直接执行」类。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

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
        "编号": box.label,
        "名字": box.name,
        "位置": box.location_text or "未记录",
        "物品": [{"名称": it.name, "数量": it.qty_text} for it in box.items],
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

TOOLS = [
    _f("search_items", "按关键词语义搜索用户所有箱子里的物品,返回命中物品及所在箱子",
       {"query": {**_S, "description": "要找的物品关键词"}}, ["query"]),
    _f("get_box", "查看某个箱子的详情(物品、位置)", {"box": {**_S, "description": "箱子编号或名字"}}, ["box"]),
    _f("create_box", "新建一个空箱子(可带位置)",
       {"name": {**_S, "description": "箱子名字/编号,如 7号 或 Liam"},
        "location_text": {**_S, "description": "可选,位置描述"}}, ["name"]),
    _f("add_items", "往某箱子加物品(箱子不存在则自动新建);同名物品会更新为给定数量",
       {"box": _S, "items": {"type": "array", "items": {"type": "object", "properties": {
           "name": _S, "qty_text": {**_S, "description": "如 ×3、×2 双、若干"}}, "required": ["name"]}}},
       ["box", "items"]),
    _f("set_box_location", "设置/更新箱子的文字位置描述",
       {"box": _S, "location_text": _S}, ["box", "location_text"]),
    _f("set_box_gps", "把用户当前 GPS 位置记录到某箱子(用户说'记一下我现在的位置'时用)",
       {"box": _S}, ["box"]),
    _f("rename_box", "修改箱子的名字/编号(重名会自动加后缀)",
       {"box": {**_S, "description": "当前编号或名字"}, "new_name": {**_S, "description": "新名字"}},
       ["box", "new_name"]),
    _f("update_item", "修改箱子里某个物品的名称或数量(数量为最终值,累加/覆盖由你算好)",
       {"box": _S, "item_name": _S, "new_name": _S, "qty_text": _S}, ["box", "item_name"]),
    _f("move_items", "把若干物品从一个箱子移到另一个箱子",
       {"from_box": _S, "to_box": _S, "item_names": _SA}, ["from_box", "to_box", "item_names"]),
    _f("set_barcode", "给箱子绑定条码/二维码码值", {"box": _S, "code": _S}, ["box", "code"]),
    _f("undo_last", "撤销上一步破坏性操作(删除/合并/清空),把数据还原(用户说'撤销''撤回''还原'时用)", {}, []),
    # ── 破坏性(系统会向用户二次确认后才执行) ──
    _f("delete_item", "从某箱子删除一个物品", {"box": _S, "item_name": _S}, ["box", "item_name"]),
    _f("delete_box", "删除整个箱子(连同里面的物品)", {"box": _S}, ["box"]),
    _f("empty_box", "清空箱子里的所有物品,但保留箱子本身", {"box": _S}, ["box"]),
    _f("merge_boxes", "把若干来源箱子合并到目标箱子(来源物品并入目标,来源空箱删除)",
       {"source_boxes": _SA, "target_box": _S}, ["source_boxes", "target_box"]),
]

DESTRUCTIVE: set[str] = {"delete_item", "delete_box", "empty_box", "merge_boxes"}


# ── 执行器(直接执行类) ────────────────────────
async def execute(db: Session, user: User, name: str, args: dict, ctx: dict) -> dict:
    fn = _EXEC.get(name)
    if not fn:
        return {"ok": False, "error": f"未知工具 {name}"}
    try:
        return await fn(db, user, args, ctx)
    except _ToolError as e:
        return {"ok": False, "error": str(e)}


class _ToolError(Exception):
    pass


def _need_box(db, user, ref):
    box = resolve_box(db, user, ref)
    if not box:
        raise _ToolError(f"没找到箱子「{ref}」")
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
        {"物品": r.name, "数量": r.qty_text, "箱子编号": r.label, "箱名": r[3], "相似度": round(1 - r.d, 2)}
        for r in rows
    ]}


async def _get_box(db, user, args, ctx):
    return {"ok": True, "box": box_brief(_need_box(db, user, args["box"]))}


async def _create_box(db, user, args, ctx):
    name, duped = dedup_name(db, user, args["name"].strip())
    box = boxes_service.create_box(db, user, name, location_text=args.get("location_text"))
    db.commit()
    return {"ok": True, "created": box.label, "renamed_to": name if duped else None,
            "note": f"名字重复,已建为「{name}」" if duped else None}


async def _add_items(db, user, args, ctx):
    box = resolve_box(db, user, args["box"])
    created = False
    if not box:
        name, _ = dedup_name(db, user, args["box"].strip())
        box = boxes_service.create_box(db, user, name, source="text")
        created = True
    items = [{"name": it["name"], "qty_text": it.get("qty_text") or "若干"} for it in args.get("items", []) if it.get("name")]
    if not items:
        raise _ToolError("没有要添加的物品")
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
        return {"ok": False, "error": "当前没有可用的 GPS 位置(用户未授权定位)"}
    box = _need_box(db, user, args["box"])
    box.gps_lat, box.gps_lng = gps["lat"], gps["lng"]
    db.commit()
    return {"ok": True, "box": box.label, "gps_saved": True}


async def _rename_box(db, user, args, ctx):
    box = _need_box(db, user, args["box"])
    new_name, duped = dedup_name(db, user, args["new_name"].strip())
    norm, label, _ = normalize_label(new_name)
    box.norm_label, box.label, box.name = norm, label, new_name
    db.commit()
    return {"ok": True, "box": new_name, "renamed_from": args["box"],
            "note": f"名字重复,已改为「{new_name}」" if duped else None}


async def _update_item(db, user, args, ctx):
    box = _need_box(db, user, args["box"])
    target = args["item_name"].strip()
    item = next((it for it in box.items if it.name == target), None)
    if not item:
        item = next((it for it in box.items if target in it.name or it.name in target), None)
    if not item:
        raise _ToolError(f"「{box.label}」里没找到物品「{target}」")
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
        else {"ok": False, "error": "没找到要移动的物品"}


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
