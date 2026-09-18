"""Destructive tools: summaries, execution, snapshot-before-execute, single-step undo."""
import json

import pytest
from sqlalchemy.orm import Session

from app.models import Media, UndoSnapshot, User
from app.services import agent_destructive, agent_tools, boxes_service


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("×2", "×3", "×5"),
        ("×2 pairs", "×1 pairs", "×3 pairs"),
        ("×2", "×1 box", "×3 box"),  # unit taken from whichever side has one
        ("some", "×3", "some"),  # unparsable → keep first
        ("", "×3", "×3"),
        (None, None, "some"),
    ],
)
def test_merge_qty(a, b, expected) -> None:
    assert agent_destructive._merge_qty(a, b) == expected


def test_merge_qty_fallback_follows_language() -> None:
    assert agent_destructive._merge_qty(None, None, "zh") == "若干"


async def _seed(db: Session, user: User):
    b6 = boxes_service.create_box(db, user, "6", location_text="attic")
    b7 = boxes_service.create_box(db, user, "7", location_text="garage")
    b8 = boxes_service.create_box(db, user, "8")
    await boxes_service.add_items(db, b6, [{"name": "screwdriver", "qty_text": "×2"}, {"name": "pliers", "qty_text": "×1"}])
    await boxes_service.add_items(db, b7, [{"name": "screwdriver", "qty_text": "×3"}, {"name": "tent", "qty_text": "×1"}])
    await boxes_service.add_items(db, b8, [{"name": "hammer", "qty_text": "×1"}])
    b6.barcode = "BX-6"
    db.add(Media(user_id=user.id, box_id=b6.id, kind="photo", filename="p6.jpg"))
    db.add(Media(user_id=user.id, box_id=b6.id, kind="audio", filename="a6.webm"))
    db.commit()
    return b6, b7, b8


async def test_summaries_are_human_readable(db, user) -> None:
    await _seed(db, user)
    s = agent_destructive.summarize
    assert s(db, user, "delete_item", {"box": "6", "item_name": "pliers"}) == "Delete “pliers” from “6”"
    assert s(db, user, "delete_box", {"box": "6"}) == "Delete box “6” (with 2 item types)"
    assert s(db, user, "delete_box", {"box": "99"}) == "Delete box “99”"
    assert s(db, user, "empty_box", {"box": "7"}) == "Empty “7” (2 item types), keep the box"
    assert s(db, user, "merge_boxes", {"source_boxes": ["6", "8"], "target_box": "7"}) == (
        "Move everything from “6, 8” into “7” and delete the emptied source boxes"
    )
    assert s(db, user, "something_else", {}) == "run something_else"


async def test_summaries_in_chinese(db, user) -> None:
    await _seed(db, user)
    user.lang = "zh"
    s = agent_destructive.summarize
    assert s(db, user, "delete_box", {"box": "6"}) == "删除整个箱子「6」(含 2 类物品)"
    assert s(db, user, "merge_boxes", {"source_boxes": ["6", "8"], "target_box": "7"}) == (
        "把「6、8」的物品并入「7」,并删除清空后的来源箱"
    )


async def test_delete_item_loose_match(db, user) -> None:
    await _seed(db, user)
    res = agent_destructive.execute(db, user, "delete_item", {"box": "6", "item_name": "plier"})
    assert res == {"ok": True, "summary": "Deleted “pliers” from “Box 6”"}
    db.expire_all()
    assert [i.name for i in agent_tools.resolve_box(db, user, "6").items] == ["screwdriver"]


async def test_delete_item_errors(db, user) -> None:
    await _seed(db, user)
    assert agent_destructive.execute(db, user, "delete_item", {"box": "99", "item_name": "x"}) == {
        "ok": False, "error": "box not found",
    }
    res = agent_destructive.execute(db, user, "delete_item", {"box": "6", "item_name": "binoculars"})
    assert res == {"ok": False, "error": "no “binoculars” in “6”"}
    assert agent_destructive.execute(db, user, "nuke", {}) == {"ok": False, "error": "unknown operation nuke"}


async def test_delete_box_cascades(db, user) -> None:
    b6, _, _ = await _seed(db, user)
    res = agent_destructive.execute(db, user, "delete_box", {"box": "6"})
    assert res == {"ok": True, "summary": "Deleted box “Box 6”"}
    db.expire_all()
    assert agent_tools.resolve_box(db, user, "6") is None
    assert db.query(Media).filter_by(box_id=b6.id).count() == 0


async def test_empty_box_keeps_box(db, user) -> None:
    await _seed(db, user)
    res = agent_destructive.execute(db, user, "empty_box", {"box": "7"})
    assert res["summary"] == "Emptied “Box 7” (2 item types)"
    db.expire_all()
    box = agent_tools.resolve_box(db, user, "7")
    assert box is not None and box.items == [] and box.location_text == "garage"


async def test_merge_boxes_sums_duplicates_moves_media_and_deletes_sources(db, user) -> None:
    b6, b7, b8 = await _seed(db, user)
    res = agent_destructive.execute(
        db, user, "merge_boxes", {"source_boxes": ["6", "8", "7", "nope"], "target_box": "7"}
    )
    assert res == {"ok": True, "summary": "Merged “Box 6, Box 8” into “Box 7”"}
    db.expire_all()
    target = agent_tools.resolve_box(db, user, "7")
    assert sorted((i.name, i.qty_text) for i in target.items) == [
        ("hammer", "×1"), ("pliers", "×1"), ("screwdriver", "×5"), ("tent", "×1"),
    ]
    assert agent_tools.resolve_box(db, user, "6") is None
    assert agent_tools.resolve_box(db, user, "8") is None
    assert target.location_text == "garage"  # target wins
    assert sorted(m.filename for m in target.media) == ["a6.webm", "p6.jpg"]
    assert target.photo_url == "/media/p6.jpg"  # first merged photo becomes the cover


async def test_merge_into_missing_target(db, user) -> None:
    await _seed(db, user)
    assert agent_destructive.execute(db, user, "merge_boxes", {"source_boxes": ["6"], "target_box": "99"}) == {
        "ok": False, "error": "target box not found",
    }
    assert agent_tools.resolve_box(db, user, "6") is not None


async def test_snapshot_is_taken_before_execution(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "merge_boxes", {"source_boxes": ["6"], "target_box": "7"})
    snap = db.get(UndoSnapshot, user.id)
    assert snap.label == "merge boxes"
    boxes = {b["label"]: b for b in json.loads(snap.payload)["boxes"]}
    assert set(boxes) == {"6", "7"}
    assert boxes["6"]["barcode"] == "BX-6" and len(boxes["6"]["media_ids"]) == 2
    assert [i["qty_text"] for i in boxes["7"]["items"] if i["name"] == "screwdriver"] == ["×3"]  # pre-merge value


async def test_undo_merge_restores_everything(db, user) -> None:
    b6, b7, _ = await _seed(db, user)
    media_ids = sorted(m.id for m in b6.media)
    agent_destructive.execute(db, user, "merge_boxes", {"source_boxes": ["6"], "target_box": "7"})
    db.expire_all()

    res = await agent_destructive.restore_last(db, user)
    assert res == {"ok": True, "summary": "Undid “merge boxes”, data restored"}
    db.expire_all()

    six = agent_tools.resolve_box(db, user, "6")
    seven = agent_tools.resolve_box(db, user, "7")
    assert six.id == b6.id and seven.id == b7.id  # same ids: frontend links stay valid
    assert six.barcode == "BX-6" and six.location_text == "attic"
    assert sorted((i.name, i.qty_text) for i in six.items) == [("pliers", "×1"), ("screwdriver", "×2")]
    assert sorted((i.name, i.qty_text) for i in seven.items) == [("screwdriver", "×3"), ("tent", "×1")]
    assert sorted(m.id for m in six.media) == media_ids  # media rows moved back, not recreated
    assert all(i.embedding is not None for i in six.items)  # re-embedded on restore
    assert db.get(UndoSnapshot, user.id) is None  # single-step: consumed


async def test_undo_delete_box(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "delete_box", {"box": "8"})
    assert agent_tools.resolve_box(db, user, "8") is None
    assert (await agent_destructive.restore_last(db, user))["ok"]
    db.expire_all()
    assert [i.name for i in agent_tools.resolve_box(db, user, "8").items] == ["hammer"]


async def test_undo_empty_box(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "empty_box", {"box": "7"})
    db.expire_all()  # a fresh request session in production; drop the stale in-memory collection here
    assert (await agent_destructive.restore_last(db, user))["ok"]
    db.expire_all()
    assert len(agent_tools.resolve_box(db, user, "7").items) == 2


async def test_only_last_operation_is_undoable(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "delete_box", {"box": "8"})
    agent_destructive.execute(db, user, "delete_item", {"box": "6", "item_name": "pliers"})
    db.expire_all()
    res = await agent_destructive.restore_last(db, user)
    assert res["summary"] == "Undid “delete item”, data restored"
    db.expire_all()
    assert agent_tools.resolve_box(db, user, "8") is None  # first deletion stays gone
    assert len(agent_tools.resolve_box(db, user, "6").items) == 2
    assert (await agent_destructive.restore_last(db, user)) == {"ok": False, "error": "nothing to undo"}
