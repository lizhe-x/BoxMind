"""Run golden sets against the live model layer and record the numbers.

    python evals/run.py routing extraction [--provider claude_code|gateway] [--model sonnet] [--concurrency 3]
                                           [--limit N] [--no-write]

Each run writes `evals/results/<set>-<stamp>.json` (per-case got/expected, latency, tokens, prompt ids) and
appends one row to `evals/RESULTS.md`. Settings come from `backend/.env` like the server; `--provider` and
`--model` override them for the run only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from . import score

ROOT = Path(__file__).resolve().parents[3]
EVALS = ROOT / "evals"
RESULTS = EVALS / "results"
SETS = ("routing", "extraction")


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


async def run_cases(cases: list[dict], concurrency: int) -> list[dict]:
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


def summarize(set_name: str, cases: list[dict], results: list[dict]) -> dict:
    fn = score.score_routing if set_name == "routing" else score.score_extraction
    summary = fn(cases, results)
    summary["latency_ms_p50"] = _percentile([r["ms"] for r in results], 0.5)
    summary["latency_ms_p95"] = _percentile([r["ms"] for r in results], 0.95)
    summary["tokens_total"] = sum(r.get("tokens", 0) for r in results)
    summary["errors"] = sum(1 for r in results if r["error"])
    return summary


def _percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def write_run(set_name: str, provider: str, model: str, cases: list[dict], results: list[dict],
              summary: dict, stamp: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    prompt = next((r.get("prompt") for r in results if r.get("prompt")), "?")
    out = RESULTS / f"{set_name}-{stamp}.json"
    payload = {
        "set": set_name, "stamp": stamp, "provider": provider, "model": model, "prompt": {"interpret": prompt},
        "summary": {k: v for k, v in summary.items() if k != "failures"},
        "failures": summary["failures"],
        "cases": [{"case": c, **r} for c, r in zip(cases, results, strict=True)],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    row = (f"| {stamp[:10]} | {set_name} | {provider} / {model} | interpret@{prompt} | {summary['n']} | "
           f"{score.summary_line(set_name, summary)} | p50 {summary['latency_ms_p50']} ms | "
           f"[json](results/{out.name}) |\n")
    md = EVALS / "RESULTS.md"
    md.write_text(md.read_text(encoding="utf-8").rstrip("\n") + "\n" + row, encoding="utf-8")
    return out


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
    ap.add_argument("sets", nargs="*", default=list(SETS), choices=SETS)
    ap.add_argument("--provider", choices=("claude_code", "gateway"))
    ap.add_argument("--model", help="model name for the chosen provider (claude: sonnet/haiku/opus; gateway: id)")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="only the first N cases of each set")
    ap.add_argument("--no-write", action="store_true", help="print only; do not touch results/ or RESULTS.md")
    args = ap.parse_args(argv)

    from ..config import settings
    if args.provider:
        settings.llm_provider = args.provider
    if args.model:
        if settings.llm_provider == "claude_code":
            settings.claude_model = args.model
        else:
            settings.llm_model = args.model
    from ..services import llm as llm_module
    llm_module.llm = llm_module._make()
    provider, model = settings.llm_provider, llm_module.llm.model_name
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    print(f"provider={provider} model={model} concurrency={args.concurrency}")

    rc = 0
    for set_name in args.sets:
        cases = load_cases(set_name)
        if args.limit:
            cases = cases[:args.limit]
        results = asyncio.run(run_cases(cases, args.concurrency))
        summary = summarize(set_name, cases, results)
        print_summary(set_name, summary)
        if not args.no_write:
            print(f"   → {write_run(set_name, provider, model, cases, results, summary, stamp).relative_to(ROOT)}")
        rc |= int(summary["errors"] > 0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
