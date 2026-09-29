# rain-themes

Themes for Rain (a Bunny-based Discord mobile client mod), in the Bunny theme format (spec 2).

| Theme | Install URL |
|---|---|
| Gruvbox (dark, medium) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/gruvbox/gruvbox.json` |
| Solarized Osaka | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/solarized-osaka/solarized-osaka.json` |

Install: copy an install URL, then add it by URL in Rain's Themes settings.

Each folder also has `<slug>-preview.html` (a static colour mockup) and
`<slug>-notes.md` (palette, mapping, contrast checks).

Themes are generated from `<folder>/theme.spec.json` by `tools/build_theme.py`;
see [tools/README.md](tools/README.md).
