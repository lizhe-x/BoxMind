"""箱子编号归一化: "1号" = "1号箱" = "Box 1" = "box1" = "1" 指向同一个箱子。

norm_label 是匹配键;display label 保留用户原始风格(数字统一为 "N号")。
"""

import re

_FULLWIDTH = str.maketrans("０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
                           "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_to_int(s: str) -> int | None:
    if not s or any(c not in _CN_DIGITS for c in s):
        return None
    if s == "十":
        return 10
    if "十" in s:
        parts = s.split("十")
        tens = _CN_DIGITS.get(parts[0], 1) if parts[0] else 1
        ones = _CN_DIGITS.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    n = 0
    for c in s:
        n = n * 10 + _CN_DIGITS[c]
    return n


def extract_number(raw: str) -> int | None:
    """从任意写法里抽出纯数字编号;非纯数字编号返回 None。"""
    s = raw.strip().translate(_FULLWIDTH)
    m = re.fullmatch(r"(?:box|箱子?|no\.?|#)?\s*(\d+)\s*(?:号箱?|号|箱)?", s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"([零一二两三四五六七八九十]+)\s*号?箱?", s)
    if m:
        return _cn_to_int(m.group(1))
    return None


def normalize_label(raw: str) -> tuple[str, str, str]:
    """返回 (norm_label 匹配键, display label, 默认箱子名)。"""
    s = raw.strip().translate(_FULLWIDTH)
    n = extract_number(s)
    if n is not None:
        return f"#{n}", f"{n}号", f"{n}号箱"
    # 非数字: 去掉尾部"箱"字做匹配键(红色大箱 = 红色大), 但保留显示原样
    key = re.sub(r"\s+", "", s).lower()
    key = re.sub(r"(箱子|箱)$", "", key) or key
    label = s if len(s) <= 4 else s[:4]
    name = s if s.endswith("箱") else s
    return key, label, name


KRAFT_PALETTE = [
    ("#9C7A52", "#7A5E3E"),
    ("#8A6A48", "#66503A"),
    ("#8F744E", "#6B5638"),
]
