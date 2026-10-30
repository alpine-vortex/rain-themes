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
tools/rain degoog [--check]           # the degoog theme store repo (../degoog-rain)
tools/rain valenced [--check]         # the Valenced theme plugin repo (../valenced-rain)
tools/rain gui                        # the "Rain Themes" window
tools/rain install [--force]          # menu entry + login autostart + git commit/merge/push-to-main hooks (main checkout only)
```

Firefox and LibreWolf use the install-default profile unless another existing
profile directory is selected with `--firefox-profile PATH` or
`--librewolf-profile PATH`. Brave uses its configured `Default` profile unless
you select another existing `Preferences` file with `--brave-preferences PATH`.
Firefox and LibreWolf directories must contain `prefs.js`. Restore before
retargeting a browser while a desktop snapshot is active.

| Script | Role |
|---|---|
| `build_theme.py` | spec → Rain JSON, preview, notes |
| `desktop_export.py` | spec → `<slug>/desktop/*` |
| `apply_theme.py` | apply / restore / pending on this machine |
| `rain_gui.py` | the GTK window (runs `rain` subcommands) |
| `degoog_export.py` | app-theme exports → the degoog store repo (`rain degoog`) |
| `valenced_export.py` | Rain + app-theme exports → the Valenced plugin repo (`rain valenced`) |
| `gallery.py` | Playwright screenshots → GALLERY.md, index.html |
| `dev/preview_desktop.py` | screenshot a palette without applying it |
| `dev/degoog_preview.py` | store screenshots from a throwaway degoog |
| `dev/test_tooling.py` | acceptance tests for the hooks, install, restore, snapshot guard, phone and atomic writes (scratch dirs, fake gsettings/dconf/adb) |

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
- Contrast table (WCAG): body/strong/secondary/muted text on selected surfaces,
  links, composited mention/selection, focus indicators, interactive icons, and
  status text. Translucent surfaces are judged over a worst-case white image
  pixel. FAILs are reported, not fatal; upstream colors are not silently changed.
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
tools/apply_theme.py <slug> [--only gtk,icons,flatpak,wallpaper,terminal,claude-code,kitty,ghostty,gnome-text-editor,xed,geany,firefox,librewolf,brave,vesktop] [--dry-run]
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
| GNOME Terminal (and Claude Code's ANSI-only themes) | `gnome-terminal.json` | Profile "Rain <Name>" written with dconf (stable uuid5 id) and made default. |
| Claude Code | `claude-code-theme.json` | Custom theme (`base` dark + colour `overrides`) written as `~/.claude/themes/rain-themes.json`; `"theme": "custom:rain-themes"` set in `~/.claude/settings.json`. Skipped without `~/.claude`. |
| kitty | `kitty-theme.conf` | Written as `~/.config/kitty/current-theme.conf` (the file `kitten themes` writes); `include current-theme.conf` appended to `kitty.conf` in a `BEGIN/END_KITTY_THEME` block only if it isn't there. Running kitty reloads (SIGUSR1). Skipped without `~/.config/kitty`. |
| Ghostty | `ghostty-theme` | Written as `~/.config/ghostty/themes/rain-themes`; the last `theme =` line in `config.ghostty` (or the older `config`) becomes `theme = rain-themes`, or one is appended. Running Ghostty reloads (SIGUSR2). |
| GNOME Text Editor | `gtksourceview-<slug>.xml` | GtkSourceView 5 scheme (id `rain-<slug>`) into `~/.local/share/gtksourceview-5/styles/`, selected with gsettings `org.gnome.TextEditor style-scheme`. Text Editor must be closed (it loads schemes only at startup); skipped if its schema isn't installed. |
| Xed | `xed-<slug>.xml` | GtkSourceView 4 scheme (the Text Editor one without `<metadata>`) into `~/.local/share/xed/styles/`, gsettings `org.x.editor.preferences.editor scheme`. Xed must be closed. |
| Icon theme | `colloid.json` (`accent`) | The Yaru or Mint-Y colour variant nearest the accent, set in `org.cinnamon.desktop.interface icon-theme`; other icon themes are skipped. |
| Flatpak apps | none | `~/.themes:ro` and `xdg-config/gtk-4.0:ro` added to the user-wide override `~/.local/share/flatpak/overrides/global`. |
| Geany editor | `geany-<slug>.conf` | Into `~/.config/geany/colorschemes/`, `color_scheme=` in `geany.conf`. Geany must be closed. |
| Firefox | `userChrome.css`, `userContent.css` | Into the default profile's `chrome/`, plus the `toolkit.legacyUserProfileCustomizations.stylesheets` pref in `user.js`. Takes effect on the next Firefox start. Firefox's default theme also follows the GTK theme on Linux, so it matches even without these files. |
| LibreWolf | `userChrome.css`, `userContent.css` | The same, in the Flatpak's profile (`~/.var/app/io.gitlab.librewolf-community/.librewolf`). |
| Brave | `brave.json` | Sets the "Customize → colour" seed (`browser.theme.user_color2`), dark mode. Brave must be closed. |
| Vesktop | `<slug>.theme.css` | Into Vesktop's `themes/`, enabled in its settings. |
| Termius (phone) | `README.md` | Manual: pick the built-in named by the spec's `termius` block (`theme`, `match`: `same palette` or `closest`). Termius has no custom-theme import. |
| Android apps (phone) | `<slug>.app-theme.json` | app-theme v1 ([docs/app-theme.md](../docs/app-theme.md)). Imported in apps such as redeye (file, clipboard, or the raw.githubusercontent.com URL in the palette README; URLs work once on `main`). Format `app-theme` v1, agreed with the redeye session 2026-09-29. `state` (NSFW/hidden/saved) comes from the spec's `app_state`; `tags` are 8 muted hues from ANSI/syntax, avoiding accent/state/danger, in stable order. |
| Android system colours (phone) | `brave.json`'s seed, via `rain phone <slug>` | adb (Wireless debugging): writes the accent as the Material You seed into `secure theme_customization_overlay_packages` (`--style`, default TONAL_SPOT), copies wallpaper/Sync/redeye files to `/sdcard/Download/rain-themes/<slug>/`. `rain phone --restore` puts the original back. Snapshots and `phone-state.json` are per device (`ro.serialno`). |
| HeliBoard (phone) | `<slug>.heliboard.json`, `<slug>-light.heliboard.json` (+ `.heliboard-simple.json`) | Manual: HeliBoard → Appearance → Colors → Load (file or clipboard). The main files use its "all colors" format, setting all 44 `ColorType` slots (`HELIBOARD_ALL` in `desktop_export.py`; the name is stored as a base36 key with value 0). All-colors mode paints key backgrounds whatever the border setting, so keys use the keyboard background (the borderless look); the `-simple` files follow the border setting. The `-simple` files use the 10-colour format. Both match real HeliBoard exports; ints are signed ARGB. The light file exists only for palettes with a `light` block. |
| Sync for Reddit (phone) | `sync-theme.json` | Manual: copy the JSON and paste it into Sync's Monet theme import (clipboard only; confirmed working 2026-09-29). Seed = accent; dark primary/secondary/link text overridden. Sync derives backgrounds from the seed, so they aren't the palette's exact background. |
| Dark Reader, Niagara | `README.md` | Manual; the values are in the file. `wallpaper-phone.png` steers Android's Material You. |

The first apply on an unthemed desktop saves the current state to
`~/.local/state/rain-themes/snapshot.json` (gsettings, terminal profile list,
`~/.config/gtk-4.0`, Firefox files, Geany scheme, Brave colour, Vesktop enabled
themes); `--restore` puts back each part that still holds Rain's value, then
retires the snapshot. The GTK2 widget PNGs are pre-rendered by
Colloid and keep its stock colours.

## Valenced

All palettes as one theme plugin for [Valenced](https://github.com/Valenced/valenced),
published from the plugin repo
[valenced-rain](https://github.com/alpine-vortex/valenced-rain). Users add
`https://alpine-vortex.github.io/valenced-rain/index.json` as a repository in
Valenced. That repo is generated: change the specs or `valenced_export.py`
here, then export and commit there.

```sh
tools/rain valenced [--out ../valenced-rain]   # README.md, repo.config.json, export.lock, themes/rain/*
tools/rain valenced --check                    # exit 1 if the checkout is stale
```

- **Inputs.** Dark colours are read back from each `<slug>.json` (Rain stays the source of
  truth); the light flavour comes from `desktop/<slug>.app-theme.json`, mapped onto the
  same 25 roles (`light_roles()`), and the wallpaper is `desktop/wallpaper-phone.png`.
- **Modes.** Dark, Darker and Midnight get the palette. Light gets the light flavour, or
  the dark colours for the six palettes without one.
- **Groups.** *Rain Themes* is opaque; *Rain Themes with wallpaper* is the same palettes
  over their wallpaper.
- **Versions.** Valenced publishes a plugin version once, so a changed plugin needs
  a new `VERSION` in the exporter. `export.lock` records the version and a hash of the
  plugin files, and the export refuses to change them under the same version.
- **Publishing.** Pushing to `main` there runs the template's release workflow: Bun + Gradle
  build the ZIP into the `gh-pages` pool and regenerate `index.json`. It needs the
  `READ_PACKAGES_TOKEN` secret (a GitHub token with `read:packages`) and GitHub Pages on `gh-pages`.
- The rest of that repo (workflows, Gradle, `package.json`) was copied once from
  `Valenced/valenced-plugin-template` at `9a4f918` without its examples; `plan-releases`
  and `lint:types` point at `themes/` only.

## degoog

All palettes as one theme for [degoog](https://github.com/degoog-org/degoog),
published as the store repo
[degoog-rain](https://github.com/alpine-vortex/degoog-rain). That repo is
generated: change the specs or `degoog_export.py` here, then export and commit there.

```sh
tools/rain degoog [--out ../degoog-rain]   # write package.json, logo.png, README.md, themes/rain/*
tools/rain degoog --check                  # exit 1 if the store checkout is stale
python3 tools/dev/degoog_preview.py --url http://127.0.0.1:4455 --out ../degoog-rain/themes/rain/screenshots
```

The source is each palette's `desktop/<slug>.app-theme.json`, so run
`rain build` first. `style.css` has one block per palette keyed on
`html[data-rain-palette]`. degoog sets that attribute from the theme's
**Palette** select (`dataAttrsFromSettings`). The 15 palettes whose spec has a
`light` block also get `[data-theme="light"]` and `prefers-color-scheme: light`
blocks; the other six stay dark in light mode. The theme's `version` is
`1.0.0+<hash of the CSS and theme.json>`, so any colour change shows as an
update in the store. Low-contrast pairs in upstream light flavours are printed
as notes, not changed.

Screenshots need a throwaway degoog with the theme active and a search engine
installed (never a live instance):

```sh
docker run -d --name degoog-rain-test -e DEGOOG_SETTINGS_PASSWORDS=<random> \
  -p 127.0.0.1:4455:4444 -v <scratch>/data:/app/data ghcr.io/degoog-org/degoog:latest
# POST /api/settings/auth {password} (keep the cookie), then
# POST /api/store/repos {url}, /api/store/install {repoUrl, itemPath, type},
# /api/theme/active {id}; install engines/wikipedia + engines/duckduckgo the same way.
```
