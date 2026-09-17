"""Destructive tools: summaries, execution, snapshot-before-execute, single-step undo."""
import pytest
from sqlalchemy.orm import Session

from app.models import Media, UndoSnapshot, User
from app.services import agent_destructive, agent_tools, boxes_service


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("×2", "×3", "×5"),
        ("×2 双", "×1 双", "×3 双"),
        ("×2", "×1 盒", "×3 盒"),  # unit taken from whichever side has one
        ("若干", "×3", "若干"),  # unparsable → keep first
        ("", "×3", "×3"),
        (None, None, "若干"),
    ],
)
def test_merge_qty(a, b, expected) -> None:
    assert agent_destructive._merge_qty(a, b) == expected


async def _seed(db: Session, user: User):
    b6 = boxes_service.create_box(db, user, "6号", location_text="阁楼")
    b7 = boxes_service.create_box(db, user, "7号", location_text="车库")
    b8 = boxes_service.create_box(db, user, "8号")
    await boxes_service.add_items(db, b6, [{"name": "螺丝刀", "qty_text": "×2"}, {"name": "钳子", "qty_text": "×1"}])
    await boxes_service.add_items(db, b7, [{"name": "螺丝刀", "qty_text": "×3"}, {"name": "帐篷", "qty_text": "×1"}])
    await boxes_service.add_items(db, b8, [{"name": "锤子", "qty_text": "×1"}])
    b6.barcode = "BX-6"
    db.add(Media(user_id=user.id, box_id=b6.id, kind="photo", filename="p6.jpg"))
    db.add(Media(user_id=user.id, box_id=b6.id, kind="audio", filename="a6.webm"))
    db.commit()
    return b6, b7, b8


async def test_summaries_are_human_readable(db, user) -> None:
    await _seed(db, user)
    s = agent_destructive.summarize
    assert s(db, user, "delete_item", {"box": "6号", "item_name": "钳子"}) == "从「6号」删除物品「钳子」"
    assert s(db, user, "delete_box", {"box": "6号"}) == "删除整个箱子「6号」(含 2 类物品)"
    assert s(db, user, "delete_box", {"box": "99号"}) == "删除整个箱子「99号」"
    assert s(db, user, "empty_box", {"box": "7号"}) == "清空「7号」的 2 类物品(保留箱子本身)"
    assert s(db, user, "merge_boxes", {"source_boxes": ["6号", "8号"], "target_box": "7号"}) == (
        "把「6号、8号」的物品并入「7号」,并删除清空后的来源箱"
    )
    assert s(db, user, "something_else", {}) == "执行 something_else"


async def test_delete_item_loose_match(db, user) -> None:
    await _seed(db, user)
    res = agent_destructive.execute(db, user, "delete_item", {"box": "6号", "item_name": "钳"})
    assert res == {"ok": True, "summary": "已从「6号箱」删除「钳子」"}
    db.expire_all()
    assert [i.name for i in agent_tools.resolve_box(db, user, "6号").items] == ["螺丝刀"]


async def test_delete_item_errors(db, user) -> None:
    await _seed(db, user)
    assert agent_destructive.execute(db, user, "delete_item", {"box": "99号", "item_name": "x"})["ok"] is False
    res = agent_destructive.execute(db, user, "delete_item", {"box": "6号", "item_name": "望远镜"})
    assert res["ok"] is False and "望远镜" in res["error"]
    assert agent_destructive.execute(db, user, "nuke", {})["ok"] is False


async def test_delete_box_cascades(db, user) -> None:
    b6, _, _ = await _seed(db, user)
    res = agent_destructive.execute(db, user, "delete_box", {"box": "6号"})
    assert res["ok"] and "6号箱" in res["summary"]
    db.expire_all()
    assert agent_tools.resolve_box(db, user, "6号") is None
    assert db.query(Media).filter_by(box_id=b6.id).count() == 0


async def test_empty_box_keeps_box(db, user) -> None:
    await _seed(db, user)
    res = agent_destructive.execute(db, user, "empty_box", {"box": "7号"})
    assert res["summary"] == "已清空「7号箱」的 2 类物品"
    db.expire_all()
    box = agent_tools.resolve_box(db, user, "7号")
    assert box is not None and box.items == [] and box.location_text == "车库"


async def test_merge_boxes_sums_duplicates_moves_media_and_deletes_sources(db, user) -> None:
    b6, b7, b8 = await _seed(db, user)
    res = agent_destructive.execute(
        db, user, "merge_boxes", {"source_boxes": ["6号", "8号", "7号", "不存在"], "target_box": "7号"}
    )
    assert res == {"ok": True, "summary": "已把「6号箱、8号箱」并入「7号箱」"}
    db.expire_all()
    target = agent_tools.resolve_box(db, user, "7号")
    assert sorted((i.name, i.qty_text) for i in target.items) == sorted(
        [("帐篷", "×1"), ("锤子", "×1"), ("钳子", "×1"), ("螺丝刀", "×5")]
    )
    assert agent_tools.resolve_box(db, user, "6号") is None
    assert agent_tools.resolve_box(db, user, "8号") is None
    assert target.location_text == "车库"  # target wins
    assert sorted(m.filename for m in target.media) == ["a6.webm", "p6.jpg"]
    assert target.photo_url == "/media/p6.jpg"  # first merged photo becomes the cover


async def test_merge_into_missing_target(db, user) -> None:
    await _seed(db, user)
    assert agent_destructive.execute(db, user, "merge_boxes", {"source_boxes": ["6号"], "target_box": "99号"})["ok"] is False
    assert agent_tools.resolve_box(db, user, "6号") is not None


async def test_snapshot_is_taken_before_execution(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "merge_boxes", {"source_boxes": ["6号"], "target_box": "7号"})
    snap = db.get(UndoSnapshot, user.id)
    assert snap.label == "合并箱子"
    import json

    boxes = {b["label"]: b for b in json.loads(snap.payload)["boxes"]}
    assert set(boxes) == {"6号", "7号"}
    assert boxes["6号"]["barcode"] == "BX-6" and len(boxes["6号"]["media_ids"]) == 2
    assert [i["qty_text"] for i in boxes["7号"]["items"] if i["name"] == "螺丝刀"] == ["×3"]  # pre-merge value


async def test_undo_merge_restores_everything(db, user) -> None:
    b6, b7, _ = await _seed(db, user)
    media_ids = sorted(m.id for m in b6.media)
    agent_destructive.execute(db, user, "merge_boxes", {"source_boxes": ["6号"], "target_box": "7号"})
    db.expire_all()

    res = await agent_destructive.restore_last(db, user)
    assert res == {"ok": True, "summary": "已撤销「合并箱子」,数据已还原"}
    db.expire_all()

    six = agent_tools.resolve_box(db, user, "6号")
    seven = agent_tools.resolve_box(db, user, "7号")
    assert six.id == b6.id and seven.id == b7.id  # same ids: frontend links stay valid
    assert six.barcode == "BX-6" and six.location_text == "阁楼"
    assert sorted((i.name, i.qty_text) for i in six.items) == sorted([("钳子", "×1"), ("螺丝刀", "×2")])
    assert sorted((i.name, i.qty_text) for i in seven.items) == sorted([("帐篷", "×1"), ("螺丝刀", "×3")])
    assert sorted(m.id for m in six.media) == media_ids  # media rows moved back, not recreated
    assert all(i.embedding is not None for i in six.items)  # re-embedded on restore
    assert db.get(UndoSnapshot, user.id) is None  # single-step: consumed


async def test_undo_delete_box(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "delete_box", {"box": "8号"})
    assert agent_tools.resolve_box(db, user, "8号") is None
    assert (await agent_destructive.restore_last(db, user))["ok"]
    db.expire_all()
    assert [i.name for i in agent_tools.resolve_box(db, user, "8号").items] == ["锤子"]


async def test_undo_empty_box(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "empty_box", {"box": "7号"})
    db.expire_all()  # a fresh request session in production; drop the stale in-memory collection here
    assert (await agent_destructive.restore_last(db, user))["ok"]
    db.expire_all()
    assert len(agent_tools.resolve_box(db, user, "7号").items) == 2


async def test_only_last_operation_is_undoable(db, user) -> None:
    await _seed(db, user)
    agent_destructive.execute(db, user, "delete_box", {"box": "8号"})
    agent_destructive.execute(db, user, "delete_item", {"box": "6号", "item_name": "钳子"})
    db.expire_all()
    res = await agent_destructive.restore_last(db, user)
    assert res["summary"] == "已撤销「删除物品」,数据已还原"
    db.expire_all()
    assert agent_tools.resolve_box(db, user, "8号") is None  # first deletion stays gone
    assert len(agent_tools.resolve_box(db, user, "6号").items) == 2
    assert (await agent_destructive.restore_last(db, user))["ok"] is False
