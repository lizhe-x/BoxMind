"""The function-calling loop in services/agent.py, driven by a scripted model."""
import json

from sqlalchemy.orm import Session

from app.models import User
from app.services import agent, agent_tools, boxes_service
from tests.conftest import ScriptedLLM, assistant_msg, tool_call


async def _seed(db: Session, user: User) -> None:
    b5 = boxes_service.create_box(db, user, "5", location_text="garage")
    b7 = boxes_service.create_box(db, user, "7")
    await boxes_service.add_items(db, b5, [{"name": "headlamp", "qty_text": "×2"}])
    await boxes_service.add_items(db, b7, [{"name": "tent", "qty_text": "×1"}])
    db.commit()


async def test_plain_reply_returns_message_without_tools(db, user, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg("  Which box do you mean?  "))
    res = await agent.run(db, user, [], "change the location", None)
    assert res == {"type": "message", "text": "Which box do you mean?"}
    assert len(llm.calls) == 1


async def test_system_prompt_carries_language_snapshot_and_history(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg("ok"))
    history = [
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "earlier reply"},
        {"role": "tool", "content": "must be dropped"},
        {"role": "user", "content": ""},
    ]
    await agent.run(db, user, history, "now", None)
    msgs = llm.calls[0]["messages"]
    assert msgs[0]["role"] == "system"
    assert "Answer in English" in msgs[0]["content"]
    snapshot = json.loads(msgs[0]["content"].split("\n")[-1])
    assert {b["label"] for b in snapshot} == {"5", "7"}
    assert {b["name"] for b in snapshot} == {"Box 5", "Box 7"}
    assert snapshot[0]["items"] or snapshot[1]["items"]
    assert [m["role"] for m in msgs[1:]] == ["user", "assistant", "user"]
    assert msgs[-1]["content"] == "now"
    assert llm.calls[0]["tools"] is agent_tools.TOOLS


async def test_system_prompt_language_follows_user(db, user, llm: ScriptedLLM) -> None:
    user.lang = "zh"
    llm.script(assistant_msg(None))
    res = await agent.run(db, user, [], "x", None)
    assert "Answer in Chinese (中文)" in llm.calls[0]["messages"][0]["content"]
    assert res["text"] == "好的。"


async def test_tool_result_is_fed_back_then_model_summarises(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(
        assistant_msg(None, [tool_call("set_box_location", {"box": "7", "location_text": "balcony"})]),
        assistant_msg("Box 7 is now on the balcony."),
    )
    res = await agent.run(db, user, [], "box 7 is on the balcony", None)
    assert res == {"type": "message", "text": "Box 7 is now on the balcony."}
    assert agent_tools.resolve_box(db, user, "7").location_text == "balcony"

    second_call = llm.calls[1]["messages"]
    assert second_call[-2]["role"] == "assistant" and second_call[-2]["tool_calls"]
    assert second_call[-1]["role"] == "tool" and second_call[-1]["tool_call_id"] == "call_1"
    assert json.loads(second_call[-1]["content"]) == {"ok": True, "box": "7", "location": "balcony"}


async def test_multi_step_search_then_move(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(
        assistant_msg(None, [tool_call("search_items", {"query": "headlamp"}, "c1")]),
        assistant_msg(None, [tool_call("move_items", {"from_box": "5", "to_box": "7", "item_names": ["headlamp"]}, "c2")]),
        assistant_msg("Moved the headlamp from box 5 to box 7."),
    )
    res = await agent.run(db, user, [], "move the headlamp to box 7", None)
    assert res["type"] == "message"
    db.expire_all()
    assert sorted(i.name for i in agent_tools.resolve_box(db, user, "7").items) == ["headlamp", "tent"]  # order = created_at, not stable
    assert len(llm.calls) == 3
    search_result = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert search_result["results"][0]["box_label"] == "5"


async def test_parallel_tool_calls_in_one_turn(db, user, llm: ScriptedLLM) -> None:
    llm.script(
        assistant_msg(None, [tool_call("create_box", {"name": "A"}, "c1"), tool_call("create_box", {"name": "B"}, "c2")]),
        assistant_msg("Created A and B."),
    )
    await agent.run(db, user, [], "create boxes A and B", None)
    tool_msgs = [m for m in llm.calls[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2"]
    assert agent_tools.resolve_box(db, user, "A") and agent_tools.resolve_box(db, user, "B")


async def test_destructive_tool_pauses_for_confirmation(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg("About to delete it", [tool_call("delete_box", {"box": "5"})]))
    res = await agent.run(db, user, [], "delete box 5", None)
    assert res["type"] == "confirm" and res["text"] == "About to delete it"
    assert res["actions"] == [{
        "tool": "delete_box", "args": {"box": "5"}, "summary": "Delete box “5” (with 1 item types)",
    }]
    assert res["executed"] == []
    assert agent_tools.resolve_box(db, user, "5") is not None  # nothing executed
    assert len(llm.calls) == 1  # loop stops immediately


async def test_mixed_turn_runs_safe_calls_and_confirms_the_rest(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg(None, [
        tool_call("set_box_location", {"box": "7", "location_text": "balcony"}, "c1"),
        tool_call("empty_box", {"box": "5"}, "c2"),
    ]))
    res = await agent.run(db, user, [], "...", None)
    assert res["type"] == "confirm" and [a["tool"] for a in res["actions"]] == ["empty_box"]
    # the non-destructive sibling runs immediately; only the destructive call waits for the user
    assert agent_tools.resolve_box(db, user, "7").location_text == "balcony"
    assert res["executed"] == [{"tool": "set_box_location", "result": {"ok": True, "box": "7", "location": "balcony"}}]
    assert len(agent_tools.resolve_box(db, user, "5").items) == 1  # empty_box not executed


async def test_malformed_arguments_do_not_crash(db, user, llm: ScriptedLLM) -> None:
    llm.script(
        assistant_msg(None, [tool_call("get_box", "{not json")]),
        assistant_msg("bad arguments"),
    )
    res = await agent.run(db, user, [], "x", None)
    assert res["type"] == "message"
    fed_back = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert fed_back == {"ok": False, "error": "missing argument box"}


async def test_malformed_destructive_arguments_still_confirm(db, user, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg(None, [tool_call("delete_item", "oops")]))
    res = await agent.run(db, user, [], "x", None)
    assert res["type"] == "confirm" and res["actions"][0]["args"] == {}


async def test_step_cap_stops_runaway_loops(db, user, llm: ScriptedLLM) -> None:
    for i in range(6):
        llm.script(assistant_msg(None, [tool_call("get_box", {"box": "nope"}, f"c{i}")]))
    llm.script(assistant_msg("never reached"))
    res = await agent.run(db, user, [], "loop", None)
    assert res == {"type": "message", "text": "I did what I could."}
    assert len(llm.calls) == 6
    assert len(llm.tool_replies) == 1


async def test_gps_context_reaches_tools(db, user, llm: ScriptedLLM) -> None:
    await _seed(db, user)
    llm.script(assistant_msg(None, [tool_call("set_box_gps", {"box": "7"})]), assistant_msg("saved"))
    await agent.run(db, user, [], "remember where I am for box 7", {"lat": 1.5, "lng": 2.5})
    box = agent_tools.resolve_box(db, user, "7")
    assert (box.gps_lat, box.gps_lng) == (1.5, 2.5)


async def test_empty_content_gets_default_text(db, user, llm: ScriptedLLM) -> None:
    llm.script(assistant_msg(None))
    assert (await agent.run(db, user, [], "x", None))["text"] == "Done."
