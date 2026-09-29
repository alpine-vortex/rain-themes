# Tools

**Start here: `tools/rain`** is the single entry point; the other scripts are its parts.

```sh
tools/rain list                       # palettes; * = applied, "desktop" = has desktop exports
tools/rain build [slug ...]           # regenerate Rain + desktop outputs (all palettes by default)
tools/rain build --gallery            # ...plus GALLERY.md / index.html / README table
tools/rain check                      # fail if any generated file is stale (the pre-commit hook runs it on the staged tree)
tools/rain apply <slug> [--only gtk,terminal] [--dry-run]
tools/rain restore                    # undo what rain still owns; changes made since are left alone
tools/rain pending                    # finish apps that were open during apply (runs at login)
tools/rain preview <slug>             # screenshots in throwaway windows
tools/rain gui                        # the "Rain Themes" window
tools/rain install [--force]          # menu entry + login autostart + git pre-commit hook (main checkout only)
```

| Script | Role |
|---|---|
| `build_theme.py` | spec → Rain JSON, preview, notes |
| `desktop_export.py` | spec → `<slug>/desktop/*` |
| `apply_theme.py` | apply / restore / pending on this machine |
| `rain_gui.py` | the GTK window (runs `rain` subcommands) |
| `gallery.py` | Playwright screenshots → GALLERY.md, index.html |
| `dev/preview_desktop.py` | screenshot a palette without applying it |
| `dev/test_tooling.py` | acceptance tests for the hook, install, restore, snapshot guard, phone and atomic writes (scratch dirs, fake gsettings/dconf/adb) |

# Rain theme builder

Turns a palette spec into a Rain / Bunny (spec 2) theme, a static preview
mockup, and a notes file.

```sh
python3 tools/build_theme.py <theme-dir> [<theme-dir> ...]
```

Each theme folder holds a `theme.spec.json`; the script writes next to it:

| File | What |
|---|---|
| `<slug>.json` | the theme (host this at a raw URL, add by URL in Rain → Themes) |
| `<slug>-preview.html` | channel list + chat mockup, colours read only from the theme |
| `<slug>-notes.md` | palette, mapping table, derived shades, contrast table, spec notes |

Workflow for a new scheme: fetch the scheme's official palette → write
`<name>/theme.spec.json` (copy an existing one) → run the script → read the
FAIL/WARN lines and adjust roles.

## Checks the script enforces

- Every key in `reference_keys.json` (taken from the Maple-Blade theme) is filled,
  no key twice, no extra keys; valid JSON.
- No `background`: surfaces must be opaque 6-digit hex. With `background`:
  surfaces must be 8-digit (translucent). Text/icon colours are always 6-digit.
- Preview contains no colour outside its `:root` block and no undefined `var()`.
- Contrast table (WCAG): body text on each surface, text on composited
  mention/selected, links, button text on brand. Translucent surfaces are judged
  over a worst-case white image pixel. FAILs are reported, not fatal.
- Warns when brand and a status colour are within 20° of hue.

## Spec format

```jsonc
{
  "slug": "gruvbox",                 // output file prefix
  "name": "Gruvbox",
  "description": "...",
  "authors": ["rain-themes"],
  "source": "https://github.com/morhetz/gruvbox",
  "variant": "Dark · medium · accent: bright orange",   // preview subtitle
  "palette": { "dark0": "#282828", ... },               // the FULL official palette
  "palette_roles": { "dark0": "bg0; Normal background" }, // optional, shown in notes
  "roles": { ... all 25 role ids ... },
  "raw": { "BRAND_560": "...", "PRIMARY_630": "...", "PRIMARY_660": "...",
           "PRIMARY_700": "...", "PRIMARY_800": "..." },  // BRAND_500/530 default to brand/brand_bright
  "background": { "url": "https://...", "blur": 0, "alpha": 0.7 },  // optional
  "preview": { "server_name": "...", "users": [5 names], "me": "...", ... }, // optional text
  "notes": ["variant/accent choices, substitutions, ..."]           // copied to notes.md
}
```

Colour refs (in `roles` and `raw`):

- `"dark0"`: a palette colour
- `"bright_orange@33"`: palette colour + hex alpha
- `{"mix": ["bright_orange", "light0", 0.333]}`: derived shade (weight of the 2nd
  colour); optional `"alpha": "E0"`. Derived shades are listed in the notes automatically.

Role ids: `main_bg secondary_bg tertiary_bg floating_bg nested_floating_bg
input_bg hover active faint selected text_strong text_normal text_secondary
text_muted interactive_muted brand brand_bright text_on_brand link danger
positive warning mention mention_hover backdrop`. The key lists for each are in
`GROUPS` at the top of `build_theme.py`.

## Gallery

```sh
python3 tools/gallery.py
```

Screenshots every theme's preview to `<slug>/<slug>-preview.png`, then writes
`GALLERY.md` and `index.html` at the repo root and refreshes the theme table in
`README.md`. Run it after adding or changing a theme.

## Desktop exports (Linux Mint / Cinnamon)

The same palette, applied to the desktop and the apps around it.

```sh
python3 tools/desktop_export.py <theme-dir> ...   # writes <theme-dir>/desktop/
tools/apply_theme.py <slug> [--only gtk,wallpaper,terminal,geany,firefox,brave,vesktop] [--dry-run]
tools/apply_theme.py --restore                    # back to the settings in the snapshot
```

A theme is exported only when its spec has three extra blocks; the others are
skipped:

```jsonc
"ansi_source": "https://...",          // where ansi/syntax came from
"ansi": [16 colour refs],               // black red green yellow blue magenta cyan white, then brights
"terminal": {"background": "...", "foreground": "...", "cursor": "...", "selection": "..."},
"syntax": {"comment": "...", "string": "...", "number": "...", "constant": "...", "keyword": "...",
           "storage": "...", "type": "...", "class": "...", "function": "...", "parameter": "...",
           "operator": "...", "builtin": "...", "tag": "...", "attribute": "...", "preprocessor": "...",
           "error": "...", "added": "...", "removed": "...", "changed": "..."}
```

Refs are palette names (with `@AA` alpha, flattened over `main_bg`) or literal
`#RRGGBB`. Everything else comes from `roles`. `terminal` may also set
`cursor_text` (the text under a block cursor); it defaults to `background`.
Selected text is always drawn in `foreground`, so `selection` must be a dark
colour even where upstream uses a light one with dark selected text.

| Target | Export | How `apply_theme.py` applies it |
|---|---|---|
| Cinnamon, GTK 2/3/4, window borders (Nemo, Geany chrome) | `colloid-palette.scss`, `colloid.json` | Rebuilds [Colloid](https://github.com/vinceliuice/Colloid-gtk-theme) (GPL-3, pinned commit, cloned to `~/.cache/rain-themes`) as `~/.themes/Rain-<Name>-Dark`, sets the three Cinnamon theme keys, links a compiled libadwaita stylesheet into `~/.config/gtk-4.0` (what Colloid's `-l` would install). |
| Wallpaper | `wallpaper-desktop.png` | Copied to `~/.local/share/backgrounds/rain-themes/`, set via gsettings. |
| GNOME Terminal (and Claude Code via `/theme` → ANSI) | `gnome-terminal.json` | Profile "Rain <Name>" written with dconf (stable uuid5 id) and made default. |
| Geany editor | `geany-<slug>.conf` | Into `~/.config/geany/colorschemes/`, `color_scheme=` in `geany.conf`. Geany must be closed. |
| Firefox | `userChrome.css`, `userContent.css` | Into the default profile's `chrome/`, plus the `toolkit.legacyUserProfileCustomizations.stylesheets` pref in `user.js`. Takes effect on the next Firefox start. Firefox's default theme also follows the GTK theme on Linux, so it matches even without these files. |
| Brave | `brave.json` | Sets the "Customize → colour" seed (`browser.theme.user_color2`), dark mode. Brave must be closed. |
| Vesktop | `<slug>.theme.css` | Into Vesktop's `themes/`, enabled in its settings. |
| Termius (phone) | `README.md` | Manual: pick the built-in named by the spec's `termius` block (`theme`, `match`: `same palette` or `closest`). Termius has no custom-theme import. |
| Android apps (phone) | `<slug>.app-theme.json` | app-theme v1 ([docs/app-theme.md](../docs/app-theme.md)). Imported in apps such as redeye (file, clipboard, or the raw.githubusercontent.com URL in the palette README; URLs work once on `main`). Format `app-theme` v1, agreed with the redeye session 2026-09-29. `state` (NSFW/hidden/saved) comes from the spec's `app_state`; `tags` are 8 muted hues from ANSI/syntax, avoiding accent/state/danger, in stable order. |
| Android system colours (phone) | `brave.json`'s seed, via `rain phone <slug>` | adb (Wireless debugging): writes the accent as the Material You seed into `secure theme_customization_overlay_packages` (`--style`, default TONAL_SPOT), copies wallpaper/Sync/redeye files to `/sdcard/Download/rain-themes/<slug>/`. `rain phone --restore` puts the original back. Snapshots and `phone-state.json` are per device (`ro.serialno`). |
| HeliBoard (phone) | `<slug>.heliboard.json`, `<slug>-light.heliboard.json` (+ `.heliboard-simple.json`) | Manual: HeliBoard → Appearance → Colors → Load (file or clipboard). The main files use its "all colors" format, setting all 44 `ColorType` slots (`HELIBOARD_ALL` in `desktop_export.py`; the name is stored as a base36 key with value 0). All-colors mode paints key backgrounds whatever the border setting, so keys use the keyboard background (the borderless look); the `-simple` files follow the border setting. The `-simple` files use the 10-colour format. Both match real HeliBoard exports; ints are signed ARGB. The light file exists only for palettes with a `light` block. |
| Sync for Reddit (phone) | `sync-theme.json` | Manual: copy the JSON and paste it into Sync's Monet theme import (clipboard only; confirmed working 2026-09-29). Seed = accent; dark primary/secondary/link text overridden. Sync derives backgrounds from the seed, so they aren't the palette's exact background. |
| Dark Reader, Niagara, Claude Code | `README.md` | Manual; the values are in the file. `wallpaper-phone.png` steers Android's Material You. |

The first apply on an unthemed desktop saves the current state to
`~/.local/state/rain-themes/snapshot.json` (gsettings, terminal profile list,
`~/.config/gtk-4.0`, Firefox files, Geany scheme, Brave colour, Vesktop enabled
themes); `--restore` puts back each part that still holds Rain's value, then
retires the snapshot. The GTK2 widget PNGs are pre-rendered by
Colloid and keep its stock colours.
