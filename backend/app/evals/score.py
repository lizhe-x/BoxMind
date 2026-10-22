"""Scoring for the interpret golden sets (routing and extraction). Pure functions, no I/O.

Case format (one JSON object per line):
  routing     {"id", "lang", "text", "known_labels"?, "expect": {"intent"}}
  extraction  {"id", "lang", "text", "known_labels"?, "expect": {"intent", "box_label", "items": [{"name", "qty_text"}],
                                                                  "location_text"}}
Any scalar in `expect` (and an item's name / qty_text) may be a list of acceptable alternatives.
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
    if exp.get("intent") not in INTENTS:
        errs.append(f"expect.intent must be one of {INTENTS}, got {exp.get('intent')!r}")
    if set_name == "extraction":
        for key in ("box_label", "items", "location_text"):
            if key not in exp:
                errs.append(f"expect.{key} missing")
        for it in exp.get("items", []):
            if "name" not in it or "qty_text" not in it:
                errs.append(f"item {it!r} needs name and qty_text")
    if not isinstance(case.get("known_labels", []), list):
        errs.append("known_labels must be a list")
    return errs


def summary_line(set_name: str, summary: dict) -> str:
    """One-line headline for RESULTS.md."""
    if set_name == "routing":
        langs = " · ".join(f"{k} {v:.2f}" for k, v in summary["by_lang"].items())
        f1 = " · ".join(f"{k} F1 {v['f1']:.2f}" for k, v in summary["per_intent"].items())
        return f"acc {summary['accuracy']:.2f} · {langs} · {f1}"
    langs = " · ".join(f"{k} {v:.2f}" for k, v in summary["by_lang"].items())
    return (f"exact {summary['exact_rate']:.2f} · {langs} · intent {summary['intent_acc']:.2f} · "
            f"label {summary['box_label_acc']:.2f} · location {summary['location_acc']:.2f} · "
            f"items P {summary['item_precision']:.2f} R {summary['item_recall']:.2f} · qty {summary['qty_acc']:.2f}")
