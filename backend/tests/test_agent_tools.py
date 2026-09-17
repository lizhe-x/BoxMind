"""Directly-executed agent tools: the functions the model can call without confirmation."""
import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.services import agent_tools, boxes_service


async def _seed(db: Session, user: User) -> None:
    b5 = boxes_service.create_box(db, user, "5号", location_text="车库")
    b7 = boxes_service.create_box(db, user, "7号")
    liam = boxes_service.create_box(db, user, "Liam")
    await boxes_service.add_items(db, b5, [{"name": "头灯", "qty_text": "×2"}, {"name": "登山杖", "qty_text": "×2 根"}])
    await boxes_service.add_items(db, b7, [{"name": "帐篷", "qty_text": "×1"}])
    await boxes_service.add_items(db, liam, [{"name": "乐高", "qty_text": "×3 盒"}])
    db.commit()


def test_tool_schema_is_valid_openai_function_calling() -> None:
    names = [t["function"]["name"] for t in agent_tools.TOOLS]
    assert len(names) == len(set(names)) == 15
    for t in agent_tools.TOOLS:
        fn = t["function"]
        assert t["type"] == "function" and fn["description"]
        params = fn["parameters"]
        assert params["type"] == "object"
        assert set(params["required"]) <= set(params["properties"])
    assert agent_tools.DESTRUCTIVE <= set(names)
    assert agent_tools.DESTRUCTIVE.isdisjoint(agent_tools._EXEC)  # destructive tools never auto-execute
    assert set(agent_tools._EXEC) | agent_tools.DESTRUCTIVE == set(names)


async def test_resolve_box_by_label_or_name(db: Session, user: User) -> None:
    await _seed(db, user)
    assert agent_tools.resolve_box(db, user, "五号").label == "5号"
    assert agent_tools.resolve_box(db, user, "5号箱").label == "5号"
    assert agent_tools.resolve_box(db, user, "liam").name == "Liam"
    assert agent_tools.resolve_box(db, user, "") is None
    assert agent_tools.resolve_box(db, user, "不存在") is None


async def test_dedup_name_appends_suffix(db: Session, user: User) -> None:
    await _seed(db, user)
    assert agent_tools.dedup_name(db, user, "Liam") == ("Liam2", True)
    boxes_service.create_box(db, user, "Liam2")
    db.commit()
    assert agent_tools.dedup_name(db, user, "Liam") == ("Liam3", True)
    assert agent_tools.dedup_name(db, user, "Noah") == ("Noah", False)


async def test_unknown_tool_is_reported_not_raised(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "launch_rocket", {}, {})
    assert res["ok"] is False and "launch_rocket" in res["error"]


async def test_missing_box_is_a_tool_error(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "get_box", {"box": "99号"}, {})
    assert res == {"ok": False, "error": "没找到箱子「99号」"}


async def test_search_items_returns_exact_match_first(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "search_items", {"query": "帐篷"}, {})
    assert res["ok"] and res["results"][0]["物品"] == "帐篷"
    assert res["results"][0]["箱子编号"] == "7号"
    assert res["results"][0]["相似度"] == 1.0
    assert len(res["results"]) == 4  # every item is returned, ranked


async def test_get_box_brief(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "get_box", {"box": "5号"}, {})
    assert res["box"] == {
        "编号": "5号", "名字": "5号箱", "位置": "车库",
        "物品": [{"名称": "头灯", "数量": "×2"}, {"名称": "登山杖", "数量": "×2 根"}],
    }


async def test_create_box_dedups_and_reports(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "create_box", {"name": "Liam", "location_text": "阁楼"}, {})
    assert res["renamed_to"] == "Liam2" and "重复" in res["note"]
    assert agent_tools.resolve_box(db, user, "Liam2").location_text == "阁楼"
    res = await agent_tools.execute(db, user, "create_box", {"name": "9号"}, {})
    assert res == {"ok": True, "created": "9号", "renamed_to": None, "note": None}


async def test_add_items_creates_box_when_missing(db: Session, user: User) -> None:
    res = await agent_tools.execute(
        db, user, "add_items", {"box": "3号", "items": [{"name": "毛毯"}, {"name": "", "qty_text": "×1"}]}, {}
    )
    assert res["created_box"] is True and res["added"] == ["毛毯"]
    box = agent_tools.resolve_box(db, user, "3号")
    assert [(i.name, i.qty_text) for i in box.items] == [("毛毯", "若干")]


async def test_add_items_rejects_empty_list(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "add_items", {"box": "3号", "items": []}, {})
    assert res == {"ok": False, "error": "没有要添加的物品"}


async def test_set_location_and_barcode(db: Session, user: User) -> None:
    await _seed(db, user)
    assert (await agent_tools.execute(db, user, "set_box_location", {"box": "7号", "location_text": "阳台"}, {}))["ok"]
    assert (await agent_tools.execute(db, user, "set_barcode", {"box": "7号", "code": "BX-7"}, {}))["ok"]
    box = agent_tools.resolve_box(db, user, "7号")
    assert (box.location_text, box.barcode) == ("阳台", "BX-7")


async def test_set_gps_requires_client_position(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "set_box_gps", {"box": "7号"}, {"gps": None})
    assert res["ok"] is False
    res = await agent_tools.execute(db, user, "set_box_gps", {"box": "7号"}, {"gps": {"lat": 31.2, "lng": 121.5}})
    assert res["gps_saved"] is True
    box = agent_tools.resolve_box(db, user, "7号")
    assert (box.gps_lat, box.gps_lng) == (31.2, 121.5)


async def test_rename_box_keeps_it_resolvable_and_dedups(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "rename_box", {"box": "7号", "new_name": "露营箱"}, {})
    assert res["ok"] and res["renamed_from"] == "7号"
    assert agent_tools.resolve_box(db, user, "7号") is None
    assert agent_tools.resolve_box(db, user, "露营箱").label == "露营箱"
    res = await agent_tools.execute(db, user, "rename_box", {"box": "5号", "new_name": "Liam"}, {})
    assert res["box"] == "Liam2" and res["note"]


@pytest.mark.parametrize("ref", ["头灯", "灯"])  # exact, then substring fallback
async def test_update_item_matches_loosely(db: Session, user: User, ref: str) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "update_item", {"box": "5号", "item_name": ref, "qty_text": "×5"}, {})
    assert res == {"ok": True, "box": "5号", "item": "头灯", "qty": "×5"}


async def test_update_item_rename(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "update_item", {"box": "5号", "item_name": "头灯", "new_name": "LED 头灯"}, {})
    assert res["item"] == "LED 头灯" and res["qty"] == "×2"
    res = await agent_tools.execute(db, user, "update_item", {"box": "5号", "item_name": "望远镜"}, {})
    assert res["ok"] is False and "望远镜" in res["error"]


async def test_move_items_between_boxes(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(
        db, user, "move_items", {"from_box": "5号", "to_box": "7号", "item_names": ["头灯", "不存在的"]}, {}
    )
    assert res == {"ok": True, "from": "5号", "to": "7号", "moved": ["头灯"]}
    db.expire_all()
    assert [i.name for i in agent_tools.resolve_box(db, user, "5号").items] == ["登山杖"]
    assert sorted(i.name for i in agent_tools.resolve_box(db, user, "7号").items) == ["头灯", "帐篷"]


async def test_move_items_nothing_found(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "move_items", {"from_box": "5号", "to_box": "7号", "item_names": ["x"]}, {})
    assert res == {"ok": False, "error": "没找到要移动的物品"}


async def test_undo_without_snapshot(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "undo_last", {}, {})
    assert res == {"ok": False, "error": "没有可撤销的操作"}
