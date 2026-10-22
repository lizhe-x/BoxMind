"""Defensive JSON extraction from model output."""
from app.services.llm import _parse_json


def test_plain_json() -> None:
    assert _parse_json('{"intent": "query"}') == {"intent": "query"}


def test_json_wrapped_in_markdown_fence() -> None:
    raw = '```json\n{"intent": "ingest", "items": [{"name": "帐篷", "qty_text": "×1"}]}\n```'
    assert _parse_json(raw)["items"][0]["name"] == "帐篷"


def test_json_with_leading_prose() -> None:
    raw = '好的，结果如下：{"box_label": "2号", "items": []}'
    assert _parse_json(raw) == {"box_label": "2号", "items": []}


def test_garbage_returns_empty_dict() -> None:
    assert _parse_json("I cannot help with that") == {}
    assert _parse_json("{not json}") == {}
    assert _parse_json("") == {}
