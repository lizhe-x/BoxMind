"""Generates every BoxMind logo variant from one geometry definition.

    python docs/brand/build.py

PNGs (frontend/public/icon-*.png) are rendered from icon-source.svg separately —
see README.md in this directory.
"""
from pathlib import Path

OUT = Path(__file__).parent

# ── the box ─────────────────────────────────────────────────────────────────
# isometric: rim half-width 150, half-height 87, wall depth 96
BOX = dict(
    rim="256,200 406,287 256,374 106,287",
    void="256,217 376,287 256,357 136,287",
    left="106,287 256,374 256,470 106,383",
    right="256,374 406,287 406,383 256,470",
)


# ── the falling shapes ──────────────────────────────────────────────────────
def pyramid(cx, cy, a, h):
    """Isometric pyramid; (cx, cy) is the centre of the base, `h` the apex rise."""
    b = round(a * 0.577)
    return dict(left=f"{cx},{cy - h} {cx - a},{cy} {cx},{cy + b}",
                right=f"{cx},{cy - h} {cx + a},{cy} {cx},{cy + b}")


def cube(cx, cy, a, d):
    """Isometric cube; (cx, cy) is the centre of the top face, `d` the wall depth."""
    b = round(a * 0.577)
    return dict(top=f"{cx},{cy - b} {cx + a},{cy} {cx},{cy + b} {cx - a},{cy}",
                right=f"{cx},{cy + b} {cx + a},{cy} {cx + a},{cy + d} {cx},{cy + b + d}",
                left=f"{cx - a},{cy} {cx},{cy + b} {cx},{cy + b + d} {cx - a},{cy + d}")


class Layout:
    """One arrangement of pyramid / cube / sphere over the box mouth.

    The two airborne shapes are tumbled a few degrees off the isometric grid —
    that, plus getting smaller the higher they are, is what reads as falling.
    """

    def __init__(self, pyr, cub, sph, tumble):
        self.pyr, self.cub, self.sph, self.tumble = pyr, cub, sph, tumble


# staggered left-right so the three read as a sequence dropping in, not a stack
FULL = Layout(
    pyr=pyramid(298, 104, 32, 46),
    cub=cube(198, 160, 32, 24),
    sph=dict(cx=272, cy=258, r=40),
    tumble=dict(pyr=(15, 298, 94), cub=(-16, 198, 172)),  # (degrees, centre x, centre y)
)
# small sizes: bigger shapes, tucked closer to the box
COMPACT = Layout(
    pyr=pyramid(296, 112, 36, 50),
    cub=cube(196, 158, 37, 28),
    sph=dict(cx=274, cy=256, r=46),
    tumble=dict(pyr=(15, 296, 100), cub=(-16, 196, 172)),
)


def defs(p, background=False):
    g = f'''
    <linearGradient id="{p}Rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8CA4FF"/><stop offset="1" stop-color="#B49BFF"/></linearGradient>
    <linearGradient id="{p}Right" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4D7CFE"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient>
    <linearGradient id="{p}Left" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2F55C9"/><stop offset="1" stop-color="#5B3AB8"/></linearGradient>
    <linearGradient id="{p}Void" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#070A14"/><stop offset="1" stop-color="#161D33"/></linearGradient>
    <radialGradient id="{p}Glow" cx=".5" cy=".5" r=".5">
      <stop offset="0" stop-color="#AFC2FF" stop-opacity=".38"/><stop offset="1" stop-color="#7C9BFF" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="{p}Sphere" cx=".34" cy=".28" r=".8">
      <stop offset="0" stop-color="#FFC9BE"/><stop offset=".42" stop-color="#FF6152"/><stop offset="1" stop-color="#CC2C26"/>
    </radialGradient>
    <linearGradient id="{p}CubeTop" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#93F5D1"/><stop offset="1" stop-color="#4FDFA9"/></linearGradient>
    <linearGradient id="{p}CubeR" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#28C990"/><stop offset="1" stop-color="#15A877"/></linearGradient>
    <linearGradient id="{p}CubeL" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1CAE7E"/><stop offset="1" stop-color="#0E8760"/></linearGradient>
    <linearGradient id="{p}PyrR" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9BDCFF"/><stop offset="1" stop-color="#3FA8FF"/></linearGradient>
    <linearGradient id="{p}PyrL" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4699F5"/><stop offset="1" stop-color="#2A76E0"/></linearGradient>'''
    g += f'\n    <clipPath id="{p}Inner"><polygon points="{BOX["void"]}"/></clipPath>'
    if background:
        g += (f'\n    <linearGradient id="{p}Bg" x1="0" y1="0" x2="1" y2="1">'
              '<stop offset="0" stop-color="#0E1424"/><stop offset="1" stop-color="#070A12"/></linearGradient>')
    return g


def art(p, layout=FULL):
    """Box + falling shapes, in paint order."""
    sph = layout.sph
    pyr_rot = "rotate(%s %s %s)" % layout.tumble["pyr"]
    cub_rot = "rotate(%s %s %s)" % layout.tumble["cub"]
    return f'''
  <!-- box -->
  <polygon points="{BOX["left"]}" fill="url(#{p}Left)" stroke="url(#{p}Left)" stroke-width="10" stroke-linejoin="round"/>
  <polygon points="{BOX["right"]}" fill="url(#{p}Right)" stroke="url(#{p}Right)" stroke-width="10" stroke-linejoin="round"/>
  <polygon points="{BOX["rim"]}" fill="url(#{p}Rim)" stroke="url(#{p}Rim)" stroke-width="10" stroke-linejoin="round"/>
  <polygon points="{BOX["void"]}" fill="url(#{p}Void)"/>
  <g clip-path="url(#{p}Inner)"><ellipse cx="256" cy="300" rx="104" ry="60" fill="url(#{p}Glow)"/></g>

  <!-- falling in: blue pyramid, green cube, red sphere -->
  <g transform="{pyr_rot}">
    <polygon points="{layout.pyr["left"]}" fill="url(#{p}PyrL)"/>
    <polygon points="{layout.pyr["right"]}" fill="url(#{p}PyrR)"/>
  </g>
  <g transform="{cub_rot}">
    <polygon points="{layout.cub["left"]}" fill="url(#{p}CubeL)"/>
    <polygon points="{layout.cub["right"]}" fill="url(#{p}CubeR)"/>
    <polygon points="{layout.cub["top"]}" fill="url(#{p}CubeTop)"/>
  </g>
  <circle cx="{sph["cx"]}" cy="{sph["cy"]}" r="{sph["r"]}" fill="url(#{p}Sphere)"/>
  <ellipse cx="{sph["cx"] - sph["r"] // 3}" cy="{sph["cy"] - sph["r"] * 2 // 5}" rx="{sph["r"] // 4}" ry="{sph["r"] // 6}" fill="#FFFFFF" opacity=".45" transform="rotate(-28 {sph["cx"] - sph["r"] // 3} {sph["cy"] - sph["r"] * 2 // 5})"/>'''


def svg(body, defs_block, w=512, h=512):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"'
            f' role="img" aria-label="BoxMind">\n  <title>BoxMind</title>\n  <defs>{defs_block}\n  </defs>\n'
            f'{body}\n</svg>\n')


def write(name, text):
    (OUT / name).write_text(text, encoding="utf-8")
    print("wrote", name)


# ── primary mark ────────────────────────────────────────────────────────────
write("logo-mark.svg", svg(art("bm"), defs("bm")))

# ── compact mark for 16–64 px ───────────────────────────────────────────────
write("favicon-mark.svg", svg(
    f'  <g transform="translate(256 268) scale(1.08) translate(-256 -268)">{art("f", COMPACT)}\n  </g>',
    defs("f")))

# ── source for the PWA / apple-touch PNGs ───────────────────────────────────
write("icon-source.svg", svg(
    '  <rect width="512" height="512" fill="url(#iBg)"/>\n'
    f'  <g transform="translate(256 262) scale(0.8) translate(-256 -262)">{art("i")}\n  </g>',
    defs("i", background=True)))

# ── horizontal lockups ──────────────────────────────────────────────────────
S = 0.6404  # 406 px of solid artwork (y 64..470) -> 260 px tall
LOCKUP = ('  <g transform="translate({dx:.1f} {dy:.1f}) scale({s})">{art}\n  </g>\n'
          '  <text x="254" y="207" font-family="\'Space Grotesk\',\'Segoe UI\',\'Helvetica Neue\',Arial,sans-serif"'
          ' font-size="132" font-weight="600" letter-spacing="-3">\n'
          '    <tspan fill="{box}" textLength="196" lengthAdjust="spacingAndGlyphs">Box</tspan>'
          '<tspan fill="url(#wText)" textLength="292" lengthAdjust="spacingAndGlyphs">Mind</tspan>\n  </text>')

for name, box_colour, g0, g1 in [
    ("logo-wordmark-dark.svg", "#F2F5FA", "#8CA4FF", "#C6A9FF"),
    ("logo-wordmark-light.svg", "#161C2B", "#4D7CFE", "#8B5CF6"),
]:
    d = defs("w") + ('\n    <linearGradient id="wText" x1="0" y1="0" x2="1" y2="0">'
                     f'<stop offset="0" stop-color="{g0}"/><stop offset="1" stop-color="{g1}"/></linearGradient>')
    body = LOCKUP.format(dx=24 - 106 * S, dy=30 - 64 * S, s=S, art=art("w"), box=box_colour)
    write(name, svg(body, d, w=790, h=320))

# ── single colour ───────────────────────────────────────────────────────────
sph = FULL.sph
mono = f'''  <path fill-rule="evenodd" d="M256 200 406 287 256 374 106 287ZM256 221 370 287 256 353 142 287Z" opacity=".95"/>
  <polygon points="{BOX["right"]}" opacity=".72"/>
  <polygon points="{BOX["left"]}" opacity=".46"/>
  <g transform="rotate({FULL.tumble["pyr"][0]} {FULL.tumble["pyr"][1]} {FULL.tumble["pyr"][2]})">
    <polygon points="{FULL.pyr["left"]}" opacity=".6"/>
    <polygon points="{FULL.pyr["right"]}" opacity=".9"/>
  </g>
  <g transform="rotate({FULL.tumble["cub"][0]} {FULL.tumble["cub"][1]} {FULL.tumble["cub"][2]})">
    <polygon points="{FULL.cub["left"]}" opacity=".5"/>
    <polygon points="{FULL.cub["right"]}" opacity=".72"/>
    <polygon points="{FULL.cub["top"]}" opacity="1"/>
  </g>
  <circle cx="{sph["cx"]}" cy="{sph["cy"]}" r="{sph["r"]}" opacity=".88"/>'''
write("logo-mono.svg", (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512"'
    ' fill="currentColor" role="img" aria-label="BoxMind">\n  <title>BoxMind</title>\n'
    f'{mono}\n</svg>\n'))

# ── helper pages ────────────────────────────────────────────────────────────
# preview.html  : contact sheet, every variant at every size, light and dark
# render.html   : single icon at 2048 px, screenshotted to make the PNGs
mono_svg = (OUT / "logo-mono.svg").read_text(encoding="utf-8")
write("preview.html", """<!doctype html><meta charset="utf-8">
<style>
 body{margin:0;font:13px -apple-system,system-ui,sans-serif;background:#05070C;color:#F2F5FA;width:820px}
 .row{display:flex;gap:30px;padding:20px 24px;align-items:flex-end;flex-wrap:wrap}
 .light{background:#fff;color:#0A0D15}
 h3{margin:16px 24px 0;font-size:12px;letter-spacing:.1em;text-transform:uppercase;opacity:.55}
 .cap{margin-top:6px;font-size:10px;opacity:.5;text-align:center}
 svg.m{width:110px;height:110px}svg.s{width:44px;height:44px}
</style>
<h3>Primary mark</h3>
<div class="row">
 <div><img src="logo-mark.svg" width="190"><div class="cap">190</div></div>
 <div><img src="logo-mark.svg" width="96"><div class="cap">96</div></div>
 <div><img src="favicon-mark.svg" width="48"><div class="cap">fav 48</div></div>
 <div><img src="favicon-mark.svg" width="32"><div class="cap">32</div></div>
 <div><img src="favicon-mark.svg" width="16"><div class="cap">16</div></div>
 <div><img src="icon-source.svg" width="96" style="border-radius:21px"><div class="cap">app icon</div></div>
</div>
<div class="row light">
 <div><img src="logo-mark.svg" width="130"><div class="cap">on white</div></div>
 <div><img src="favicon-mark.svg" width="48"><div class="cap">48</div></div>
 <div><img src="favicon-mark.svg" width="16"><div class="cap">16</div></div>
</div>
<h3>Lockup</h3>
<div class="row"><img src="logo-wordmark-dark.svg" width="400"></div>
<div class="row light"><img src="logo-wordmark-light.svg" width="400"></div>
<h3>Mono</h3>
<div class="row" style="color:#F2F5FA">""" + mono_svg.replace("<svg ", '<svg class="m" ', 1)
      + mono_svg.replace("<svg ", '<svg class="s" ', 1) + """</div>
<div class="row light" style="color:#161C2B">""" + mono_svg.replace("<svg ", '<svg class="m" ', 1)
      + mono_svg.replace("<svg ", '<svg class="s" ', 1) + "</div>\n")

write("render.html", '<!doctype html><meta charset="utf-8">\n'
                     '<style>html,body{margin:0;padding:0;background:#05070C;overflow:hidden}'
                     'img{display:block}</style>\n'
                     '<img id="i" src="icon-source.svg" width="2048" height="2048">\n')
