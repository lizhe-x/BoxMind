"""Recompute every item embedding with the configured model (after switching BOXMIND_EMBEDDING_MODEL / _DIM).

    python -m app.maintenance.reembed            # dry run: counts, current column width vs configured
    python -m app.maintenance.reembed --apply    # widen the column if needed, re-embed everything

The vector column is retyped to the configured dimension (existing vectors are dropped first, they belong to
the old model anyway), then items are embedded in batches with the new model. Idempotent: re-running after
success just re-embeds.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select, text

from ..config import settings
from ..db import SessionLocal, engine
from ..models import Item
from ..services import embeddings

BATCH = 64


def column_dim() -> int | None:
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'items'::regclass AND attname = 'embedding'"
        )).scalar()
    return int(row) if row and row > 0 else None


async def reembed(apply: bool) -> None:
    current = column_dim()
    with SessionLocal() as db:
        total = db.scalar(select(func.count(Item.id))) or 0
    print(f"model={settings.embedding_model} dim={settings.embedding_dim} column_dim={current} items={total}")
    if not apply:
        print("dry run; add --apply to write")
        return
    if current != settings.embedding_dim:
        with engine.begin() as conn:
            conn.execute(text("UPDATE items SET embedding = NULL"))
            conn.execute(text(f"ALTER TABLE items ALTER COLUMN embedding TYPE vector({settings.embedding_dim})"))
        print(f"column retyped to vector({settings.embedding_dim})")
    embeddings.warmup()
    done = 0
    with SessionLocal() as db:
        ids = db.scalars(select(Item.id).order_by(Item.created_at)).all()
        for start in range(0, len(ids), BATCH):
            items = db.scalars(select(Item).where(Item.id.in_(ids[start:start + BATCH]))).all()
            vectors = await embeddings.embed([it.name for it in items])
            for it, vec in zip(items, vectors, strict=True):
                it.embedding = vec
            db.commit()
            done += len(items)
            print(f"  {done}/{len(ids)}")
    print("done")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    asyncio.run(reembed(args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
