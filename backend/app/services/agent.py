"""Agent 编排:function-calling 循环。读/增量/修改工具直接执行;破坏性工具暂停返回确认。"""
import json

from sqlalchemy.orm import Session

from ..models import User
from . import agent_tools
from .llm import llm

_SYSTEM = """你是 BoxMind 的智能仓储助手。用户用自然语言下达操作指令(改位置、改名、加/删物品、移动物品、合并箱子、删箱、绑码等),你要调用合适的工具完成。

规则:
- 能做就调工具做;一句话需要多步(如先搜物品在哪、再移动)就连续调用多个工具。
- 指代不清时(例如多个箱子都有同名物品)不要乱猜,用一句话向用户反问澄清(直接回复文字、不调工具)。
- 数量填最终值:用户说"再加3个"而当前是2个,你要算好填 ×5。
- 全部做完后用一句简短中文汇报你做了什么。
- 破坏性操作(删除/合并/清空)直接调对应工具即可,系统会向用户二次确认,你无需自己确认或追问。

下面是该用户当前所有箱子的快照(用于解析"7号""Liam""厨房箱"等指代,以及计算数量):
"""


async def run(db: Session, user: User, history: list[dict], message: str, gps: dict | None) -> dict:
    boxes = agent_tools.all_boxes(db, user)
    index = json.dumps([agent_tools.box_brief(b) for b in boxes], ensure_ascii=False)
    messages: list[dict] = [{"role": "system", "content": _SYSTEM + index}]
    for m in history or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})
    ctx = {"gps": gps}

    for _ in range(6):  # 最多 6 步,防失控
        msg = await llm.chat_with_tools(messages, agent_tools.TOOLS)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return {"type": "message", "text": (msg.get("content") or "好的。").strip()}

        # 破坏性工具 → 暂停,交前端确认(M14 填充 DESTRUCTIVE)
        pending = [tc for tc in tool_calls if tc["function"]["name"] in agent_tools.DESTRUCTIVE]
        if pending:
            from . import agent_destructive
            actions = []
            for tc in pending:
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                actions.append({
                    "tool": tc["function"]["name"],
                    "args": args,
                    "summary": agent_destructive.summarize(db, user, tc["function"]["name"], args),
                })
            return {"type": "confirm", "actions": actions,
                    "text": (msg.get("content") or "").strip()}

        # 直接执行类
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })
        for tc in tool_calls:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await agent_tools.execute(db, user, tc["function"]["name"], args, ctx)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return {"type": "message", "text": "已尽力处理完。"}
