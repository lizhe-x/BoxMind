"""Pure scoring of the interpret golden sets."""
from app.evals import score


def _case(id_, lang, text, **expect):
    return {"id": id_, "lang": lang, "text": text, "expect": expect}


# ── normalisers / matching ──────────────────────────────────────────────
def test_label_matching_uses_app_key() -> None:
    assert score.matches("3", "3号", score.norm_label)
    assert score.matches("3", "Box 3", score.norm_label)
    assert score.matches(["red", "red box"], "Red Box", score.norm_label)
    assert not score.matches("3", "4", score.norm_label)


def test_qty_matching_ignores_x_variant_and_spaces() -> None:
    assert score.matches("×2 pairs", "x2 pairs", score.norm_qty)
    assert score.matches("×2件", "×2 件", score.norm_qty)
    assert not score.matches("×2", "×3", score.norm_qty)


def test_none_matches_only_none_or_empty() -> None:
    assert score.matches(None, None, score.norm_text)
    assert score.matches(None, "", score.norm_text)
    assert not score.matches(None, "garage", score.norm_text)
    assert not score.matches("garage", None, score.norm_text)
    assert score.matches([None, "garage"], "Garage.", score.norm_text)


# ── routing ─────────────────────────────────────────────────────────────
def test_routing_accuracy_confusion_and_failures() -> None:
    cases = [
        _case("a", "en", "Box 1 has a tent", intent="ingest"),
        _case("b", "zh", "雪地靴在哪", intent="query"),
        _case("c", "en", "Delete box 9", intent="operation"),
        _case("d", "zh", "清空4号箱", intent="operation"),
    ]
    results = [
        {"got": {"intent": "ingest"}, "error": None},
        {"got": {"intent": "query"}, "error": None},
        {"got": {"intent": "query"}, "error": None},       # wrong
        {"got": None, "error": "boom"},                     # provider error
    ]
    s = score.score_routing(cases, results)
    assert s["n"] == 4 and s["accuracy"] == 0.5
    assert s["by_lang"] == {"en": 0.5, "zh": 0.5}
    assert s["confusion"]["operation"] == {"query": 1, "error": 1}
    assert s["per_intent"]["query"]["precision"] == 0.5 and s["per_intent"]["query"]["recall"] == 1.0
    assert s["per_intent"]["operation"]["recall"] == 0.0
    assert [f["id"] for f in s["failures"]] == ["c", "d"]
    assert s["failures"][1]["got"] == "error"


# ── extraction ──────────────────────────────────────────────────────────
def _x(id_, lang, text, box_label, items, location=None):
    return _case(id_, lang, text, intent="ingest", box_label=box_label, items=items, location_text=location)


def test_extraction_exact_case() -> None:
    case = _x("x", "en", "Box 1 has three down jackets and a headlamp", "1",
              [{"name": ["down jackets", "down jacket"], "qty_text": "×3"}, {"name": "headlamp", "qty_text": "×1"}])
    got = {"intent": "ingest", "box_label": "1", "language": "en", "location_text": None,
           "items": [{"name": "Headlamp", "qty_text": "x1"}, {"name": "down jacket", "qty_text": "×3"}]}
    row = score.score_extraction_case(case, got)
    assert row["exact"] and row["problems"] == []
    assert row["items_tp"] == 2 and row["items_fp"] == 0 and row["items_fn"] == 0 and row["qty_ok"] == 2


def test_extraction_reports_each_problem() -> None:
    case = _x("x", "zh", "3号箱放了两件羽绒服和一个头灯,在车库", "3",
              [{"name": "羽绒服", "qty_text": "×2"}, {"name": "头灯", "qty_text": "×1"}], "车库")
    got = {"intent": "operation", "box_label": "4号", "language": "en", "location_text": None,
           "items": [{"name": "羽绒服", "qty_text": "×3"}, {"name": "袜子", "qty_text": "×1"}]}
    row = score.score_extraction_case(case, got)
    assert not row["exact"]
    assert row["items_tp"] == 1 and row["items_fp"] == 1 and row["items_fn"] == 1 and row["qty_ok"] == 0
    joined = "\n".join(row["problems"])
    for needle in ("intent", "box_label", "location", "language", "missing items: 头灯", "extra items: 袜子", "qty of '羽绒服'"):
        assert needle in joined, joined


def test_extraction_summary_micro_averages() -> None:
    cases = [
        _x("a", "en", "t", "1", [{"name": "tent", "qty_text": "×1"}, {"name": "lamp", "qty_text": "×2"}]),
        _x("b", "zh", "t", "2", [{"name": "帐篷", "qty_text": "×1"}], "地下室"),
    ]
    results = [
        {"got": {"intent": "ingest", "box_label": "1", "language": "en", "location_text": None,
                 "items": [{"name": "tent", "qty_text": "×1"}, {"name": "lamp", "qty_text": "×1"}]}, "error": None},
        {"got": None, "error": "timeout"},
    ]
    s = score.score_extraction(cases, results)
    assert s["n"] == 2 and s["exact_rate"] == 0.0
    assert s["item_precision"] == 1.0 and s["item_recall"] == round(2 / 3, 4)
    assert s["qty_acc"] == 0.5
    assert s["box_label_acc"] == 0.5 and s["intent_acc"] == 0.5
    assert s["failures"][1]["problems"][0].startswith("error: timeout")
    line = score.summary_line("extraction", s)
    assert line.startswith("exact 0.00") and "items P 1.00 R 0.67" in line


# ── validation ──────────────────────────────────────────────────────────
def test_validate_case_catches_shape_errors() -> None:
    assert score.validate_case("routing", {"id": "r", "lang": "en", "text": "x", "expect": {"intent": "query"}}) == []
    errs = score.validate_case("extraction", {"id": "x", "lang": "fr", "text": "x",
                                              "expect": {"intent": "ask", "items": [{"name": "a"}]}})
    joined = "\n".join(errs)
    for needle in ("lang must be", "expect.intent", "expect.box_label missing", "expect.location_text missing",
                   "needs name and qty_text"):
        assert needle in joined, joined
