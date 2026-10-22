"""Agent 编排:function-calling 循环。读/增量/修改工具直接执行;破坏性工具暂停返回确认。

每次运行开一条 trace(模型、prompt 版本、工具调用、步数、耗时、结局),评测和生产追踪都从这里读。
"""
import json
import time

from sqlalchemy.orm import Session

from ..i18n import lang_name, tr
from ..models import User
from . import agent_tools, trace
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

MAX_STEPS = 6  # 最多 6 步,防失控


async def run(db: Session, user: User, history: list[dict], message: str, gps: dict | None) -> dict:
    t = trace.start("agent", model=llm.model_name, prompts={"agent": trace.prompt_id(_SYSTEM)},
                    input=message, lang=user.lang)
    try:
        return await _run(db, user, history, message, gps, t)
    except Exception as e:
        t.error = str(e)
        t.finish("error")
        raise


async def _run(db: Session, user: User, history: list[dict], message: str, gps: dict | None, t: trace.Trace) -> dict:
    boxes = agent_tools.all_boxes(db, user)
    index = json.dumps([agent_tools.box_brief(b) for b in boxes], ensure_ascii=False)
    messages: list[dict] = [{"role": "system", "content": _SYSTEM.format(lang=lang_name(user.lang)) + index}]
    for m in history or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})
    ctx = {"gps": gps}

    for _ in range(MAX_STEPS):
        t.steps += 1
        msg = await llm.chat_with_tools(messages, agent_tools.TOOLS)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            text = (msg.get("content") or tr(user.lang, "agent_default_reply")).strip()
            t.finish("message", text=text)
            return {"type": "message", "text": text}

        # 破坏性工具 → 暂停,交前端确认。同一轮里夹带的非破坏性调用(如"先移动再合并")照常执行,
        # 否则它们会随着暂停被静默丢弃,用户看到的只有确认卡。
        pending = [tc for tc in tool_calls if tc["function"]["name"] in agent_tools.DESTRUCTIVE]
        if pending:
            from . import agent_destructive
            executed = []
            for tc in tool_calls:
                if tc["function"]["name"] in agent_tools.DESTRUCTIVE:
                    continue
                result = await _execute(db, user, tc, ctx, t)
                executed.append({"tool": tc["function"]["name"], "result": result})
            actions = []
            for tc in pending:
                args = _args(tc)
                actions.append({
                    "tool": tc["function"]["name"],
                    "args": args,
                    "summary": agent_destructive.summarize(db, user, tc["function"]["name"], args),
                })
            t.confirm = [a["tool"] for a in actions]
            text = (msg.get("content") or "").strip()
            t.finish("confirm", text=text, actions=[{"tool": a["tool"], "args": a["args"]} for a in actions])
            return {"type": "confirm", "actions": actions, "executed": executed, "text": text}

        # 直接执行类
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })
        for tc in tool_calls:
            result = await _execute(db, user, tc, ctx, t)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    text = tr(user.lang, "agent_step_cap")
    t.finish("step_cap", text=text)
    return {"type": "message", "text": text}


async def _execute(db: Session, user: User, tc: dict, ctx: dict, t: trace.Trace) -> dict:
    name, args = tc["function"]["name"], _args(tc)
    t0 = time.monotonic()
    try:
        result = await agent_tools.execute(db, user, name, args, ctx)
    except Exception as e:
        t.tool(name, args, None, trace.ms_since(t0), error=f"{type(e).__name__}: {e}")
        raise
    t.tool(name, args, result, trace.ms_since(t0))
    return result


def _args(tc: dict) -> dict:
    try:
        return json.loads(tc["function"]["arguments"] or "{}")
    except json.JSONDecodeError:
        return {}
