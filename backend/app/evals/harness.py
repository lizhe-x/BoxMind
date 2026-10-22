"""Run golden sets against the live model layer and record the numbers.

    python evals/run.py [routing] [extraction] [retrieval] [tools] [--provider claude_code|gateway] [--model sonnet]
                        [--concurrency 3] [--limit N] [--no-write]

routing / extraction call `llm.interpret`; retrieval calls the agent's `search_items` tool over the fixture
world; tools runs the whole agent loop (`agent.run`) on a fresh copy of the world per case and checks the
trace (tools executed, confirm gate, arguments) and the resulting box state. The DB-backed sets use a
dedicated `boxmind_eval` database (created on demand next to the configured one; override with
BOXMIND_EVAL_DATABASE_URL) and the real embedding model.

Each run writes `evals/results/<set>-<stamp>.json` (per-case got/expected, latency, tokens, prompt ids) and
appends one row to `evals/RESULTS.md`. Settings come from `backend/.env` like the server; `--provider` and
`--model` override them for the run only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from . import score

ROOT = Path(__file__).resolve().parents[3]
EVALS = ROOT / "evals"
RESULTS = EVALS / "results"
SETS = ("routing", "extraction", "retrieval", "tools")
INTERPRET_SETS = ("routing", "extraction")
GPS = {"lat": 40.7128, "lng": -74.0060}  # "where I am" for set_box_gps cases


def load_cases(set_name: str, path: Path | None = None) -> list[dict]:
    path = path or EVALS / f"{set_name}.jsonl"
    cases, errors, seen = [], [], set()
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}:{lineno}: {e}")
            continue
        for err in score.validate_case(set_name, case):
            errors.append(f"{path.name}:{lineno} ({case.get('id')}): {err}")
        if case.get("id") in seen:
            errors.append(f"{path.name}:{lineno}: duplicate id {case['id']}")
        seen.add(case.get("id"))
        cases.append(case)
    if errors:
        raise ValueError("\n".join(errors))
    return cases


# ── runners ─────────────────────────────────────────────────────────────
async def run_interpret(cases: list[dict], concurrency: int) -> list[dict]:
    """Call `llm.interpret` for every case; never raises, errors land in the row."""
    from ..services import trace
    from ..services.llm import llm

    sem = asyncio.Semaphore(max(1, concurrency))

    async def one(case: dict) -> dict:
        async with sem:
            t0 = time.monotonic()
            row: dict = {"id": case["id"], "got": None, "error": None, "ms": 0, "tokens": 0}
            with trace.collect() as traces:
                try:
                    parsed = await llm.interpret(case["text"], list(case.get("known_labels", [])), case.get("lang"))
                    row["got"] = {k: v for k, v in parsed.items() if not k.startswith("_")}
                except Exception as e:  # noqa: BLE001 — an eval must finish and report the failure
                    row["error"] = f"{type(e).__name__}: {e}"
            row["ms"] = int((time.monotonic() - t0) * 1000)
            if traces:
                row["tokens"] = traces[0].tokens
                row["prompt"] = traces[0].prompts.get("interpret")
                row["model"] = traces[0].model
            return row

    return list(await asyncio.gather(*(one(c) for c in cases)))


async def run_retrieval(cases: list[dict], stamp: str) -> list[dict]:
    """One user with the world; every query goes through the agent's `search_items` tool."""
    from ..db import SessionLocal
    from ..services import agent_tools
    from . import world

    db = SessionLocal()
    try:
        user = world.new_user(db, f"eval-retrieval-{stamp}", "en")
        await world.load_world(db, user)
        rows = []
        for case in cases:
            t0 = time.monotonic()
            row: dict = {"id": case["id"], "hits": [], "boxes": [], "error": None, "ms": 0}
            try:
                res = await agent_tools.execute(db, user, "search_items", {"query": case["text"]}, {})
                row["hits"] = [r["item"] for r in res.get("results", [])]
                row["boxes"] = [r["box_label"] for r in res.get("results", [])]
                row["similarity"] = [r["similarity"] for r in res.get("results", [])]
            except Exception as e:  # noqa: BLE001
                row["error"] = f"{type(e).__name__}: {e}"
            row["ms"] = int((time.monotonic() - t0) * 1000)
            rows.append(row)
        return rows
    finally:
        db.close()


async def run_tools(cases: list[dict], concurrency: int, stamp: str) -> list[dict]:
    """A fresh copy of the world per case (own user, own session), the full agent loop, then the state."""
    from ..db import SessionLocal
    from ..services import agent, trace
    from . import world

    sem = asyncio.Semaphore(max(1, concurrency))

    async def one(case: dict) -> dict:
        async with sem:
            db = SessionLocal()
            t0 = time.monotonic()
            row: dict = {"id": case["id"], "trace": None, "result": None, "state": {}, "error": None, "ms": 0}
            try:
                user = world.new_user(db, f"eval-tools-{case['id']}-{stamp}", case["lang"])
                await world.load_world(db, user)
                with trace.collect() as traces:
                    try:
                        row["result"] = await agent.run(db, user, [], case["text"], GPS)
                    except Exception as e:  # noqa: BLE001
                        row["error"] = f"{type(e).__name__}: {e}"
                        db.rollback()
                if traces:
                    row["trace"] = traces[0].to_dict()
                db.expire_all()
                for spec in case["expect"].get("state", []):
                    row["state"][spec["box"]] = world.box_state(db, user, spec["box"])
            finally:
                db.close()
            row["ms"] = int((time.monotonic() - t0) * 1000)
            return row

    return list(await asyncio.gather(*(one(c) for c in cases)))


def prepare_database() -> None:
    """Point the app at the dedicated eval database (creating it if needed) and reset it."""
    from sqlalchemy import create_engine, text

    from ..config import settings

    url = os.environ.get("BOXMIND_EVAL_DATABASE_URL") or settings.database_url.rsplit("/", 1)[0] + "/boxmind_eval"
    settings.database_url = url
    admin_url, dbname = url.rsplit("/", 1)[0] + "/postgres", url.rsplit("/", 1)[1]
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}).scalar():
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin.dispose()
    from .. import db as app_db
    from ..services import embeddings
    from . import world

    assert str(app_db.engine.url).endswith(dbname), "app.db was imported before the eval database was configured"
    app_db.init_db()
    world.reset_database(app_db.engine)
    embeddings.warmup()


# ── summary / output ────────────────────────────────────────────────────
def summarize(set_name: str, cases: list[dict], results: list[dict]) -> dict:
    fn = {"routing": score.score_routing, "extraction": score.score_extraction,
          "retrieval": score.score_retrieval, "tools": score.score_tools}[set_name]
    summary = fn(cases, results)
    summary["latency_ms_p50"] = _percentile([r["ms"] for r in results], 0.5)
    summary["latency_ms_p95"] = _percentile([r["ms"] for r in results], 0.95)
    summary["tokens_total"] = sum(r.get("tokens", 0) or (r.get("trace") or {}).get("tokens", 0) for r in results)
    summary["errors"] = sum(1 for r in results if r["error"])
    return summary


def _percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def run_label(set_name: str, results: list[dict]) -> tuple[str, str]:
    """(provider / model, prompt id) for the RESULTS.md row."""
    from ..config import settings

    if set_name == "retrieval":
        return f"embedding / {settings.embedding_model.rsplit('/', 1)[-1]}", "-"
    from ..services.llm import llm

    provider = f"{settings.llm_provider} / {llm.model_name}"
    if set_name in INTERPRET_SETS:
        return provider, "interpret " + next((r.get("prompt") for r in results if r.get("prompt")), "?")
    prompts = next(((r.get("trace") or {}).get("prompts") for r in results if r.get("trace")), {}) or {}
    return provider, "agent " + prompts.get("agent", "?")


def write_run(set_name: str, cases: list[dict], results: list[dict], summary: dict, stamp: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    model, prompt = run_label(set_name, results)
    out = RESULTS / f"{set_name}-{stamp}.json"
    payload = {
        "set": set_name, "stamp": stamp, "model": model, "prompt": prompt,
        "summary": {k: v for k, v in summary.items() if k != "failures"},
        "failures": summary["failures"],
        "cases": [{"case": c, **r} for c, r in zip(cases, results, strict=True)],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    row = (f"| {stamp[:10]} | {set_name} | {model} | {prompt} | {summary['n']} | "
           f"{score.summary_line(set_name, summary)} | p50 {summary['latency_ms_p50']} ms | "
           f"[json](results/{out.name}) |\n")
    md = EVALS / "RESULTS.md"
    md.write_text(md.read_text(encoding="utf-8").rstrip("\n") + "\n" + row, encoding="utf-8")
    return out


HEADLINE = {"routing": ("accuracy", "acc"), "extraction": ("exact_rate", "exact"),
            "retrieval": ("recall@8", "R@8"), "tools": ("pass_rate", "pass")}
MATRIX_START, MATRIX_END = "<!-- matrix:start -->", "<!-- matrix:end -->"


def build_matrix() -> str:
    """Latest run per (set, model, prompt) from results/, as one markdown table per set: rows = model,
    columns = prompt version, cell = headline metric and p50 latency. Regenerated after every run."""
    latest: dict[str, dict[tuple[str, str], dict]] = {}
    for path in sorted(RESULTS.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        latest.setdefault(d["set"], {})[(d["model"], d["prompt"])] = d  # sorted by stamp → last wins
    out = []
    for set_name in SETS:
        runs = latest.get(set_name)
        if not runs:
            continue
        key, label = HEADLINE[set_name]
        prompts = sorted({p for _, p in runs}, key=lambda p: p.split(" ")[1] if " " in p else p)
        models = sorted({m for m, _ in runs})
        out.append(f"**{set_name}** ({label}, p50 latency)\n")
        out.append("| model | " + " | ".join(prompts) + " |")
        out.append("|---|" + "---|" * len(prompts))
        for m in models:
            cells = []
            for pr in prompts:
                d = runs.get((m, pr))
                cells.append(f"{d['summary'][key]:.2f} · {d['summary']['latency_ms_p50']} ms" if d else "")
            out.append(f"| {m} | " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def write_matrix() -> None:
    md = EVALS / "RESULTS.md"
    text = md.read_text(encoding="utf-8")
    a, b = text.index(MATRIX_START) + len(MATRIX_START), text.index(MATRIX_END)
    md.write_text(text[:a] + "\n" + build_matrix() + text[b:], encoding="utf-8")


def print_summary(set_name: str, summary: dict) -> None:
    print(f"\n== {set_name}: n={summary['n']} errors={summary['errors']} "
          f"p50={summary['latency_ms_p50']}ms p95={summary['latency_ms_p95']}ms tokens={summary['tokens_total']}")
    print("   " + score.summary_line(set_name, summary))
    if set_name == "routing":
        print("   confusion (rows = expected):")
        for exp, row in summary["confusion"].items():
            print(f"     {exp:>10}: " + "  ".join(f"{k}={v}" for k, v in sorted(row.items())))
    for f in summary["failures"]:
        detail = f"expected {f['expect']} got {f['got']}" if "expect" in f else "; ".join(f["problems"])
        print(f"   ✗ {f['id']}  {f['text']}\n       {detail}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sets", nargs="*", metavar="SET", help=f"any of {', '.join(SETS)}; default: all four")
    ap.add_argument("--provider", choices=("claude_code", "gateway"))
    ap.add_argument("--model", help="model name for the chosen provider (claude: sonnet/haiku/opus; gateway: id)")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="only the first N cases of each set")
    ap.add_argument("--no-write", action="store_true", help="print only; do not touch results/ or RESULTS.md")
    ap.add_argument("--report", action="store_true", help="only rebuild the comparison matrix in RESULTS.md")
    args = ap.parse_args(argv)
    if args.report:
        write_matrix()
        print(build_matrix())
        return 0
    args.sets = args.sets or list(SETS)
    if unknown := [x for x in args.sets if x not in SETS]:
        ap.error(f"unknown set(s) {unknown}; choose from {', '.join(SETS)}")

    from ..config import settings
    if args.provider:
        settings.llm_provider = args.provider
    if args.model:
        if settings.llm_provider == "claude_code":
            settings.claude_model = args.model
        else:
            settings.llm_model = args.model
    if any(s not in INTERPRET_SETS for s in args.sets):
        prepare_database()
    from ..services import llm as llm_module
    llm_module.llm = llm_module._make()
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    print(f"provider={settings.llm_provider} model={llm_module.llm.model_name} "
          f"embedding={settings.embedding_model} concurrency={args.concurrency}")

    return asyncio.run(_run_sets(args, stamp))  # one loop for every set: provider locks bind to it once


async def _run_sets(args: argparse.Namespace, stamp: str) -> int:
    rc = 0
    for set_name in args.sets:
        cases = load_cases(set_name)
        if args.limit:
            cases = cases[:args.limit]
        if set_name in INTERPRET_SETS:
            results = await run_interpret(cases, args.concurrency)
        elif set_name == "retrieval":
            results = await run_retrieval(cases, stamp)
        else:
            results = await run_tools(cases, args.concurrency, stamp)
        summary = summarize(set_name, cases, results)
        print_summary(set_name, summary)
        if not args.no_write:
            print(f"   → {write_run(set_name, cases, results, summary, stamp).relative_to(ROOT)}")
        rc |= int(summary["errors"] > 0)
    if not args.no_write:
        write_matrix()
    return rc


if __name__ == "__main__":
    sys.exit(main())
