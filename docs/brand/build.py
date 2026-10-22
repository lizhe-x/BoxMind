"""Generates every BoxMind logo variant from one geometry definition.

    python docs/brand/build.py

The mark: a closed shipping box seen from the front-right, brand gradient on the walls, a strip of tape over
the top and down the front, and an amber label tag hanging from the top-right corner. It says "every box has
a name and a list". Chosen 2026-10-22 over the earlier open box with falling solids (the red sphere read as a
clown nose).

Outputs (all in this directory):
  logo-mark.svg          512×512, transparent, the primary mark
  favicon-mark.svg       the mark cropped tight, for 16–64 px
  icon-source.svg        the mark on the app background with a ground shadow, 512×512
  app-icon-1024.svg      same at 1024×1024; render it to PNG for the iOS AppIcon and the PWA icons
  logo-mono.svg          one colour (currentColor), for print and fixed-palette favicons
  logo-wordmark-dark.svg / logo-wordmark-light.svg   horizontal lockups
  preview.html           contact sheet, render.html  the 1024 icon alone

PNGs are rendered separately (see README.md).
"""
from pathlib import Path

OUT = Path(__file__).parent

# ── geometry, in a 512 × 512 space ─────────────────────────────────────────
# box: front face 98..358 × 196..436, top face rises 60 to the back, side face 60 to the right
TOP = "98,196 358,196 418,136 158,136"
SIDE = "358,196 418,136 418,376 358,436"
FRONT = "M109,196 H358 V436 H109 Q98,436 98,425 V207 Q98,196 109,196 Z"
TAPE_TOP = "213,196 243,196 303,136 273,136"
TAPE_FRONT = dict(x=213, y=196, w=30, h=240)
# label tag in its own 196 × 276 space, hole at (98, 52); placed by hole position, rotation and scale
TAG = "M98,0 Q110,0 118,10 L188,66 Q196,72 196,82 V246 Q196,276 166,276 H30 Q0,276 0,246 V82 Q0,72 8,66 L78,10 Q86,0 98,0 Z"
TAG_HOLE = (98, 52)
TAG_AT = (395, 170)      # where the hole sits in the 512 space
TAG_ROT = -14
TAG_SCALE = 0.59
STRING = "M418,136 C 414,148 405,160 395,170"


def tag_group(fill="url(#tag)", hole_ring="#0C1122", hole_dot="#F6EEDC", lines="#5A3A0E", lines_opacity=".7",
              scale=TAG_SCALE, at=TAG_AT, extra_attrs=""):
    hx, hy = TAG_HOLE
    return (f'<g transform="translate({at[0]},{at[1]}) rotate({TAG_ROT}) scale({scale}) translate({-hx},{-hy})"{extra_attrs}>'
            f'<path d="{TAG}" fill="{fill}"/>'
            f'<circle cx="{hx}" cy="{hy}" r="20" fill="{hole_ring}" fill-opacity=".82"/>'
            f'<circle cx="{hx}" cy="{hy}" r="9" fill="{hole_dot}"/>'
            f'<rect x="44" y="124" width="108" height="24" rx="12" fill="{lines}" fill-opacity="{lines_opacity}"/>'
            f'<rect x="44" y="174" width="70" height="24" rx="12" fill="{lines}" fill-opacity="{lines_opacity}"/>'
            '</g>')


def tag_shadow():
    hx, hy = TAG_HOLE
    x, y = TAG_AT[0] + 5, TAG_AT[1] + 7
    return (f'<g transform="translate({x},{y}) rotate({TAG_ROT}) scale({TAG_SCALE}) translate({-hx},{-hy})">'
            f'<path d="{TAG}" fill="#05070F" fill-opacity=".45" filter="url(#tagShadow)"/></g>')


def defs(p, background=False):
    """Gradient definitions with a per-file id prefix so several marks can share one HTML page."""
    d = [
        f'<linearGradient id="{p}front" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5584FF"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient>',
        f'<linearGradient id="{p}side" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3C63D6"/><stop offset="1" stop-color="#4E35A8"/></linearGradient>',
        f'<linearGradient id="{p}top" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#B4C4FF"/><stop offset="1" stop-color="#CDB8FF"/></linearGradient>',
        f'<linearGradient id="{p}tag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFD98A"/><stop offset="1" stop-color="#FFA640"/></linearGradient>',
        f'<filter id="{p}tagShadow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="6"/></filter>',
    ]
    if background:
        d += [
            f'<linearGradient id="{p}bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0C1122"/><stop offset="1" stop-color="#171F3C"/></linearGradient>',
            f'<radialGradient id="{p}vig" cx=".5" cy=".42" r=".6"><stop offset="0" stop-color="#2A3566" stop-opacity=".55"/><stop offset="1" stop-color="#0C1122" stop-opacity="0"/></radialGradient>',
            f'<filter id="{p}soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="11"/></filter>',
        ]
    return "<defs>" + "".join(d) + "</defs>"


def art(p, shadow=False):
    """The mark in the 512 space. `p` is the gradient id prefix."""
    parts = []
    if shadow:
        parts.append(f'<ellipse cx="260" cy="442" rx="165" ry="22" fill="#05070F" fill-opacity=".7" filter="url(#{p}soft)"/>')
    parts += [
        f'<polygon points="{TOP}" fill="url(#{p}top)"/>',
        f'<polygon points="{SIDE}" fill="url(#{p}side)"/>',
        f'<path d="{FRONT}" fill="url(#{p}front)"/>',
        f'<polygon points="{TAPE_TOP}" fill="#FFFFFF" fill-opacity=".22"/>',
        f'<rect x="{TAPE_FRONT["x"]}" y="{TAPE_FRONT["y"]}" width="{TAPE_FRONT["w"]}" height="{TAPE_FRONT["h"]}" fill="#FFFFFF" fill-opacity=".16"/>',
        tag_shadow().replace('url(#tagShadow)', f'url(#{p}tagShadow)'),
        f'<path d="{STRING}" fill="none" stroke="#F6EEDC" stroke-width="4.5" stroke-linecap="round"/>',
        tag_group(fill=f"url(#{p}tag)", hole_dot="#F6EEDC"),
    ]
    return "".join(parts)


def mono():
    """One colour: the box as three tones of currentColor, the tag solid, hole and lines knocked to low opacity."""
    return "".join([
        f'<polygon points="{TOP}" fill="currentColor" fill-opacity=".28"/>',
        f'<polygon points="{SIDE}" fill="currentColor" fill-opacity=".55"/>',
        f'<path d="{FRONT}" fill="currentColor" fill-opacity=".4"/>',
        f'<path d="{STRING}" fill="none" stroke="currentColor" stroke-width="4.5" stroke-linecap="round"/>',
        tag_group(fill="currentColor", hole_ring="#FFFFFF", hole_dot="currentColor", lines="#FFFFFF", lines_opacity=".85"),
    ])


def svg(body, defs_block="", w=512, h=512, viewbox="0 0 512 512", extra=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{w}" height="{h}" role="img" aria-label="BoxMind"{extra}>'
            f'<title>BoxMind</title>{defs_block}{body}</svg>\n')


def write(name, text):
    (OUT / name).write_text(text, encoding="utf-8")
    print(name)


def background(p, size):
    return (f'<rect width="{size}" height="{size}" fill="url(#{p}bg)"/>'
            f'<rect width="{size}" height="{size}" fill="url(#{p}vig)"/>')


def wordmark(text_color):
    p = "w"
    mark = f'<g transform="translate(0,-10) scale(0.66)">{art(p)}</g>'
    text = (f'<text x="254" y="207" font-family="\'Space Grotesk\',\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif" '
            f'font-size="132" font-weight="600" letter-spacing="-3" fill="{text_color}">BoxMind</text>')
    return svg(mark + text, defs(p), w=790, h=320, viewbox="0 0 790 320")


def main():
    write("logo-mark.svg", svg(art("m"), defs("m")))
    write("favicon-mark.svg", svg(art("f"), defs("f"), viewbox="80 104 392 392"))
    write("icon-source.svg", svg(background("i", 512) + art("i", shadow=True), defs("i", background=True)))
    write("app-icon-1024.svg", svg(f'<g transform="scale(2)">{background("a", 512) + art("a", shadow=True)}</g>',
                                   defs("a", background=True), w=1024, h=1024, viewbox="0 0 1024 1024"))
    write("logo-mono.svg", svg(mono(), extra=' fill="currentColor"'))
    write("logo-wordmark-dark.svg", wordmark("#F2F5FA"))
    write("logo-wordmark-light.svg", wordmark("#141826"))

    sizes = [16, 32, 64, 128, 256]
    tiles = "".join(
        f'<div class="row"><span class="lbl">{s} px</span>'
        f'<span class="light"><img src="favicon-mark.svg" width="{s}" height="{s}"></span>'
        f'<span class="dark"><img src="favicon-mark.svg" width="{s}" height="{s}"></span>'
        f'<span class="light"><img src="logo-mark.svg" width="{s}" height="{s}"></span>'
        f'<span class="dark"><img src="logo-mark.svg" width="{s}" height="{s}"></span>'
        f'<span class="dark"><img src="icon-source.svg" width="{s}" height="{s}" style="border-radius:22%"></span></div>'
        for s in sizes)
    write("preview.html", f"""<!doctype html><meta charset="utf-8"><title>BoxMind brand preview</title>
<style>body{{font:14px system-ui;margin:24px;color:#333}} .row{{display:flex;align-items:center;gap:18px;margin:10px 0}}
.lbl{{width:60px;color:#888}} .light,.dark{{display:inline-flex;padding:14px;border-radius:12px}} .light{{background:#f2f2f7}} .dark{{background:#0c1122}}
h2{{font-weight:500;margin:28px 0 8px}} img{{display:block}}</style>
<h2>favicon-mark · logo-mark · icon-source (light / dark)</h2>{tiles}
<h2>wordmarks</h2>
<div class="row"><span class="light"><img src="logo-wordmark-light.svg" height="120"></span><span class="dark"><img src="logo-wordmark-dark.svg" height="120"></span></div>
<h2>mono</h2>
<div class="row"><span class="light" style="color:#141826"><img src="logo-mono.svg" width="128"></span><span class="dark" style="color:#fff"><img src="logo-mono.svg" width="128"></span></div>
""")
    write("render.html", '<!doctype html><meta charset="utf-8"><title>BoxMind icon</title>'
                         '<style>body{margin:0;background:#fff}</style><img src="app-icon-1024.svg" width="1024" height="1024">\n')


if __name__ == "__main__":
    main()
