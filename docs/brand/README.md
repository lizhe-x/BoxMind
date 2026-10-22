# BoxMind brand assets

An open isometric box with three geometric solids dropping into it — a blue
pyramid, a green cube, a red sphere. The sphere has already landed in the mouth
of the box; the other two are still in the air, tumbled a few degrees off the
isometric grid and drawn smaller the higher they are. That tilt and the size
falloff are what read as falling; an earlier attempt using motion streaks turned
into dark stubs on the dark background and was dropped.

Box colours come from the app's design tokens (`frontend/src/theme.ts`): the
brand gradient `#4D7CFE → #8B5CF6` for the walls, lighter tints for the rim,
`#070A14 → #161D33` for the interior. The falling solids deliberately sit
outside that palette so they carry the colour.

| File | Use |
|---|---|
| `logo-mark.svg` | primary mark, 512×512, transparent background |
| `favicon-mark.svg` | compact variant (larger solids, tucked closer) for 16–64 px — shipped as `frontend/public/favicon.svg` |
| `icon-source.svg` | mark on the app background, source for the PWA / apple-touch PNGs |
| `logo-wordmark-dark.svg` | horizontal lockup for dark backgrounds |
| `logo-wordmark-light.svg` | horizontal lockup for light backgrounds |
| `logo-mono.svg` | single colour, inherits `currentColor` — for print, stamps, fixed-palette favicons |

Generated from `icon-source.svg`:
`frontend/public/icon-512.png`, `icon-192.png`, `icon-180.png`.

## Regenerating

Every SVG comes out of one geometry definition:

```
python docs/brand/build.py
```

That also writes `preview.html` (contact sheet — every variant at every size, on
light and dark) and `render.html` (the icon at 2048 px). To redo the PNGs, serve
this directory, screenshot `render.html` at 512×512, and downscale to 512 / 192 / 180.

## Notes

- The lockup uses live `<text>` with a `Space Grotesk → Segoe UI → Helvetica Neue → Arial`
  stack. `textLength` is pinned on both tspans, so the lockup keeps its width even
  when the preferred font is missing.
- `logo-mono.svg` uses `fill="currentColor"`; it only picks up the surrounding colour
  when inlined in the DOM, not when loaded through `<img>`.
- Minimum size for the full mark is about 32 px. Below that the three solids blur
  into specks — still legible as a coloured box, but use `favicon-mark.svg`, where
  they are larger.
