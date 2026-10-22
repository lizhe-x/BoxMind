"""Scoring for the golden sets. Pure functions, no I/O.

Case format (one JSON object per line; see evals/README.md):
  routing     {"id", "lang", "text", "known_labels"?, "expect": {"intent"}}
  extraction  {"id", "lang", "text", "known_labels"?, "expect": {"intent", "box_label", "items": [{"name", "qty_text"}],
                                                                  "location_text"}}
  retrieval   {"id", "lang", "text", "tag", "expect": {"items": [world item names]}}
  tools       {"id", "lang", "text", "expect": {"tools"?: [write tools], "confirm"?: [destructive tools],
                                               "args"?: {tool: {arg: value}}, "state"?: [{"box", ...}]}}
Any expected scalar (and an item's name / qty_text) may be a list of acceptable alternatives.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..normalize import normalize_label

INTENTS = ("ingest", "query", "operation")
_EDGE_PUNCT = " \t\r\n,.;:!?，。、;:!?()（）\"'“”‘’"


def norm_text(s: str | None) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", s.strip(_EDGE_PUNCT).lower())


def norm_qty(s: str | None) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", "", s.strip().replace("x", "×").replace("X", "×").replace("✕", "×")).lower()


def norm_label(s: str | None) -> str:
    """Labels compare by the app's own matching key: "3" == "3号" == "Box 3"; "red box" == "red"."""
    if s is None or not str(s).strip():
        return ""
    return normalize_label(str(s))[0]


def matches(expect: Any, got: Any, norm) -> bool:
    """`expect` is None, a scalar or a list of acceptable scalars."""
    alts = expect if isinstance(expect, list) else [expect]
    if got is None or (isinstance(got, str) and not got.strip()):
        return any(a is None for a in alts)
    return any(a is not None and norm(a) == norm(got) for a in alts)


def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def _f1(p: float, r: float) -> float:
    return round(2 * p * r / (p + r), 4) if p + r else 0.0


# ── routing ─────────────────────────────────────────────────────────────
def score_routing(cases: list[dict], results: list[dict]) -> dict:
    """`results[i]` is `{"got": parsed-or-None, "error": str|None, ...}` for `cases[i]`."""
    confusion: dict[str, Counter] = {i: Counter() for i in INTENTS}
    by_lang: dict[str, list[int]] = {}
    failures = []
    correct = 0
    for case, res in zip(cases, results, strict=True):
        exp = case["expect"]["intent"]
        got = (res.get("got") or {}).get("intent") or ("error" if res.get("error") else "none")
        ok = got == exp
        correct += ok
        confusion[exp][got] += 1
        by_lang.setdefault(case.get("lang", "?"), [0, 0])
        by_lang[case["lang"]][0] += ok
        by_lang[case["lang"]][1] += 1
        if not ok:
            failures.append({"id": case["id"], "text": case["text"], "expect": exp, "got": got,
                             "error": res.get("error")})
    per_intent = {}
    for intent in INTENTS:
        tp = confusion[intent][intent]
        support = sum(confusion[intent].values())
        predicted = sum(confusion[e][intent] for e in INTENTS)
        p, r = _rate(tp, predicted), _rate(tp, support)
        per_intent[intent] = {"precision": p, "recall": r, "f1": _f1(p, r), "support": support}
    return {
        "n": len(cases),
        "accuracy": _rate(correct, len(cases)),
        "by_lang": {lang: _rate(c, n) for lang, (c, n) in sorted(by_lang.items())},
        "per_intent": per_intent,
        "confusion": {e: dict(c) for e, c in confusion.items()},
        "failures": failures,
    }


# ── extraction ──────────────────────────────────────────────────────────
def match_items(expected: list[dict], got: list[dict]) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Greedy one-to-one match by name → (pairs, unmatched expected, unmatched got)."""
    remaining = list(got)
    pairs, missed = [], []
    for e in expected:
        hit = next((g for g in remaining if matches(e["name"], g.get("name"), norm_text)), None)
        if hit is None:
            missed.append(e)
        else:
            pairs.append((e, hit))
            remaining.remove(hit)
    return pairs, missed, remaining


def score_extraction_case(case: dict, got: dict | None) -> dict:
    exp = case["expect"]
    got = got or {}
    pairs, missed, extra = match_items(exp.get("items", []), got.get("items") or [])
    qty_ok = sum(matches(e.get("qty_text"), g.get("qty_text"), norm_qty) for e, g in pairs)
    problems = []
    checks = {
        "intent": got.get("intent") == exp.get("intent", "ingest"),
        "box_label": matches(exp.get("box_label"), got.get("box_label"), norm_label),
        "location": matches(exp.get("location_text"), got.get("location_text"), norm_text),
        "language": matches(case.get("lang"), got.get("language"), norm_text),
    }
    fields = {"intent": "intent", "box_label": "box_label", "location": "location_text", "language": "language"}
    for k, ok in checks.items():
        if not ok:
            expected = case.get("lang") if k == "language" else exp.get(fields[k])
            problems.append(f"{k}: expected {expected!r}, got {got.get(fields[k])!r}")
    if missed:
        problems.append("missing items: " + ", ".join(str(e["name"]) for e in missed))
    if extra:
        problems.append("extra items: " + ", ".join(str(g.get("name")) for g in extra))
    for e, g in pairs:
        if not matches(e.get("qty_text"), g.get("qty_text"), norm_qty):
            problems.append(f"qty of {g.get('name')!r}: expected {e.get('qty_text')!r}, got {g.get('qty_text')!r}")
    return {
        **checks,
        "items_tp": len(pairs), "items_fp": len(extra), "items_fn": len(missed),
        "qty_ok": qty_ok, "qty_n": len(pairs),
        "exact": not problems,
        "problems": problems,
    }


def score_extraction(cases: list[dict], results: list[dict]) -> dict:
    rows = []
    for case, res in zip(cases, results, strict=True):
        row = score_extraction_case(case, res.get("got"))
        if res.get("error"):
            row["problems"].insert(0, f"error: {res['error']}")
            row["exact"] = False
        rows.append(row)
    n = len(rows)
    tp = sum(r["items_tp"] for r in rows)
    fp = sum(r["items_fp"] for r in rows)
    fn = sum(r["items_fn"] for r in rows)
    p, r_ = _rate(tp, tp + fp), _rate(tp, tp + fn)
    by_lang: dict[str, list[int]] = {}
    for case, row in zip(cases, rows, strict=True):
        by_lang.setdefault(case.get("lang", "?"), [0, 0])
        by_lang[case["lang"]][0] += row["exact"]
        by_lang[case["lang"]][1] += 1
    return {
        "n": n,
        "exact_rate": _rate(sum(r["exact"] for r in rows), n),
        "by_lang": {lang: _rate(c, m) for lang, (c, m) in sorted(by_lang.items())},
        "intent_acc": _rate(sum(r["intent"] for r in rows), n),
        "box_label_acc": _rate(sum(r["box_label"] for r in rows), n),
        "location_acc": _rate(sum(r["location"] for r in rows), n),
        "language_acc": _rate(sum(r["language"] for r in rows), n),
        "item_precision": p,
        "item_recall": r_,
        "item_f1": _f1(p, r_),
        "qty_acc": _rate(sum(r["qty_ok"] for r in rows), sum(r["qty_n"] for r in rows)),
        "failures": [{"id": c["id"], "text": c["text"], "problems": r["problems"]}
                     for c, r in zip(cases, rows, strict=True) if not r["exact"]],
    }


# ── retrieval ───────────────────────────────────────────────────────────
def score_retrieval_case(case: dict, hits: list[str], ks: tuple[int, ...] = (1, 3, 8)) -> dict:
    """`hits` are item names in rank order."""
    expected = [norm_text(e) for e in case["expect"]["items"]]
    ranked = [norm_text(h) for h in hits]
    recall = {k: _rate(sum(e in ranked[:k] for e in expected), len(expected)) for k in ks}
    first = next((i + 1 for i, h in enumerate(ranked) if h in expected), None)
    missing = [e for e, raw in zip(expected, case["expect"]["items"], strict=True) if e not in ranked[:max(ks)]]
    return {"recall": recall, "rr": round(1 / first, 4) if first else 0.0, "first_rank": first,
            "missing": [case["expect"]["items"][expected.index(m)] for m in missing]}


def score_retrieval(cases: list[dict], results: list[dict], ks: tuple[int, ...] = (1, 3, 8)) -> dict:
    rows = [score_retrieval_case(c, r.get("hits") or [], ks) for c, r in zip(cases, results, strict=True)]
    n = len(rows)
    groups: dict[str, dict[str, list]] = {"by_lang": {}, "by_tag": {}}
    for case, row in zip(cases, rows, strict=True):
        groups["by_lang"].setdefault(case.get("lang", "?"), []).append(row)
        groups["by_tag"].setdefault(case.get("tag", "untagged"), []).append(row)
    k_max = max(ks)

    def agg(items: list[dict]) -> dict:
        return {"n": len(items), f"recall@{k_max}": _mean([r["recall"][k_max] for r in items]),
                "mrr": _mean([r["rr"] for r in items])}

    return {
        "n": n,
        **{f"recall@{k}": _mean([r["recall"][k] for r in rows]) for k in ks},
        "mrr": _mean([r["rr"] for r in rows]),
        "by_lang": {k: agg(v) for k, v in sorted(groups["by_lang"].items())},
        "by_tag": {k: agg(v) for k, v in sorted(groups["by_tag"].items())},
        "failures": [{"id": c["id"], "text": c["text"],
                      "problems": [f"missing from top {k_max}: {', '.join(r['missing'])}; "
                                   f"got {', '.join((res.get('hits') or [])[:k_max])}"]}
                     for c, r, res in zip(cases, rows, results, strict=True) if r["recall"][k_max] < 1],
    }


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


# ── tool calling ────────────────────────────────────────────────────────
READ_TOOLS = {"search_items", "get_box"}
LABEL_KEYS = {"box", "from_box", "to_box", "target_box", "name"}
ARRAY_KEYS = {"item_names", "source_boxes", "items"}


def arg_matches(key: str, want: Any, got: Any) -> bool:
    if key in ARRAY_KEYS:
        if not isinstance(got, list) or not isinstance(want, list) or len(got) != len(want):
            return False
        norm = norm_label if key == "source_boxes" else norm_text
        got_vals = [g.get("name") if isinstance(g, dict) else g for g in got]
        want_vals = [w.get("name") if isinstance(w, dict) else w for w in want]
        return all(any(matches(w, g, norm) for g in got_vals) for w in want_vals)
    if isinstance(got, (dict, list)):
        return False
    return matches(want, None if got is None else str(got), norm_label if key in LABEL_KEYS else norm_text)


def _state_problems(spec: dict, state: dict | None) -> list[str]:
    box = spec["box"]
    if state is None:
        return [f"state of box {box!r} not captured"]
    out = []
    if not state.get("exists"):
        return [] if spec.get("exists") is False else [f"box {box!r} does not exist afterwards"]
    if spec.get("exists") is False:
        return [f"box {box!r} still exists"]
    items = {norm_text(k): v for k, v in (state.get("items") or {}).items()}
    for want in spec.get("has", []):
        names, qty = (want.get("name"), want.get("qty")) if isinstance(want, dict) else (want, None)
        alts = names if isinstance(names, list) else [names]
        hit = next((norm_text(a) for a in alts if norm_text(a) in items), None)
        if hit is None:
            out.append(f"box {box!r} lacks {alts[0]!r}")
        elif qty is not None and not matches(qty, items[hit], norm_qty):
            out.append(f"box {box!r}: {alts[0]!r} qty expected {qty!r}, got {items[hit]!r}")
    for name in spec.get("lacks", []):
        if norm_text(name) in items:
            out.append(f"box {box!r} still has {name!r}")
    if "location" in spec and not matches(spec["location"], state.get("location"), norm_text):
        out.append(f"box {box!r} location expected {spec['location']!r}, got {state.get('location')!r}")
    if "location_contains" in spec and norm_text(spec["location_contains"]) not in norm_text(state.get("location")):
        out.append(f"box {box!r} location {state.get('location')!r} lacks {spec['location_contains']!r}")
    if "barcode" in spec and (state.get("barcode") or "") != spec["barcode"]:
        out.append(f"box {box!r} barcode expected {spec['barcode']!r}, got {state.get('barcode')!r}")
    if "gps" in spec and bool(state.get("gps")) != spec["gps"]:
        out.append(f"box {box!r} gps expected {spec['gps']}, got {state.get('gps')}")
    return out


def score_tools_case(case: dict, row: dict) -> dict:
    """`row` = {"trace": Trace.to_dict(), "state": {box ref: box_state}, "error": str|None}."""
    exp = case["expect"]
    tr = row.get("trace") or {}
    calls = tr.get("tool_calls") or []
    executed = [c["name"] for c in calls if c["name"] not in READ_TOOLS]
    confirm = list(tr.get("confirm") or [])
    problems: list[str] = []
    checks: dict[str, bool | None] = {"tools": None, "confirm": None, "args": None, "state": None}

    if row.get("error"):
        problems.append(f"error: {row['error']}")
    if "tools" in exp:
        checks["tools"] = sorted(executed) == sorted(exp["tools"])
        if not checks["tools"]:
            problems.append(f"tools expected {exp['tools']}, executed {executed}")
    want_confirm = list(exp.get("confirm", []))
    checks["confirm"] = sorted(confirm) == sorted(want_confirm)
    if not checks["confirm"]:
        problems.append(f"confirm expected {want_confirm}, got {confirm}")

    if exp.get("args"):
        ok_all = True
        actions = [{"name": a["tool"], "args": a["args"]} for a in (tr.get("output") or {}).get("actions", [])]
        for tool, want in exp["args"].items():
            call = next((c for c in calls + actions if c["name"] == tool), None)
            if call is None:
                ok_all = False
                problems.append(f"{tool} was not called")
                continue
            for key, value in want.items():
                if not arg_matches(key, value, (call.get("args") or {}).get(key)):
                    ok_all = False
                    problems.append(f"{tool}.{key} expected {value!r}, got {(call.get('args') or {}).get(key)!r}")
        checks["args"] = ok_all
    if exp.get("state"):
        captured = row.get("state") or {}
        state_problems = [p for spec in exp["state"] for p in _state_problems(spec, captured.get(spec["box"]))]
        checks["state"] = not state_problems
        problems.extend(state_problems)

    if problems and (tr.get("output") or {}).get("text"):
        problems.append(f"reply: {tr['output']['text']!r}")
    return {**checks, "passed": not problems, "problems": problems, "steps": tr.get("steps", 0),
            "missed_gate": bool(want_confirm) and not confirm, "spurious_gate": bool(confirm) and not want_confirm}


def score_tools(cases: list[dict], results: list[dict]) -> dict:
    rows = [score_tools_case(c, r) for c, r in zip(cases, results, strict=True)]
    n = len(rows)
    by_lang: dict[str, list[int]] = {}
    for case, row in zip(cases, rows, strict=True):
        by_lang.setdefault(case.get("lang", "?"), [0, 0])
        by_lang[case["lang"]][0] += row["passed"]
        by_lang[case["lang"]][1] += 1

    def acc(key: str) -> float:
        scored = [r[key] for r in rows if r[key] is not None]
        return _rate(sum(scored), len(scored))

    return {
        "n": n,
        "pass_rate": _rate(sum(r["passed"] for r in rows), n),
        "by_lang": {lang: _rate(c, m) for lang, (c, m) in sorted(by_lang.items())},
        "tools_acc": acc("tools"), "confirm_acc": acc("confirm"), "args_acc": acc("args"), "state_acc": acc("state"),
        "missed_gate": sum(r["missed_gate"] for r in rows), "spurious_gate": sum(r["spurious_gate"] for r in rows),
        "steps_avg": _mean([r["steps"] for r in rows]),
        "failures": [{"id": c["id"], "text": c["text"], "problems": r["problems"]}
                     for c, r in zip(cases, rows, strict=True) if not r["passed"]],
    }


# ── validation of the golden files ──────────────────────────────────────
def validate_case(set_name: str, case: dict) -> list[str]:
    errs = []
    for key in ("id", "lang", "text", "expect"):
        if key not in case:
            errs.append(f"missing {key}")
    if errs:
        return errs
    if case["lang"] not in ("en", "zh"):
        errs.append(f"lang must be en|zh, got {case['lang']!r}")
    exp = case["expect"]
    if set_name in ("routing", "extraction") and exp.get("intent") not in INTENTS:
        errs.append(f"expect.intent must be one of {INTENTS}, got {exp.get('intent')!r}")
    if set_name == "extraction":
        for key in ("box_label", "items", "location_text"):
            if key not in exp:
                errs.append(f"expect.{key} missing")
        for it in exp.get("items", []):
            if "name" not in it or "qty_text" not in it:
                errs.append(f"item {it!r} needs name and qty_text")
    if set_name == "retrieval" and not (isinstance(exp.get("items"), list) and exp["items"]):
        errs.append("expect.items must be a non-empty list of world item names")
    if set_name == "tools":
        if not ("tools" in exp or "confirm" in exp or "state" in exp):
            errs.append("expect needs at least one of tools / confirm / state")
        for key in ("tools", "confirm"):
            if key in exp and not isinstance(exp[key], list):
                errs.append(f"expect.{key} must be a list")
        for spec in exp.get("state", []):
            if "box" not in spec:
                errs.append(f"state entry {spec!r} needs box")
    if not isinstance(case.get("known_labels", []), list):
        errs.append("known_labels must be a list")
    return errs


def summary_line(set_name: str, summary: dict) -> str:
    """One-line headline for RESULTS.md."""
    if set_name == "routing":
        langs = " · ".join(f"{k} {v:.2f}" for k, v in summary["by_lang"].items())
        f1 = " · ".join(f"{k} F1 {v['f1']:.2f}" for k, v in summary["per_intent"].items())
        return f"acc {summary['accuracy']:.2f} · {langs} · {f1}"
    if set_name == "retrieval":
        langs = " · ".join(f"{k} {v['recall@8']:.2f}" for k, v in summary["by_lang"].items())
        tags = " · ".join(f"{k} {v['recall@8']:.2f}" for k, v in summary["by_tag"].items())
        return (f"R@1 {summary['recall@1']:.2f} · R@3 {summary['recall@3']:.2f} · R@8 {summary['recall@8']:.2f} · "
                f"MRR {summary['mrr']:.2f} · {langs} · {tags}")
    if set_name == "tools":
        langs = " · ".join(f"{k} {v:.2f}" for k, v in summary["by_lang"].items())
        return (f"pass {summary['pass_rate']:.2f} · {langs} · tools {summary['tools_acc']:.2f} · "
                f"confirm {summary['confirm_acc']:.2f} · args {summary['args_acc']:.2f} · "
                f"state {summary['state_acc']:.2f} · missed gate {summary['missed_gate']} · "
                f"spurious gate {summary['spurious_gate']} · steps {summary['steps_avg']:.1f}")
    langs = " · ".join(f"{k} {v:.2f}" for k, v in summary["by_lang"].items())
    return (f"exact {summary['exact_rate']:.2f} · {langs} · intent {summary['intent_acc']:.2f} · "
            f"label {summary['box_label_acc']:.2f} · location {summary['location_acc']:.2f} · "
            f"items P {summary['item_precision']:.2f} R {summary['item_recall']:.2f} · qty {summary['qty_acc']:.2f}")
