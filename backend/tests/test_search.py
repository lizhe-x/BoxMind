"""Hybrid search: vector neighbours fused with trigram matches. Embeddings are the deterministic fakes from
conftest (identical strings match, nothing else does), so what the trigram leg adds is visible."""
from sqlalchemy.orm import Session

from app.models import User
from app.services import boxes_service, search


def test_rrf_sums_reciprocal_ranks() -> None:
    scores = search.rrf([["a", "b", "c"], ["c", "a"]], k=10)
    assert scores["a"] == 1 / 11 + 1 / 12
    assert scores["c"] == 1 / 13 + 1 / 11
    assert scores["b"] == 1 / 12
    assert sorted(scores, key=lambda x: -scores[x]) == ["a", "c", "b"]


async def _seed(db: Session, user: User) -> None:
    box = boxes_service.create_box(db, user, "5")
    await boxes_service.add_items(db, box, [{"name": "鼠标", "qty_text": "×1"}, {"name": "打印机", "qty_text": "×1"},
                                            {"name": "tape measure", "qty_text": "×1"}])
    box2 = boxes_service.create_box(db, user, "3")
    await boxes_service.add_items(db, box2, [{"name": "drill", "qty_text": "×1"}])
    db.commit()


async def test_vector_mode_only_finds_identical_strings(db: Session, user: User) -> None:
    await _seed(db, user)
    hits = await search.search_items(db, user, "鼠标", mode="vector")
    assert hits[0]["item"] == "鼠标" and hits[0]["similarity"] == 1.0
    hits = await search.search_items(db, user, "鼠标在哪", mode="vector")
    assert hits[0]["similarity"] < 0.9  # fake vectors: a different string is unrelated, whatever ranks first


async def test_hybrid_mode_adds_trigram_matches(db: Session, user: User) -> None:
    await _seed(db, user)
    hits = await search.search_items(db, user, "鼠标在哪", mode="hybrid")
    assert hits[0]["item"] == "鼠标" and hits[0]["box_label"] == "5"
    hits = await search.search_items(db, user, "tape measur", mode="hybrid")
    assert hits[0]["item"] == "tape measure"
    assert set(hits[0]) == {"item", "qty", "box_label", "box_name", "similarity", "score"}


async def test_hybrid_ranks_an_item_seen_by_both_signals_first(db: Session, user: User) -> None:
    await _seed(db, user)
    hits = await search.search_items(db, user, "drill", mode="hybrid")
    assert hits[0]["item"] == "drill" and hits[0]["similarity"] == 1.0
    assert hits[0]["score"] > hits[1]["score"]


async def test_search_respects_limit_and_user(db: Session, user: User) -> None:
    await _seed(db, user)
    assert len(await search.search_items(db, user, "x", limit=2)) == 2
    other = User(device_id="other-device", email="o@example.com")
    db.add(other)
    db.commit()
    assert await search.search_items(db, other, "drill") == []
