"""Turn failed production runs into eval-case stubs: production failure → new eval case.

    python evals/export.py [--since 7d|24h|all] [--out evals/inbox]

A run is "failed" when the user gave it a thumbs down, undid the action it led to, or it ended in an error
or hit the step cap. Each becomes one JSONL line in `evals/inbox/<stamp>-<set>.jsonl` with the model's own
answer prefilled as `expect` and a `_review` note: a human corrects the expectation and moves the line into
the set. Stubs never go into the sets automatically; a failed run is evidence that the model's answer is
wrong, so its answer cannot be the label.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INBOX = ROOT / "evals" / "inbox"
READ_TOOLS = {"search_items", "get_box"}


def reason(run: dict) -> str | None:
    if run.get("feedback") == -1:
        return "thumbs_down"
    if run.get("undone"):
        return "undone"
    if run.get("outcome") in ("error", "step_cap"):
        return str(run["outcome"])
    return None


def stub(run: dict) -> tuple[str, dict] | None:
    """(set name, case) for a run dict (`runs.to_dict` shape), or None when no set covers that kind."""
    why = reason(run)
    if why is None:
        return None
    source = {"run_id": run["id"], "reason": why, "model": run.get("model"), "prompt": run.get("prompt"),
              "created_at": run.get("created_at"), "note": run.get("feedback_note")}
    lang = "zh" if str(run.get("lang", "")).startswith("zh") else "en"
    cid = f"inbox-{run['id'][:8]}"
    if run["kind"] == "interpret":
        got = (run.get("output") or {}).get("parsed") or {}
        if got.get("intent") == "ingest":
            case = {"id": cid, "lang": lang, "text": run["input"],
                    "expect": {"intent": "ingest", "box_label": got.get("box_label"),
                               "items": [{"name": it.get("name"), "qty_text": it.get("qty_text")}
                                         for it in got.get("items") or []],
                               "location_text": got.get("location_text")},
                    "_source": source, "_review": "model output prefilled; correct every field before moving"}
            return "extraction", case
        case = {"id": cid, "lang": lang, "text": run["input"], "expect": {"intent": got.get("intent") or "query"},
                "_source": source, "_review": "model's intent prefilled; set the right one before moving"}
        return "routing", case
    if run["kind"] == "agent":
        calls = run.get("tool_calls") or []
        executed = [c["name"] for c in calls if c.get("name") not in READ_TOOLS]
        args = {c["name"]: c.get("args") for c in calls if c.get("name") not in READ_TOOLS}
        for a in (run.get("output") or {}).get("actions") or []:
            args.setdefault(a["tool"], a.get("args"))
        case = {"id": cid, "lang": lang, "text": run["input"],
                "expect": {"tools": executed, "confirm": run.get("confirm") or [], "args": args, "state": []},
                "_source": {**source, "reply": (run.get("output") or {}).get("text")},
                "_review": "what the agent did is prefilled; write what it should have done, add state checks"}
        return "tools", case
    case = {"id": cid, "lang": lang, "text": run["input"], "_source": source, "_output": run.get("output"),
            "_review": f"no golden set for kind {run['kind']!r} yet; kept for the record"}
    return run["kind"], case


def parse_since(text: str, now: datetime | None = None) -> datetime | None:
    if text == "all":
        return None
    m = re.fullmatch(r"(\d+)([dh])", text)
    if not m:
        raise ValueError("--since takes Nd, Nh or all")
    n, unit = int(m.group(1)), m.group(2)
    return (now or datetime.now(UTC)) - (timedelta(days=n) if unit == "d" else timedelta(hours=n))


def export(run_dicts: list[dict], out_dir: Path, stamp: str) -> dict[str, Path]:
    by_set: dict[str, list[dict]] = {}
    for run in run_dicts:
        s = stub(run)
        if s:
            by_set.setdefault(s[0], []).append(s[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for set_name, cases in by_set.items():
        path = out_dir / f"{stamp}-{set_name}.jsonl"
        path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
        written[set_name] = path
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="7d")
    ap.add_argument("--out", default=str(INBOX))
    args = ap.parse_args(argv)
    since = parse_since(args.since)

    from sqlalchemy import select

    from ..db import SessionLocal
    from ..models import AgentRun
    from ..services import runs

    q = select(AgentRun).where(runs.failed_filter())
    if since:
        q = q.where(AgentRun.created_at >= since)
    with SessionLocal() as db:
        rows = [runs.to_dict(r) for r in db.scalars(q.order_by(AgentRun.created_at))]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    written = export(rows, Path(args.out), stamp)
    print(f"{len(rows)} failed run(s) since {args.since}")
    for set_name, path in written.items():
        print(f"  {set_name}: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    if not written:
        print("  nothing to export")
    return 0


if __name__ == "__main__":
    sys.exit(main())
