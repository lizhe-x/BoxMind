"""The function-calling loop in services/agent.py, driven by a scripted model."""
import json

from sqlalchemy.orm import Session

from app.models import User
from app.services import agent, agent_tools, boxes_service
from tests.conftest import ScriptedLLM, assistant_msg, tool_call


async def _seed(db: Session, user: User) -> None:
    b5 = boxes_service.create_box(db, user, "5号", location_text="车库")
    b7 = boxes_service.create_box(db, user, "7号")
    await boxes_service.add_items(db, b5, [{"name": "头灯", "qty_text": "×2"}])
    await boxes_service.add_items(db, b7, [{"name": "帐篷", "qty_text": "×1"}])
    db.commit()


async def test_plain_reply_returns_message_without_tools(db, user, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg("  你想操作哪个箱子?  "))
    res = await agent.run(db, user, [], "改一下位置", None)
    assert res == {"type": "message", "text": "你想操作哪个箱子?"}
    assert len(llm.calls) == 1


async def test_system_prompt_carries_box_snapshot_and_history(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg("好的"))
    history = [
        {"role": "user", "content": "之前的话"},
        {"role": "assistant", "content": "之前的回复"},
        {"role": "tool", "content": "must be dropped"},
        {"role": "user", "content": ""},
    ]
    await agent.run(db, user, history, "现在的话", None)
    msgs = llm.calls[0]["messages"]
    assert msgs[0]["role"] == "system"
    snapshot = json.loads(msgs[0]["content"].split("\n")[-1])
    assert {b["编号"] for b in snapshot} == {"5号", "7号"}
    assert snapshot[0]["物品"] or snapshot[1]["物品"]
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"]
    assert msgs[-1]["content"] == "现在的话"
    assert llm.calls[0]["tools"] is agent_tools.TOOLS


async def test_tool_result_is_fed_back_then_model_summarises(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(
        assistant_msg(None, [tool_call("set_box_location", {"box": "7号", "location_text": "阳台"})]),
        assistant_msg("已把7号箱位置改为阳台。"),
    )
    res = await agent.run(db, user, [], "7号箱在阳台", None)
    assert res == {"type": "message", "text": "已把7号箱位置改为阳台。"}
    assert agent_tools.resolve_box(db, user, "7号").location_text == "阳台"

    second_call = llm.calls[1]["messages"]
    assert second_call[-2]["role"] == "assistant" and second_call[-2]["tool_calls"]
    assert second_call[-1]["role"] == "tool" and second_call[-1]["tool_call_id"] == "call_1"
    assert json.loads(second_call[-1]["content"]) == {"ok": True, "box": "7号", "location": "阳台"}


async def test_multi_step_search_then_move(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(
        assistant_msg(None, [tool_call("search_items", {"query": "头灯"}, "c1")]),
        assistant_msg(None, [tool_call("move_items", {"from_box": "5号", "to_box": "7号", "item_names": ["头灯"]}, "c2")]),
        assistant_msg("头灯已从5号移到7号。"),
    )
    res = await agent.run(db, user, [], "把头灯移到7号", None)
    assert res["type"] == "message"
    db.expire_all()
    assert [i.name for i in agent_tools.resolve_box(db, user, "7号").items] == ["帐篷", "头灯"]
    assert len(llm.calls) == 3
    search_result = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert search_result["results"][0]["箱子编号"] == "5号"


async def test_parallel_tool_calls_in_one_turn(db, user, llm: ScriptedLLM) -> None:
    llm.script(
        assistant_msg(None, [tool_call("create_box", {"name": "A"}, "c1"), tool_call("create_box", {"name": "B"}, "c2")]),
        assistant_msg("建好了 A 和 B。"),
    )
    await agent.run(db, user, [], "建两个箱子 A 和 B", None)
    tool_msgs = [m for m in llm.calls[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2"]
    assert agent_tools.resolve_box(db, user, "A") and agent_tools.resolve_box(db, user, "B")


async def test_destructive_tool_pauses_for_confirmation(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg("要删了哦", [tool_call("delete_box", {"box": "5号"})]))
    res = await agent.run(db, user, [], "删掉5号箱", None)
    assert res["type"] == "confirm" and res["text"] == "要删了哦"
    assert res["actions"] == [{
        "tool": "delete_box", "args": {"box": "5号"}, "summary": "删除整个箱子「5号」(含 1 类物品)",
    }]
    assert agent_tools.resolve_box(db, user, "5号") is not None  # nothing executed
    assert len(llm.calls) == 1  # loop stops immediately


async def test_mixed_turn_only_surfaces_destructive_calls(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg(None, [
        tool_call("set_box_location", {"box": "7号", "location_text": "阳台"}, "c1"),
        tool_call("empty_box", {"box": "5号"}, "c2"),
    ]))
    res = await agent.run(db, user, [], "...", None)
    assert res["type"] == "confirm" and [a["tool"] for a in res["actions"]] == ["empty_box"]
    # the non-destructive sibling runs immediately; only the destructive call waits for the user
    assert agent_tools.resolve_box(db, user, "7号").location_text == "阳台"
    assert res["executed"] == [{"tool": "set_box_location", "result": {"ok": True, "box": "7号", "location": "阳台"}}]
    assert len(agent_tools.resolve_box(db, user, "5号").items) == 1  # empty_box not executed


async def test_malformed_arguments_do_not_crash(db, user, llm: ScriptedLLM) -> None:
    llm.script(
        assistant_msg(None, [tool_call("get_box", "{not json")]),
        assistant_msg("参数有问题"),
    )
    res = await agent.run(db, user, [], "x", None)
    assert res["type"] == "message"
    fed_back = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert fed_back["ok"] is False  # KeyError inside the tool must surface as a tool error, not a 500


async def test_malformed_destructive_arguments_still_confirm(db, user, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg(None, [tool_call("delete_item", "oops")]))
    res = await agent.run(db, user, [], "x", None)
    assert res["type"] == "confirm" and res["actions"][0]["args"] == {}


async def test_step_cap_stops_runaway_loops(db, user, llm: ScriptedLLM) -> None:
    for i in range(6):
        llm.script(assistant_msg(None, [tool_call("get_box", {"box": "nope"}, f"c{i}")]))
    llm.script(assistant_msg("never reached"))
    res = await agent.run(db, user, [], "loop", None)
    assert res == {"type": "message", "text": "已尽力处理完。"}
    assert len(llm.calls) == 6
    assert len(llm.tool_replies) == 1


async def test_gps_context_reaches_tools(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg(None, [tool_call("set_box_gps", {"box": "7号"})]), assistant_msg("记好了"))
    await agent.run(db, user, [], "记一下我现在的位置到7号", {"lat": 1.5, "lng": 2.5})
    box = agent_tools.resolve_box(db, user, "7号")
    assert (box.gps_lat, box.gps_lng) == (1.5, 2.5)


async def test_empty_content_gets_default_text(db, user, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg(None))
    assert (await agent.run(db, user, [], "x", None))["text"] == "好的。"
