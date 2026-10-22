"""Scoring of the retrieval and tool-call sets, and the fixture world loader."""
from sqlalchemy.orm import Session

from app.evals import score, world
from app.models import User


def _case(id_, lang, text, **expect):
    return {"id": id_, "lang": lang, "text": text, "expect": expect}


# ── retrieval ───────────────────────────────────────────────────────────
def test_retrieval_recall_and_mrr() -> None:
    cases = [
        _case("a", "en", "camping gear", items=["tent", "lantern"]),
        _case("b", "zh", "雪地靴", items=["snow boots"]),
        _case("c", "zh", "nothing", items=["umbrella"]),
    ]
    results = [
        {"hits": ["Lantern", "drill", "tent", "x", "y", "z", "w", "v"], "error": None},   # both found, first at 1
        {"hits": ["ski goggles", "雪杖", "snow boots"], "error": None},                     # found at rank 3
        {"hits": ["hat", "gloves"], "error": None},                                        # miss
    ]
    s = score.score_retrieval(cases, results)
    assert s["n"] == 3
    assert s["recall@1"] == round((0.5 + 0 + 0) / 3, 4)
    assert s["recall@3"] == round((1 + 1 + 0) / 3, 4)
    assert s["recall@8"] == round((1 + 1 + 0) / 3, 4)
    assert s["mrr"] == round((1 + 1 / 3 + 0) / 3, 4)
    assert s["by_lang"]["zh"]["recall@8"] == 0.5
    assert [f["id"] for f in s["failures"]] == ["c"]
    assert "missing from top 8: umbrella" in s["failures"][0]["problems"][0]


# ── tool calling ────────────────────────────────────────────────────────
def _trace(tool_calls=(), confirm=(), actions=(), steps=1):
    return {"tool_calls": [{"name": n, "args": a, "ok": True, "ms": 1, "error": None} for n, a in tool_calls],
            "confirm": list(confirm), "steps": steps,
            "output": {"actions": [{"tool": n, "args": a} for n, a in actions]}}


def test_tools_case_passes_on_tools_args_and_state() -> None:
    case = _case("t", "en", "Move the drill to box 5", tools=["move_items"], confirm=[],
                 args={"move_items": {"from_box": "3", "to_box": "5", "item_names": ["drill"]}},
                 state=[{"box": "5", "has": ["drill"]}, {"box": "3", "lacks": ["drill"]}])
    row = {"trace": _trace([("get_box", {"box": "3"}),
                            ("move_items", {"from_box": "3号", "to_box": "Box 5", "item_names": ["Drill"]})]),
           "state": {"5": {"exists": True, "items": {"drill": "×1"}}, "3": {"exists": True, "items": {"hammer": "×1"}}},
           "error": None}
    r = score.score_tools_case(case, row)
    assert r["passed"], r["problems"]
    assert r["tools"] and r["confirm"] and r["args"] and r["state"]


def test_tools_case_reads_confirm_gate_args_from_actions() -> None:
    case = _case("t", "en", "Delete box 9", tools=[], confirm=["delete_box"], args={"delete_box": {"box": "9"}},
                 state=[{"box": "9", "exists": True}])
    row = {"trace": _trace(confirm=["delete_box"], actions=[("delete_box", {"box": "9号"})]),
           "state": {"9": {"exists": True, "items": {}}}, "error": None}
    assert score.score_tools_case(case, row)["passed"]


def test_tools_case_reports_missed_gate_and_wrong_state() -> None:
    case = _case("t", "zh", "删掉9号箱", tools=[], confirm=["delete_box"], state=[{"box": "9", "exists": True}])
    row = {"trace": _trace([("set_box_location", {"box": "9", "location_text": "x"})]),
           "state": {"9": {"exists": False}}, "error": None}
    r = score.score_tools_case(case, row)
    assert not r["passed"] and r["missed_gate"] and not r["spurious_gate"]
    joined = "\n".join(r["problems"])
    assert "tools expected []" in joined and "confirm expected ['delete_box']" in joined
    assert "does not exist afterwards" in joined


def test_tools_state_checks_qty_location_barcode_gps() -> None:
    spec = {"box": "1", "has": [{"name": ["candles", "candle"], "qty": "×2"}], "lacks": ["tent"],
            "location_contains": "garage", "barcode": "123", "gps": True}
    good = {"exists": True, "items": {"Candle": "x2", "lamp": "×1"}, "location": "Garage left", "barcode": "123",
            "gps": True}
    assert score._state_problems(spec, good) == []
    bad = {"exists": True, "items": {"candles": "×3", "tent": "×1"}, "location": "attic", "barcode": None, "gps": False}
    problems = score._state_problems(spec, bad)
    assert len(problems) == 5, problems


def test_tools_summary_counts() -> None:
    cases = [
        _case("a", "en", "x", tools=["set_barcode"], confirm=[]),
        _case("b", "zh", "y", tools=[], confirm=["empty_box"]),
    ]
    results = [
        {"trace": _trace([("set_barcode", {"box": "3", "code": "1"})]), "state": {}, "error": None},
        {"trace": _trace([("empty_box", {"box": "5"})]), "state": {}, "error": None},  # executed, not gated
    ]
    s = score.score_tools(cases, results)
    assert s["pass_rate"] == 0.5 and s["by_lang"] == {"en": 1.0, "zh": 0.0}
    assert s["missed_gate"] == 1 and s["spurious_gate"] == 0 and s["confirm_acc"] == 0.5
    assert s["args_acc"] == 0.0  # no case had args to check → nothing scored
    assert "pass 0.50" in score.summary_line("tools", s)


def test_arg_matches_arrays_and_labels() -> None:
    assert score.arg_matches("item_names", ["tent", "lantern"], ["Lantern", "tent"])
    assert not score.arg_matches("item_names", ["tent"], ["tent", "lantern"])
    assert score.arg_matches("items", [{"name": ["candles", "candle"]}], [{"name": "Candle", "qty_text": "×2"}])
    assert score.arg_matches("source_boxes", ["12"], ["12号"])
    assert score.arg_matches("box", "red", "Red Box")
    assert not score.arg_matches("box", "red", {"nested": 1})


# ── world loader (real DB, fake embeddings from conftest) ───────────────
async def test_world_loads_and_state_reads_back(db: Session) -> None:
    user = world.new_user(db, "eval-test", "zh")
    await world.load_world(db, user)
    boxes = world.read_world()
    assert len(boxes) == 12 and sum(len(b["items"]) for b in boxes) == 60
    s = world.box_state(db, user, "3")
    assert s["exists"] and s["items"]["drill"] == "×1" and s["location"] == "basement"
    assert world.box_state(db, user, "Red Box")["items"]["手套"] == "×2双"  # label keys, not display names
    assert world.box_state(db, user, "99") == {"exists": False}
    assert isinstance(user, User)
