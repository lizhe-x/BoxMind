# BoxMind brand assets

A closed shipping box seen from the front-right, with a strip of tape over the top and down the front and an
amber label tag hanging from the top-right corner. It says "every box has a name and a list". The box walls use
the app's brand gradient (`#5584FF → #8B5CF6`, `frontend/src/theme.ts`), the tag sits outside that palette so
it carries the colour. Adopted 2026-10-22; the earlier mark (an open box with three falling solids) read as a
clown nose at small sizes. The other directions considered are in `candidates/`.

| File | Use |
|---|---|
| `logo-mark.svg` | primary mark, 512×512, transparent background |
| `favicon-mark.svg` | the mark cropped tight, for 16–64 px — shipped as `frontend/public/favicon.svg` |
| `icon-source.svg` | mark on the app background with a ground shadow, 512×512 |
| `app-icon-1024.svg` | same at 1024×1024, source of `ios/BoxMind/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png` and the PWA PNGs |
| `logo-wordmark-dark.svg` / `logo-wordmark-light.svg` | horizontal lockups |
| `logo-mono.svg` | single colour, inherits `currentColor` — for print, stamps, fixed-palette favicons |

Generated from `app-icon-1024.svg`: the iOS app icon (opaque PNG), `frontend/public/icon-512.png`, `icon-192.png`, `icon-180.png`.

## Regenerating

Every SVG comes out of one geometry definition:

```
python docs/brand/build.py
```

That also writes `preview.html` (contact sheet at 16–256 px on light and dark, wordmarks, mono) and
`render.html` (the icon at 1024 px). To redo the PNGs on a Mac without an SVG rasteriser:

```
qlmanage -t -s 1024 -o out docs/brand/app-icon-1024.svg     # QuickLook renders SVG → out/app-icon-1024.svg.png
```

then flatten to RGB (the App Store rejects alpha in the 1024 icon) and downscale with Pillow or `sips`.

## Notes

- The tag is placed by the position of its hole, so the string always meets it; move `TAG_AT` and the string together.
- `favicon-mark.svg` is only a tighter viewBox on the same art; at 16 px the tag is what identifies the mark.
- `logo-mono.svg` knocks the tag's hole and lines out in white; on a dark surface they disappear, which is acceptable.
