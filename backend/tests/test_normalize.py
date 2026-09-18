"""Box label normalisation: every way a user can say "box 1" must map to the same key,
and the display label / default name follow the UI language."""
import pytest

from app.normalize import extract_number, normalize_label


@pytest.mark.parametrize(
    "raw",
    ["1号", "1号箱", "1", "Box 1", "box1", "BOX 1", "No.1", "#1", "１号", "一号", "一号箱", "  1 号 ", "1 box"],
)
def test_numeric_variants_share_one_key(raw: str) -> None:
    assert normalize_label(raw)[0] == "#1"
    assert normalize_label(raw, "zh")[0] == "#1"


def test_numeric_display_follows_language() -> None:
    assert normalize_label("Box 1") == ("#1", "1", "Box 1")  # default: English
    assert normalize_label("1号", "en") == ("#1", "1", "Box 1")
    assert normalize_label("Box 1", "zh") == ("#1", "1号", "1号箱")
    assert normalize_label("1", "zh-CN") == ("#1", "1号", "1号箱")
    assert normalize_label("1", "fr") == ("#1", "1", "Box 1")  # unknown languages fall back to English


@pytest.mark.parametrize(
    ("raw", "n"),
    [("十", 10), ("十号", 10), ("十二号", 12), ("二十", 20), ("二十三号箱", 23), ("两号", 2), ("零号", 0)],
)
def test_chinese_numerals(raw: str, n: int) -> None:
    assert extract_number(raw) == n


@pytest.mark.parametrize("raw", ["红色大箱", "Liam", "工具", "A2", "厨房 箱子", "kitchen box"])
def test_non_numeric_returns_none(raw: str) -> None:
    assert extract_number(raw) is None


def test_text_label_strips_trailing_box_word_for_matching_only() -> None:
    norm, label, name = normalize_label("红色大箱")
    assert norm == "红色大"  # matching key
    assert label == "红色大箱"  # display kept verbatim
    assert name == "红色大箱"
    assert normalize_label("红色大")[0] == norm  # "红色大" and "红色大箱" are the same box

    norm, label, name = normalize_label("Kitchen box")
    assert norm == "kitchen" and normalize_label("kitchen")[0] == norm
    assert (label, name) == ("Kitchen box", "Kitchen box")  # text labels are kept verbatim


def test_text_label_is_case_and_space_insensitive() -> None:
    assert normalize_label("Kitchen Box")[0] == normalize_label("kitchenbox")[0]


def test_long_cjk_label_is_kept_verbatim() -> None:
    norm, label, name = normalize_label("露营装备大箱子")
    assert label == "露营装备大箱子"
    assert name == "露营装备大箱子"
    assert norm == "露营装备大"  # "箱子" suffix removed from key


def test_only_box_word_falls_back_to_itself() -> None:
    # "箱" / "box" alone would strip to an empty key; the code must fall back to the raw key
    assert normalize_label("箱")[0] == "箱"
    assert normalize_label("box")[0] == "box"
