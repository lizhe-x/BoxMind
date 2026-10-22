"""Box/item service layer: label lookup, next label, palette, upsert semantics, language of defaults."""
from sqlalchemy.orm import Session

from app.models import User
from app.normalize import KRAFT_PALETTE
from app.services import boxes_service


def test_create_and_find_by_any_label_variant(db: Session, user: User) -> None:
    box = boxes_service.create_box(db, user, "Box 3", location_text="garage")
    db.commit()
    assert (box.label, box.name, box.norm_label) == ("3", "Box 3", "#3")  # user.lang defaults to en
    for variant in ("3", "三号", "3号箱", "box3", "#3"):
        assert boxes_service.find_box_by_label(db, user.id, variant).id == box.id
    assert boxes_service.find_box_by_label(db, user.id, "4") is None


def test_defaults_follow_user_language(db: Session, user: User) -> None:
    user.lang = "zh"
    db.commit()
    box = boxes_service.create_box(db, user, "Box 3")
    db.commit()
    assert (box.label, box.name) == ("3号", "3号箱")
    assert boxes_service.find_box_by_label(db, user.id, "3").id == box.id  # matching stays language-neutral


def test_find_is_scoped_to_user(db: Session, user: User) -> None:
    other = User(device_id="other-device-0002")
    db.add(other)
    db.commit()
    boxes_service.create_box(db, other, "1")
    db.commit()
    assert boxes_service.find_box_by_label(db, user.id, "1") is None


def test_next_num_label_skips_text_labels_and_follows_language(db: Session, user: User) -> None:
    assert boxes_service.next_num_label(db, user) == "1"
    boxes_service.create_box(db, user, "2")
    boxes_service.create_box(db, user, "Liam")
    boxes_service.create_box(db, user, "7号")
    db.commit()
    assert boxes_service.next_num_label(db, user) == "8"
    user.lang = "zh"
    assert boxes_service.next_num_label(db, user) == "8号"


def test_palette_cycles_by_box_count(db: Session, user: User) -> None:
    colours = []
    for i in range(len(KRAFT_PALETTE) + 1):
        b = boxes_service.create_box(db, user, f"{i + 1}")
        colours.append((b.color_a, b.color_b))
    db.commit()
    assert colours[: len(KRAFT_PALETTE)] == KRAFT_PALETTE
    assert colours[-1] == KRAFT_PALETTE[0]


async def test_add_items_upserts_by_name_and_embeds(db: Session, user: User) -> None:
    box = boxes_service.create_box(db, user, "1")
    await boxes_service.add_items(db, box, [{"name": "tent", "qty_text": "×1"}, {"name": "headlamp"}])
    db.commit()
    assert sorted((it.name, it.qty_text) for it in box.items) == [("headlamp", "×1"), ("tent", "×1")]
    assert all(it.embedding is not None and len(it.embedding) == 384 for it in box.items)

    await boxes_service.add_items(db, box, [{"name": "tent", "qty_text": "×3"}])
    db.commit()
    db.refresh(box)
    assert len(box.items) == 2  # no duplicate row
    assert next(it for it in box.items if it.name == "tent").qty_text == "×3"


async def test_add_items_empty_is_noop(db: Session, user: User) -> None:
    box = boxes_service.create_box(db, user, "1")
    await boxes_service.add_items(db, box, [])
    db.commit()
    assert box.items == []


def test_usage_log_counts_without_charging(db: Session, user: User) -> None:
    before = user.credit_balance
    boxes_service.log_usage(db, user, "query")
    boxes_service.log_usage(db, user, "ingest", tokens=42)
    db.commit()
    assert boxes_service.usage_count(db, user.id) == 2
    assert user.credit_balance == before
