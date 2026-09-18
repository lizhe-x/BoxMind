"""Agent 编排:function-calling 循环。读/增量/修改工具直接执行;破坏性工具暂停返回确认。"""
import json

from sqlalchemy.orm import Session

from ..i18n import lang_name, tr
from ..models import User
from . import agent_tools
from .llm import llm

_SYSTEM = """You are BoxMind's storage assistant. The user gives instructions in natural language about their
storage boxes (change a location, rename, add or remove items, move items, merge boxes, delete a box,
bind a barcode, ...). Call the right tools to carry them out.

Rules:
- If it can be done, do it with tools. One sentence may need several steps (e.g. search where an item is,
  then move it): chain tool calls.
- If a reference is ambiguous (e.g. several boxes hold an item with that name) do not guess; ask one short
  clarifying question in plain text instead of calling a tool.
- Quantities are final values: if the user says "add 3 more" and the box has 2, send ×5.
- When everything is done, report what you did in one short sentence.
- Destructive operations (delete / merge / empty) are fine to call directly; the app asks the user to
  confirm them, you do not need to ask.
- Answer in {lang}. Keep item names exactly as the user wrote them.

Snapshot of the user's boxes (to resolve references like "box 7", "Liam", "the kitchen box" and to compute
quantities):
"""


async def run(db: Session, user: User, history: list[dict], message: str, gps: dict | None) -> dict:
    boxes = agent_tools.all_boxes(db, user)
    index = json.dumps([agent_tools.box_brief(b) for b in boxes], ensure_ascii=False)
    messages: list[dict] = [{"role": "system", "content": _SYSTEM.format(lang=lang_name(user.lang)) + index}]
    for m in history or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})
    ctx = {"gps": gps}

    for _ in range(6):  # 最多 6 步,防失控
        msg = await llm.chat_with_tools(messages, agent_tools.TOOLS)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return {"type": "message", "text": (msg.get("content") or tr(user.lang, "agent_default_reply")).strip()}

        # 破坏性工具 → 暂停,交前端确认。同一轮里夹带的非破坏性调用(如"先移动再合并")照常执行,
        # 否则它们会随着暂停被静默丢弃,用户看到的只有确认卡。
        pending = [tc for tc in tool_calls if tc["function"]["name"] in agent_tools.DESTRUCTIVE]
        if pending:
            from . import agent_destructive
            executed = []
            for tc in tool_calls:
                if tc["function"]["name"] in agent_tools.DESTRUCTIVE:
                    continue
                result = await agent_tools.execute(db, user, tc["function"]["name"], _args(tc), ctx)
                executed.append({"tool": tc["function"]["name"], "result": result})
            actions = []
            for tc in pending:
                args = _args(tc)
                actions.append({
                    "tool": tc["function"]["name"],
                    "args": args,
                    "summary": agent_destructive.summarize(db, user, tc["function"]["name"], args),
                })
            return {"type": "confirm", "actions": actions, "executed": executed,
                    "text": (msg.get("content") or "").strip()}

        # 直接执行类
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })
        for tc in tool_calls:
            result = await agent_tools.execute(db, user, tc["function"]["name"], _args(tc), ctx)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return {"type": "message", "text": tr(user.lang, "agent_step_cap")}


def _args(tc: dict) -> dict:
    try:
        return json.loads(tc["function"]["arguments"] or "{}")
    except json.JSONDecodeError:
        return {}
