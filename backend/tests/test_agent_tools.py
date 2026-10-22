"""Directly-executed agent tools: the functions the model can call without confirmation."""
import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.services import agent_tools, boxes_service


async def _seed(db: Session, user: User) -> None:
    b5 = boxes_service.create_box(db, user, "5", location_text="garage")
    b7 = boxes_service.create_box(db, user, "7")
    liam = boxes_service.create_box(db, user, "Liam")
    await boxes_service.add_items(db, b5, [{"name": "headlamp", "qty_text": "×2"}, {"name": "trekking poles", "qty_text": "×2"}])
    await boxes_service.add_items(db, b7, [{"name": "tent", "qty_text": "×1"}])
    await boxes_service.add_items(db, liam, [{"name": "LEGO", "qty_text": "×3 boxes"}])
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
    assert agent_tools.resolve_box(db, user, "五号").label == "5"
    assert agent_tools.resolve_box(db, user, "box 5").label == "5"
    assert agent_tools.resolve_box(db, user, "Box 5").label == "5"  # also matches the default name
    assert agent_tools.resolve_box(db, user, "liam").name == "Liam"
    assert agent_tools.resolve_box(db, user, "") is None
    assert agent_tools.resolve_box(db, user, "nope") is None


async def test_dedup_name_appends_suffix(db: Session, user: User) -> None:
    await _seed(db, user)
    assert agent_tools.dedup_name(db, user, "Liam") == ("Liam2", True)
    boxes_service.create_box(db, user, "Liam2")
    db.commit()
    assert agent_tools.dedup_name(db, user, "Liam") == ("Liam3", True)
    assert agent_tools.dedup_name(db, user, "Noah") == ("Noah", False)


async def test_unknown_tool_is_reported_not_raised(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "launch_rocket", {}, {})
    assert res == {"ok": False, "error": "unknown tool launch_rocket"}


async def test_missing_box_is_a_tool_error(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "get_box", {"box": "99"}, {})
    assert res == {"ok": False, "error": "box “99” not found"}


async def test_missing_argument_is_a_tool_error(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "get_box", {}, {})
    assert res == {"ok": False, "error": "missing argument box"}


async def test_tool_errors_follow_user_language(db: Session, user: User) -> None:
    user.lang = "zh"
    res = await agent_tools.execute(db, user, "get_box", {"box": "99"}, {})
    assert res == {"ok": False, "error": "没找到箱子「99」"}


async def test_search_items_returns_exact_match_first(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "search_items", {"query": "tent"}, {})
    assert res["ok"] and res["results"][0]["item"] == "tent"
    assert res["results"][0]["box_label"] == "7" and res["results"][0]["box_name"] == "Box 7"
    assert res["results"][0]["similarity"] == 1.0
    assert len(res["results"]) == 4  # every item is returned, ranked


async def test_get_box_brief(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "get_box", {"box": "5"}, {})
    assert res["box"] == {
        "label": "5", "name": "Box 5", "location": "garage",
        "items": [{"name": "headlamp", "qty": "×2"}, {"name": "trekking poles", "qty": "×2"}],
    }


async def test_create_box_dedups_and_reports(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "create_box", {"name": "Liam", "location_text": "attic"}, {})
    assert res["renamed_to"] == "Liam2" and res["note"] == "name already taken, created as “Liam2”"
    assert agent_tools.resolve_box(db, user, "Liam2").location_text == "attic"
    res = await agent_tools.execute(db, user, "create_box", {"name": "box 9"}, {})
    assert res == {"ok": True, "created": "9", "renamed_to": None, "note": None}
    assert agent_tools.resolve_box(db, user, "9").name == "Box 9"


async def test_add_items_creates_box_when_missing(db: Session, user: User) -> None:
    res = await agent_tools.execute(
        db, user, "add_items", {"box": "3", "items": [{"name": "blanket"}, {"name": "", "qty_text": "×1"}]}, {}
    )
    assert res["created_box"] is True and res["added"] == ["blanket"]
    box = agent_tools.resolve_box(db, user, "3")
    assert [(i.name, i.qty_text) for i in box.items] == [("blanket", "some")]


async def test_add_items_rejects_empty_list(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "add_items", {"box": "3", "items": []}, {})
    assert res == {"ok": False, "error": "no items to add"}


async def test_set_location_and_barcode(db: Session, user: User) -> None:
    await _seed(db, user)
    assert (await agent_tools.execute(db, user, "set_box_location", {"box": "7", "location_text": "balcony"}, {}))["ok"]
    assert (await agent_tools.execute(db, user, "set_barcode", {"box": "7", "code": "BX-7"}, {}))["ok"]
    box = agent_tools.resolve_box(db, user, "7")
    assert (box.location_text, box.barcode) == ("balcony", "BX-7")


async def test_set_gps_requires_client_position(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "set_box_gps", {"box": "7"}, {"gps": None})
    assert res["ok"] is False and "GPS" in res["error"]
    res = await agent_tools.execute(db, user, "set_box_gps", {"box": "7"}, {"gps": {"lat": 31.2, "lng": 121.5}})
    assert res["gps_saved"] is True
    box = agent_tools.resolve_box(db, user, "7")
    assert (box.gps_lat, box.gps_lng) == (31.2, 121.5)


async def test_rename_box_keeps_it_resolvable_and_dedups(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "rename_box", {"box": "7", "new_name": "Camping"}, {})
    assert res["ok"] and res["renamed_from"] == "7"
    assert agent_tools.resolve_box(db, user, "7") is None
    assert agent_tools.resolve_box(db, user, "camping").label == "Camping"
    res = await agent_tools.execute(db, user, "rename_box", {"box": "5", "new_name": "Liam"}, {})
    assert res["box"] == "Liam2" and res["note"] == "name already taken, renamed to “Liam2”"


@pytest.mark.parametrize("ref", ["headlamp", "lamp"])  # exact, then substring fallback
async def test_update_item_matches_loosely(db: Session, user: User, ref: str) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "update_item", {"box": "5", "item_name": ref, "qty_text": "×5"}, {})
    assert res == {"ok": True, "box": "5", "item": "headlamp", "qty": "×5"}


async def test_update_item_rename(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "update_item", {"box": "5", "item_name": "headlamp", "new_name": "LED headlamp"}, {})
    assert res["item"] == "LED headlamp" and res["qty"] == "×2"
    res = await agent_tools.execute(db, user, "update_item", {"box": "5", "item_name": "binoculars"}, {})
    assert res == {"ok": False, "error": "no item “binoculars” in “5”"}


async def test_move_items_between_boxes(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(
        db, user, "move_items", {"from_box": "5", "to_box": "7", "item_names": ["headlamp", "nothing"]}, {}
    )
    assert res == {"ok": True, "from": "5", "to": "7", "moved": ["headlamp"]}
    db.expire_all()
    assert [i.name for i in agent_tools.resolve_box(db, user, "5").items] == ["trekking poles"]
    assert sorted(i.name for i in agent_tools.resolve_box(db, user, "7").items) == ["headlamp", "tent"]


async def test_move_items_nothing_found(db: Session, user: User) -> None:
    await _seed(db, user)
    res = await agent_tools.execute(db, user, "move_items", {"from_box": "5", "to_box": "7", "item_names": ["x"]}, {})
    assert res == {"ok": False, "error": "none of those items were found"}


async def test_undo_without_snapshot(db: Session, user: User) -> None:
    res = await agent_tools.execute(db, user, "undo_last", {}, {})
    assert res == {"ok": False, "error": "nothing to undo"}
