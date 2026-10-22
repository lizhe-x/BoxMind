"""The golden files in evals/ must parse, validate and stay balanced; a bad case fails CI, not the eval run."""
import pytest

from app.evals import harness, world


@pytest.mark.parametrize("set_name", harness.SETS)
def test_golden_set_is_valid(set_name: str) -> None:
    cases = harness.load_cases(set_name)
    assert len(cases) >= 40
    langs = {c["lang"] for c in cases}
    assert langs == {"en", "zh"}
    zh = sum(c["lang"] == "zh" for c in cases)
    assert abs(zh - (len(cases) - zh)) <= 2, "sets stay roughly half Chinese, half English"


def test_routing_set_covers_every_intent_evenly() -> None:
    cases = harness.load_cases("routing")
    counts = {i: sum(c["expect"]["intent"] == i for c in cases) for i in ("ingest", "query", "operation")}
    assert min(counts.values()) >= 15, counts


def test_retrieval_and_tools_refer_to_world_items() -> None:
    names = {name for b in world.read_world() for name, _ in b["items"]}
    for case in harness.load_cases("retrieval"):
        missing = set(case["expect"]["items"]) - names
        assert not missing, f"{case['id']}: not in world: {missing}"
    for case in harness.load_cases("tools"):
        for spec in case["expect"].get("state", []):
            for name in spec.get("lacks", []):
                assert name in names, f"{case['id']}: lacks {name!r} not in world"


def test_tools_set_exercises_the_confirm_gate_in_both_languages() -> None:
    cases = harness.load_cases("tools")
    gated = {c["lang"] for c in cases if c["expect"].get("confirm")}
    assert gated == {"en", "zh"}
    assert sum(bool(c["expect"].get("confirm")) for c in cases) >= 8


def test_load_cases_reports_bad_lines(tmp_path) -> None:
    bad = tmp_path / "routing.jsonl"
    bad.write_text('{"id": "a", "lang": "en", "text": "x", "expect": {"intent": "query"}}\n'
                   '{"id": "a", "lang": "xx", "text": "y", "expect": {"intent": "nope"}}\n'
                   'not json\n', encoding="utf-8")
    with pytest.raises(ValueError) as e:
        harness.load_cases("routing", bad)
    msg = str(e.value)
    assert "duplicate id a" in msg and "lang must be" in msg and "routing.jsonl:3" in msg
