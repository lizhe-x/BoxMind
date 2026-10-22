"""The fixture world for DB-backed evals: load `evals/fixtures/world.json` for a user, read box state back.

Item embeddings are computed once per process (the real embedding model) and reused, so loading the
world for forty users costs one embedding pass.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Item, User
from ..services import agent_tools, boxes_service, embeddings

WORLD = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "world.json"
_vectors: dict[str, list[float]] = {}


def read_world(path: Path = WORLD) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["boxes"]


async def load_world(db: Session, user: User, boxes: list[dict] | None = None) -> None:
    """Create every box and item of the world for `user` (which must have no boxes yet)."""
    boxes = boxes or read_world()
    names = sorted({name for b in boxes for name, _ in b["items"]} - _vectors.keys())
    if names:
        _vectors.update(zip(names, await embeddings.embed(names), strict=True))
    for b in boxes:
        box = boxes_service.create_box(db, user, b["label"], location_text=b.get("location"))
        if b.get("barcode"):
            box.barcode = b["barcode"]
        for name, qty in b["items"]:
            box.items.append(Item(name=name, qty_text=qty, embedding=_vectors[name]))
    db.commit()


def new_user(db: Session, device_id: str, lang: str) -> User:
    u = User(device_id=device_id, email=f"{device_id}@eval.invalid", lang=lang)
    db.add(u)
    db.commit()
    return u


def box_state(db: Session, user: User, ref: str) -> dict:
    """What a case's `state` assertions are checked against."""
    box = agent_tools.resolve_box(db, user, ref)
    if not box:
        return {"exists": False}
    return {
        "exists": True,
        "label": box.label,
        "name": box.name,
        "location": box.location_text,
        "barcode": box.barcode,
        "gps": box.gps_lat is not None,
        "items": {it.name: it.qty_text for it in box.items},
    }


def reset_database(engine) -> None:
    """Empty every table of the (dedicated) eval database."""
    from ..db import Base

    with engine.begin() as conn:
        names = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {names} CASCADE"))
