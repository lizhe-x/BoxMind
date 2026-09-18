"""app.maintenance.relabel: re-localise Chinese-era defaults without touching user-written text."""
from sqlalchemy.orm import Session

from app.maintenance.relabel import relabel
from app.models import Box, UndoSnapshot, User
from app.services import agent_destructive, agent_tools, boxes_service


async def _seed_chinese_account(db: Session, user: User):
    user.lang = "zh"
    db.commit()
    b5 = boxes_service.create_box(db, user, "5号", location_text="车库")  # default name 5号箱
    custom = boxes_service.create_box(db, user, "7号", name="露营装备")  # user-named
    liam = boxes_service.create_box(db, user, "Liam")  # text label
    await boxes_service.add_items(db, b5, [{"name": "头灯", "qty_text": "若干"}, {"name": "帐篷", "qty_text": "×1"}])
    await boxes_service.add_items(db, liam, [{"name": "乐高", "qty_text": "×3 盒"}])
    db.commit()
    agent_destructive.execute(db, user, "delete_item", {"box": "Liam", "item_name": "乐高"})  # leaves a snapshot
    return b5, custom, liam


async def test_dry_run_reports_but_changes_nothing(db, user) -> None:
    b5, custom, liam = await _seed_chinese_account(db, user)
    rep = relabel(db, "en", apply=False)
    assert (rep.users, rep.boxes_relabelled, rep.boxes_renamed, rep.items_requantified, rep.snapshots_dropped) == (1, 2, 1, 1, 1)
    assert any("'5号' → '5'" in c for c in rep.changes)
    db.expire_all()
    assert user.lang == "zh" and db.get(Box, b5.id).label == "5号" and db.get(UndoSnapshot, user.id) is not None


async def test_apply_relabels_defaults_and_keeps_user_text(db, user) -> None:
    b5, custom, liam = await _seed_chinese_account(db, user)
    rep = relabel(db, "en", apply=True)
    db.expire_all()

    assert user.lang == "en"
    b5 = db.get(Box, b5.id)
    assert (b5.label, b5.name, b5.location_text) == ("5", "Box 5", "车库")  # generated → English, typed → kept
    custom = db.get(Box, custom.id)
    assert (custom.label, custom.name) == ("7", "露营装备")  # label localised, custom name untouched
    liam = db.get(Box, liam.id)
    assert (liam.label, liam.name) == ("Liam", "Liam")
    qtys = {it.name: it.qty_text for it in b5.items}
    assert qtys == {"头灯": "some", "帐篷": "×1"}  # only the placeholder changes, item names never do
    assert db.get(UndoSnapshot, user.id) is None
    assert "undo snapshots dropped 1" in rep.summary()

    # matching still works from either language and the account now produces English defaults
    assert agent_tools.resolve_box(db, user, "五号").id == b5.id
    assert boxes_service.next_num_label(db, user) == "8"

    # idempotent
    rep2 = relabel(db, "en", apply=True)
    assert (rep2.users, rep2.boxes_relabelled, rep2.boxes_renamed, rep2.items_requantified) == (0, 0, 0, 0)


async def test_truncated_text_labels_are_restored_from_the_name(db, user) -> None:
    truncated = boxes_service.create_box(db, user, "BX-INTEG-9")
    truncated.label = "BX-I"  # what the old 4-char display rule stored
    renamed = boxes_service.create_box(db, user, "Liam", name="Liam's toys")  # custom name, not a truncation
    db.commit()
    rep = relabel(db, "en", apply=True)
    db.expire_all()
    assert db.get(Box, truncated.id).label == "BX-INTEG-9"
    assert db.get(Box, renamed.id).label == "Liam"  # name shares the prefix but not the matching key → untouched
    assert rep.boxes_relabelled == 1


async def test_round_trip_back_to_chinese(db, user) -> None:
    b5, _, _ = await _seed_chinese_account(db, user)
    relabel(db, "en", apply=True)
    relabel(db, "zh", apply=True)
    db.expire_all()
    b5 = db.get(Box, b5.id)
    assert (b5.label, b5.name) == ("5号", "5号箱")
    assert {it.qty_text for it in b5.items} == {"若干", "×1"}
