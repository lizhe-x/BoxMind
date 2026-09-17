"""Box label normalisation: every way a user can say "box 1" must map to the same key."""
import pytest

from app.normalize import extract_number, normalize_label


@pytest.mark.parametrize(
    "raw",
    ["1号", "1号箱", "1", "Box 1", "box1", "BOX 1", "No.1", "#1", "１号", "一号", "一号箱", "  1 号 "],
)
def test_numeric_variants_share_one_key(raw: str) -> None:
    norm, label, name = normalize_label(raw)
    assert (norm, label, name) == ("#1", "1号", "1号箱")


@pytest.mark.parametrize(
    ("raw", "n"),
    [("十", 10), ("十号", 10), ("十二号", 12), ("二十", 20), ("二十三号箱", 23), ("两号", 2), ("零号", 0)],
)
def test_chinese_numerals(raw: str, n: int) -> None:
    assert extract_number(raw) == n


@pytest.mark.parametrize("raw", ["红色大箱", "Liam", "工具", "A2", "厨房 箱子"])
def test_non_numeric_returns_none(raw: str) -> None:
    assert extract_number(raw) is None


def test_text_label_strips_trailing_box_word_for_matching_only() -> None:
    norm, label, name = normalize_label("红色大箱")
    assert norm == "红色大"  # matching key
    assert label == "红色大箱"  # display kept verbatim (≤4 chars)
    assert name == "红色大箱"
    assert normalize_label("红色大")[0] == norm  # "红色大" and "红色大箱" are the same box


def test_text_label_is_case_and_space_insensitive() -> None:
    assert normalize_label("Kitchen Box")[0] == normalize_label("kitchenbox")[0]


def test_long_text_label_is_truncated_for_display_but_name_kept() -> None:
    norm, label, name = normalize_label("露营装备大箱子")
    assert label == "露营装备"  # 4-char badge
    assert name == "露营装备大箱子"
    assert norm == "露营装备大"  # "箱子" suffix removed from key


def test_only_box_word_falls_back_to_itself() -> None:
    # "箱" alone would strip to an empty key; the code must fall back to the raw key
    assert normalize_label("箱")[0] == "箱"
