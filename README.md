# rain-themes

Themes for Rain (a Bunny-based Discord mobile client mod), in the Bunny theme format (spec 2).

| Theme | Install URL |
|---|---|
| Gruvbox (dark, medium) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/gruvbox/gruvbox.json` |
| Solarized Osaka | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/solarized-osaka/solarized-osaka.json` |
| Nord Polar Night (nord9 accent) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/nord-polar-night/nord-polar-night.json` |
| Nord Frost (nord8 accent) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/nord-frost/nord-frost.json` |
| Tokyo Dark | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/tokyodark/tokyodark.json` |
| Dracula | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/dracula/dracula.json` |

Install: copy an install URL, then add it by URL in Rain's Themes settings.

Each folder also has `<slug>-preview.html` (a static colour mockup) and
`<slug>-notes.md` (palette, mapping, contrast checks).

Themes are generated from `<folder>/theme.spec.json` by `tools/build_theme.py`;
see [tools/README.md](tools/README.md).
