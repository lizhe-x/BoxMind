"""User-facing strings produced by the backend, in the user's UI language.

Only text that reaches the user directly lives here: default box names, tool
result messages the model relays, confirm-card summaries, undo messages and
time formatting. Prompts are parameterised with the language name so the
models answer in the same language. The UI default is English; Chinese is the
other supported language.
"""
from __future__ import annotations

from datetime import datetime

LANGS = ("en", "zh")
DEFAULT_LANG = "en"


def norm_lang(lang: str | None) -> str:
    lang = (lang or "").lower()
    return "zh" if lang.startswith("zh") else DEFAULT_LANG


def lang_name(lang: str | None) -> str:
    return "Chinese (中文)" if norm_lang(lang) == "zh" else "English"


_S: dict[str, dict[str, str]] = {
    "en": {
        # box naming
        "label_num": "{n}",
        "name_num": "Box {n}",
        "qty_some": "some",
        "list_sep": ", ",
        # agent loop
        "agent_default_reply": "Done.",
        "agent_step_cap": "I did what I could.",
        # tool results (relayed to the model, which answers the user)
        "tool_unknown": "unknown tool {name}",
        "tool_missing_arg": "missing argument {arg}",
        "box_not_found": "box “{ref}” not found",
        "no_items": "no items to add",
        "item_not_found": "no item “{item}” in “{box}”",
        "move_none": "none of those items were found",
        "gps_unavailable": "no GPS position available (location permission not granted)",
        "dup_created": "name already taken, created as “{name}”",
        "dup_renamed": "name already taken, renamed to “{name}”",
        # destructive operations
        "op_delete_item": "delete item",
        "op_delete_box": "delete box",
        "op_empty_box": "empty box",
        "op_merge_boxes": "merge boxes",
        "op_generic": "run {tool}",
        "sum_delete_item": "Delete “{item}” from “{box}”",
        "sum_delete_box": "Delete box “{box}”",
        "sum_delete_box_n": " (with {n} item types)",
        "sum_empty_box": "Empty “{box}” ({n} item types), keep the box",
        "sum_merge": "Move everything from “{srcs}” into “{target}” and delete the emptied source boxes",
        "res_deleted_item": "Deleted “{item}” from “{box}”",
        "res_deleted_box": "Deleted box “{box}”",
        "res_emptied": "Emptied “{box}” ({n} item types)",
        "res_merged": "Merged “{srcs}” into “{target}”",
        "err_box_not_found": "box not found",
        "err_target_not_found": "target box not found",
        "err_no_item": "no “{item}” in “{box}”",
        "err_unknown_op": "unknown operation {tool}",
        "undo_none": "nothing to undo",
        "undo_done": "Undid “{label}”, data restored",
        # RAG context
        "not_recorded": "not recorded",
        "recorded": "recorded",
        "hint_none": "none",
        "hint_item": "{name} (in {label}, similarity {sim:.2f})",
        "time_today": "today {hm}",
    },
    "zh": {
        "label_num": "{n}号",
        "name_num": "{n}号箱",
        "qty_some": "若干",
        "list_sep": "、",
        "agent_default_reply": "好的。",
        "agent_step_cap": "已尽力处理完。",
        "tool_unknown": "未知工具 {name}",
        "tool_missing_arg": "缺少参数 {arg}",
        "box_not_found": "没找到箱子「{ref}」",
        "no_items": "没有要添加的物品",
        "item_not_found": "「{box}」里没找到物品「{item}」",
        "move_none": "没找到要移动的物品",
        "gps_unavailable": "当前没有可用的 GPS 位置(用户未授权定位)",
        "dup_created": "名字重复,已建为「{name}」",
        "dup_renamed": "名字重复,已改为「{name}」",
        "op_delete_item": "删除物品",
        "op_delete_box": "删除箱子",
        "op_empty_box": "清空箱子",
        "op_merge_boxes": "合并箱子",
        "op_generic": "执行 {tool}",
        "sum_delete_item": "从「{box}」删除物品「{item}」",
        "sum_delete_box": "删除整个箱子「{box}」",
        "sum_delete_box_n": "(含 {n} 类物品)",
        "sum_empty_box": "清空「{box}」的 {n} 类物品(保留箱子本身)",
        "sum_merge": "把「{srcs}」的物品并入「{target}」,并删除清空后的来源箱",
        "res_deleted_item": "已从「{box}」删除「{item}」",
        "res_deleted_box": "已删除箱子「{box}」",
        "res_emptied": "已清空「{box}」的 {n} 类物品",
        "res_merged": "已把「{srcs}」并入「{target}」",
        "err_box_not_found": "没找到箱子",
        "err_target_not_found": "没找到目标箱子",
        "err_no_item": "「{box}」里没有「{item}」",
        "err_unknown_op": "未知操作 {tool}",
        "undo_none": "没有可撤销的操作",
        "undo_done": "已撤销「{label}」,数据已还原",
        "not_recorded": "未记录",
        "recorded": "已记录",
        "hint_none": "无",
        "hint_item": "{name}(在{label}, 相似度{sim:.2f})",
        "time_today": "今天 {hm}",
    },
}


def tr(lang: str | None, key: str, **kw) -> str:
    return _S[norm_lang(lang)][key].format(**kw)


def join(lang: str | None, parts: list[str]) -> str:
    return tr(lang, "list_sep").join(parts)


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fmt_time(dt: datetime, lang: str | None, now: datetime | None = None) -> str:
    """Short, human date for the RAG context: 'today 19:47' / 'Sep 17' / 'Sep 17, 2025'."""
    local = dt.astimezone()
    today = (now or datetime.now(local.tzinfo)).astimezone().date()
    d = local.date()
    if d == today:
        return tr(lang, "time_today", hm=local.strftime("%H:%M"))
    if norm_lang(lang) == "zh":
        return f"{d.month}月{d.day}日" if d.year == today.year else f"{d.year}年{d.month}月{d.day}日"
    mon = _MONTHS[d.month - 1]
    return f"{mon} {d.day}" if d.year == today.year else f"{mon} {d.day}, {d.year}"
