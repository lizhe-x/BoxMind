"""Re-localise existing data after a language change.

Data created before the UI became English-by-default carries Chinese defaults:
numeric boxes are labelled "5号" and named "5号箱", unknown quantities read "若干".
This command switches every account to a target language and rewrites those
generated defaults to that language. Anything the user typed themselves (custom
box names, item names, locations) is left alone.

    python -m app.maintenance.relabel --lang en            # dry run, prints the plan
    python -m app.maintenance.relabel --lang en --apply    # write it

Undo snapshots are dropped because they hold the old labels.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..i18n import LANGS, norm_lang, tr
from ..models import Box, Item, UndoSnapshot, User
from ..normalize import extract_number, normalize_label

# every default the app has ever generated for a numeric box, in any language
_DEFAULT_NAME_KEYS = ("name_num",)
_QTY_SOME = {tr(lang, "qty_some") for lang in LANGS}


def _default_names(n: int) -> set[str]:
    return {tr(lang, key, n=n) for lang in LANGS for key in _DEFAULT_NAME_KEYS}


@dataclass
class Report:
    users: int = 0
    boxes_relabelled: int = 0
    boxes_renamed: int = 0
    items_requantified: int = 0
    snapshots_dropped: int = 0
    changes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"users → {self.users}, box labels {self.boxes_relabelled}, box names {self.boxes_renamed}, "
            f"item quantities {self.items_requantified}, undo snapshots dropped {self.snapshots_dropped}"
        )


def relabel(db: Session, target_lang: str, apply: bool = False) -> Report:
    lang = norm_lang(target_lang)
    rep = Report()
    some = tr(lang, "qty_some")

    for user in db.scalars(select(User)).all():
        if norm_lang(user.lang) != lang or user.lang != lang:
            rep.users += 1
            rep.changes.append(f"user {user.email or user.device_id}: lang {user.lang!r} → {lang!r}")
            if apply:
                user.lang = lang

    for box in db.scalars(select(Box)).all():
        n = extract_number(box.label)
        if n is None:
            # text labels are the user's own words, except where the old display rule truncated them
            # ("BX-INTEG-9" was stored as label "BX-I"); restore from the name when both share the matching key
            if (
                box.name != box.label
                and box.name.startswith(box.label)
                and normalize_label(box.name)[0] == box.norm_label
            ):
                rep.boxes_relabelled += 1
                rep.changes.append(f"box {box.id[:8]}: label {box.label!r} → {box.name!r} (untruncated)")
                if apply:
                    box.label = box.name
            continue
        new_label = tr(lang, "label_num", n=n)
        new_name = tr(lang, "name_num", n=n)
        if box.label != new_label:
            rep.boxes_relabelled += 1
            rep.changes.append(f"box {box.id[:8]}: label {box.label!r} → {new_label!r}")
            if apply:
                box.label = new_label
        if box.name in _default_names(n) and box.name != new_name:
            rep.boxes_renamed += 1
            rep.changes.append(f"box {box.id[:8]}: name {box.name!r} → {new_name!r}")
            if apply:
                box.name = new_name

    for item in db.scalars(select(Item).where(Item.qty_text.in_(list(_QTY_SOME)))).all():
        if item.qty_text != some:
            rep.items_requantified += 1
            if apply:
                item.qty_text = some

    rep.snapshots_dropped = len(db.scalars(select(UndoSnapshot.user_id)).all())
    if apply:
        db.execute(delete(UndoSnapshot))
        db.commit()
    return rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True, choices=LANGS, help="target UI language for every account")
    ap.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    args = ap.parse_args()

    from ..db import SessionLocal

    with SessionLocal() as db:
        rep = relabel(db, args.lang, apply=args.apply)
    for line in rep.changes:
        print(line)
    print(("APPLIED: " if args.apply else "DRY RUN: ") + rep.summary())


if __name__ == "__main__":
    main()
