"""箱子编号归一化: "1号" = "1号箱" = "Box 1" = "box1" = "1" 指向同一个箱子。

norm_label 是匹配键(语言无关);display label / 默认名字按用户界面语言生成:
en → label "1", name "Box 1";zh → label "1号", name "1号箱"。
"""

import re

from .i18n import tr

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
    m = re.fullmatch(r"(?:box|箱子?|no\.?|#)?\s*(\d+)\s*(?:号箱?|号|箱|box)?", s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"([零一二两三四五六七八九十]+)\s*号?箱?", s)
    if m:
        return _cn_to_int(m.group(1))
    return None


def normalize_label(raw: str, lang: str | None = None) -> tuple[str, str, str]:
    """返回 (norm_label 匹配键, display label, 默认箱子名)。"""
    s = raw.strip().translate(_FULLWIDTH)
    n = extract_number(s)
    if n is not None:
        return f"#{n}", tr(lang, "label_num", n=n), tr(lang, "name_num", n=n)
    # 非数字: 去掉尾部 "箱" / "box" 做匹配键(红色大箱 = 红色大, kitchen box = kitchen);
    # label 与 name 都保留原样,徽章里放不下由前端缩小字号/省略
    key = re.sub(r"\s+", "", s).lower()
    key = re.sub(r"(箱子|箱|box)$", "", key) or key
    return key, s, s


KRAFT_PALETTE = [
    ("#9C7A52", "#7A5E3E"),
    ("#8A6A48", "#66503A"),
    ("#8F744E", "#6B5638"),
]
