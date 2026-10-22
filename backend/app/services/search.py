"""Item search: pgvector cosine neighbours fused with pg_trgm trigram matches by reciprocal rank fusion.

Why two signals: the embedding index is good at meaning ("warm clothes" → 羽绒服) and the trigram index is
good at spelling (a query that contains the stored name, a typo, a partial), and each one misses what the
other catches. RRF needs no score calibration between them: each candidate scores Σ 1/(k + rank) over the
rankings it appears in. `settings.search_mode` picks "hybrid" (default) or "vector" (the old behaviour);
the eval harness runs the retrieval set under both.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Box, Item, User
from . import embeddings

CANDIDATES = 20       # per signal, before fusion
RRF_K = 60
TRIGRAM_MIN = 0.3     # pg_trgm similarity floor; below this a match is noise


def rrf(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, 1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return scores


async def search_items(db: Session, user: User, query: str, limit: int = 8, mode: str | None = None) -> list[dict]:
    """Top `limit` items for the query, each `{item, qty, box_label, box_name, similarity, score}`.
    `similarity` is the cosine similarity when the vector index saw the item, else None."""
    mode = mode or settings.search_mode
    base = (select(Item.id, Item.name, Item.qty_text, Box.label, Box.name.label("box_name"))
            .join(Box, Item.box_id == Box.id).where(Box.user_id == user.id))

    qvec = (await embeddings.embed([query], query=True))[0]
    vec_rows = db.execute(
        base.add_columns(Item.embedding.cosine_distance(qvec).label("d"))
        .where(Item.embedding.is_not(None)).order_by("d").limit(CANDIDATES)
    ).all()
    hits = {r.id: {"item": r.name, "qty": r.qty_text, "box_label": r.label, "box_name": r.box_name,
                   "similarity": round(1 - r.d, 2)} for r in vec_rows}
    rankings = [[r.id for r in vec_rows]]

    if mode == "hybrid":
        sim = func.similarity(Item.name, query)
        tri_rows = db.execute(
            base.add_columns(sim.label("s")).where(sim > TRIGRAM_MIN).order_by(sim.desc()).limit(CANDIDATES)
        ).all()
        for r in tri_rows:
            hits.setdefault(r.id, {"item": r.name, "qty": r.qty_text, "box_label": r.label, "box_name": r.box_name,
                                   "similarity": None})
        rankings.append([r.id for r in tri_rows])

    scores = rrf(rankings)
    out = []
    for item_id in sorted(hits, key=lambda i: -scores[i])[:limit]:
        out.append({**hits[item_id], "score": round(scores[item_id], 4)})
    return out
