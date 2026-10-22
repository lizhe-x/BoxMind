#!/usr/bin/env python3
"""Regenerate BoxMindKit/Sources/BoxMindKit/L10nTable.swift from frontend/src/i18n.ts.

The frozen web client stays the source of truth for UI strings; run this after editing i18n.ts:
    python3 ios/scripts/gen_l10n.py
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend/src/i18n.ts"
DST = ROOT / "ios/BoxMindKit/Sources/BoxMindKit/L10nTable.swift"
EXTRA = ROOT / "ios/scripts/l10n_extra.json"  # iOS-only keys, {key: {"en": ..., "zh": ...}}
PAT = re.compile(r"""^\s*(\w+):\s*('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"),\s*(//.*)?$""", re.M)


def block(src: str, name: str) -> str:
    start = src.index(f"const {name}")
    return src[start:src.index("\n}", start)]


def parse(b: str) -> dict[str, str]:
    out = {}
    for k, v, _ in PAT.findall(b):
        q = v[0]
        out[k] = v[1:-1].replace("\\" + q, q).replace("\\\\", "\\")
    return out


def swift_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    src = SRC.read_text()
    en, zh = parse(block(src, "en")), parse(block(src, "zh"))
    assert set(en) == set(zh), set(en) ^ set(zh)
    if EXTRA.exists():
        import json
        for k, v in json.loads(EXTRA.read_text()).items():
            if k.startswith("_"):
                continue
            assert k not in en, f"{k} already exists in i18n.ts"
            en[k], zh[k] = v["en"], v["zh"]
    keys = list(en)
    lines = [
        "// GENERATED from frontend/src/i18n.ts (+ ios/scripts/l10n_extra.json) by ios/scripts/gen_l10n.py — do not edit by hand.",
        "// UI strings. English is the default; Chinese is the other supported language.",
        "",
        "public enum L10nKey: String, CaseIterable, Sendable {",
        *[f"    case {k}" for k in keys],
        "}",
        "",
        "extension L10n {",
        "    static let en: [L10nKey: String] = [",
        *[f"        .{k}: {swift_str(en[k])}," for k in keys],
        "    ]",
        "",
        "    static let zh: [L10nKey: String] = [",
        *[f"        .{k}: {swift_str(zh[k])}," for k in keys],
        "    ]",
        "}",
        "",
    ]
    DST.write_text("\n".join(lines))
    print(f"{len(keys)} keys → {DST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
