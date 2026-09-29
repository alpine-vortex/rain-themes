# Design notes

How the desktop side works, why it's built this way, and what was found along
the way, including the dead ends, so they don't get re-investigated. The Rain
(mobile) side is covered in [../tools/README.md](../tools/README.md).

## Principles

- **The spec is the only source.** Every output is generated; nothing is
  hand-edited. Colour choices happen in `theme.spec.json` (`roles`, `ansi`,
  `terminal`, `syntax`), not in the exporters.
- **Colours come from the palette's upstream.** ANSI and syntax colours are
  copied from the palette's own published files (the URL goes in
  `ansi_source`), not invented.
- **Outputs are committed, third-party builds are not.** `<slug>/desktop/*` is
  small and ours, so it's in git. The compiled Colloid theme is GPL-3 and
  large, so it's built on the machine at apply time from a pinned upstream
  commit.
- **Applying is reversible.** The first apply snapshots everything it will
  touch. Nothing is deleted without a backup.
- **Don't fight apps that own their config.** Apps that rewrite their config on
  exit are skipped while running rather than raced.

## Pipeline

1. `build_theme.py` resolves the spec's `roles` into the Rain JSON. Unchanged by
   the desktop work; the extra spec keys are ignored by it.
2. `desktop_export.py` imports `Resolver`, `GROUPS`, `mix`, `over` from
   `build_theme.py`, so there's no second resolver. It flattens every
   translucent role over `main_bg`, because desktop formats want opaque hex.
   Then it writes `<slug>/desktop/`.
3. `apply_theme.py` reads only `<slug>/desktop/`, never the spec.

Exports are only produced for specs with all of `ansi`, `terminal` and
`syntax`. Other specs are skipped, which keeps the rest of the repo building
unchanged.

## Colloid (Cinnamon + GTK)

**Why Colloid:** it's by the same author as Orchis (a common Mint theme),
supports Cinnamon, GTK 2/3/4, libadwaita and window borders, and already swaps
palettes through Sass variables. Its installer ships Nord/Dracula/Gruvbox/
Everforest/Catppuccin variants. Recolouring compiled CSS instead was rejected:
Mint-Y-Dark's compiled files have 88 (Cinnamon) and 176 (GTK) distinct colours,
many blended.

**How the build works** (`build_gtk` in `apply_theme.py`):

1. Copy the cached clone (pinned `COLLOID_COMMIT`) to a temp dir. The installer
   writes temp files into `src/`, so never run it in the cache itself.
2. Overwrite `src/sass/_color-palette-default.scss` with our palette. We take
   over the *default* scheme rather than adding a new name, so none of
   `install.sh` / `assets.sh` / `gtkrc.sh` needs patching.
3. Set `$colortype: 'fixed'` in `_tweaks.scss`. This only matters to the
   libadwaita and gnome-shell Sass; without it libadwaita uses the system
   accent.
4. Run `install.sh -d <tmp> -n Rain-<Name> -c dark -t default`. **Never pass
   `-l`**: it `rm -rf`s `~/.config/gtk-4.0/{assets,gtk.css,gtk-dark.css}` on the
   live system.
5. Compile `src/main/libadwaita/libadwaita-Dark.scss` into the theme's
   `libadwaita/gtk.css`. That's what `-l` would install; apply links it into
   `~/.config/gtk-4.0/` after the snapshot.
6. Swap Colloid's stock hex values in the pre-drawn assets (svg, gtkrc,
   metacity xml, thumbnails) in **one regex pass** with a dict. Chained `sed`
   could re-hit a colour it just wrote. The stock values are the `STOCK`
   pattern plus `colloid.json`'s `swap` map.
7. Copy only `Rain-<Name>-Dark`. The `-hdpi`/`-xhdpi` siblings are Xfce window
   borders only.

**Palette mapping** (`colloid()` in `desktop_export.py`). In the dark variant
Colloid reads:

| Colloid variable | Used for | Our role |
|---|---|---|
| `$grey-700` | window/view background | `main_bg` |
| `$grey-750` | titlebar, sidebar | `secondary_bg` |
| `$grey-800` | panel, OSD | `tertiary_bg` |
| `$grey-650` | cards/surfaces | `floating_bg` |
| `$grey-050…600` | assorted light greys | interpolated `text_strong` → `nested_floating_bg` |
| `$grey-850…950` | deeper shades | `tertiary_bg` darkened |
| `$white` | **all text** (`on($background)` returns it) | `text_strong` |
| `$black` | shadows, text on light accents | `tertiary_bg` darkened |
| `$default-light` | **the accent** | `brand` |
| `$links` | links | `link` |
| `$button-close/max/min` | window buttons | `danger` / `positive` / `warning` |
| `$red-light` etc. | status colours | bright ANSI colours; orange from the palette's `orange`/`peach` |

**Known limits:** GTK2 widget PNGs are pre-rendered and keep Colloid's colours
(barely matters; almost nothing uses GTK2). The metacity button images are
neutral grey SVGs, and the titlebar colours come from the GTK theme via
`gtk:custom`.

## GNOME Terminal

- Profiles are dconf keys under `/org/gnome/terminal/legacy/profiles:/:<uuid>/`.
  Valid key names come from `gsettings list-recursively
  org.gnome.Terminal.Legacy.Profile:<path>`.
- A profile only appears in the UI if its uuid is in `profiles:/list`. On
  the development machine, `list` and `default` were **unset**, meaning the implicit profile
  `b1dcc9dd-…` from the schema default. So apply writes the list explicitly,
  keeping existing ids, and `--restore` *resets* the keys rather than writing
  empty values.
- The uuid is `uuid5(NAMESPACE_URL, "rain-themes/<slug>")`, so re-applying
  updates the same profile instead of adding duplicates.
- Claude Code needs no export. Its ANSI-only theme uses the terminal palette.

## Geany

A standard `.conf` scheme generated from the shape of the shipped
`/usr/share/geany/colorschemes/alt.conf`, so every named style is present.
Selected with `color_scheme=` in `~/.config/geany/geany.conf`, which Geany
rewrites on exit. Hence the running check.

## Firefox

- **No add-on.** Release Firefox only permanently installs Mozilla-signed
  add-ons, so a generated theme add-on can't be installed by a script.
  `userChrome.css` + `userContent.css` with
  `toolkit.legacyUserProfileCustomizations.stylesheets` works and is fully
  scriptable.
- **Variable names change between versions.** Firefox 156 uses design-system
  tokens (`--toolbox-background-color`, `--toolbar-background-color`,
  `--toolbar-field-*`, `--panel-background-color`, `--color-accent-primary`, …);
  the older `--lwt-*` / `--toolbar-bgcolor` names are mostly dead. To re-derive
  them after an update:

  ```sh
  mkdir /tmp/omni && cd /tmp/omni
  unzip -qo /usr/lib/firefox/browser/omni.ja 'chrome/browser/skin/*' 'chrome/browser/content/browser/*.css'
  unzip -qo /usr/lib/firefox/omni.ja 'chrome/toolkit/skin/classic/global/*'
  grep -rhoE -- '--(toolbar|toolbox|urlbar|panel|tab)[a-z0-9-]*:' . | sort | uniq -c | sort -rn
  ```
- **Some tokens can't be overridden from `:root`.** Firefox defines them in
  cascade layers on `:root, :host` and inside the default theme's
  `-moz-native-theme` media blocks. So userChrome also sets the variables on
  the elements themselves (`#nav-bar`, `.urlbar`, `panel`, …) and adds direct
  rules for the toolbox, nav bar, tabs and `.urlbar-background`. The URL bar is
  `.urlbar` / `.urlbar-background` (classes), not the old `#urlbar-background`.
- On Linux the default "System theme" takes its toolbar colours from GTK (e.g.
  `--toolbox-background-color: ActiveCaption`), so the Colloid theme alone gets
  Firefox most of the way.
- **Icons need their own colour.** Toolbar icons use `--toolbarbutton-icon-fill`,
  and an active theme (e.g. the Firefox Color extension's default theme, which
  is green) sets it separately from text. userChrome sets it explicitly.
- **Firefox Color link** (`firefox-color.json`): Firefox Color's share URLs are
  `?theme=` + json-url's `lzma` codec = msgpack → LZMA "alone" (preset 9) →
  URL-safe base64 without padding. `desktop_export.py` has a tiny msgpack
  encoder, so no Node is needed. Verified by decoding with `json-url@2.3.4`.
  Firefox for Android has no theme support at all.
- The profile is `Default=` in `~/.mozilla/firefox/installs.ini`, not
  `profiles.ini` (a machine can have several profiles).
- Verified by screenshot in a throwaway `--no-remote --profile` instance; see
  `tools/dev/preview_desktop.py`.

## Brave (Brave Origin)

- Prefs: `~/.config/BraveSoftware/Brave-Origin/Default/Preferences` (JSON, one
  line). The theme is `browser.theme.{user_color2, color_scheme2,
  color_variant2}` with `extensions.theme.id = "user_color_theme_id"`.
  `user_color2` is a signed 32-bit ARGB int (`argb_int()`).
  `color_scheme2: 2` = dark.
- None of these are MAC-protected in `Secure Preferences` (its `protection.macs`
  was checked and doesn't list them), so a plain edit survives. Not yet
  confirmed by relaunching Brave.
- A seed colour gives an approximation (Chromium generates a Material palette
  from it). The alternative is Brave's GTK mode, which follows Colloid. Its
  pref key hasn't been verified, so it isn't scripted; the way to find it is to
  toggle it in the UI and diff `Preferences`.

## Vesktop

- The CSS is the Rain theme's own semantic/raw colours as Discord CSS
  variables: `BACKGROUND_PRIMARY` → `--background-primary`, `BRAND_500` →
  `--brand-500`. Desktop and mobile Discord therefore get the same mapping.
- Discord redefines its variables on `.theme-dark` and the visual-refresh
  classes, so the block targets those selectors too, with `!important`.
- Paths: `~/.config/vesktop/` (native) or
  `~/.var/app/dev.vencord.Vesktop/config/vesktop/` (Flatpak).
  `settings/settings.json` → `enabledThemes`. **Unverified**: Vesktop wasn't
  installed when this was written. Confirm the variable names in DevTools and
  the settings path on first use.

## Wallpapers and the phone

- Wallpapers are drawn with Pillow: a `tertiary_bg`→`main_bg` gradient, one
  large blurred `brand` field and one smaller `link` field. The phone version
  (1440×3200) gives the accent more area on purpose, because Android's Material
  You picks seed colours by chroma × area.
- **Niagara Launcher can't be generated.** It has no hex colour picker: Theme
  colour offers three wallpaper-derived swatches plus nine fixed "Standard"
  ones (sampled into `NIAGARA_SWATCHES`). Its `.nlt` export is an 8-byte header
  (`NLT\0` + version 1) followed by high-entropy bytes. It isn't
  zlib/gzip/zstd/brotli/lzma/bz2 and looks encrypted. Reverse-engineering the
  app for the key was rejected (likely against its terms, and fragile). The
  approach instead: wallpaper + swatch by hand, then commit the exported `.nlt`.
- Rain (phone Discord) needs **raw** GitHub URLs. `blob/` URLs return HTML.

## One entry point, pending queue, GUI

- `tools/rain` wraps everything. `rain check` builds every palette into a temp
  dir (Rain + desktop, desktop reading the *fresh* Rain JSON) and compares
  bytes with the committed files. It also flags files in `desktop/` that
  nothing generates, except hand-exported `.nlt` files. It's the git
  pre-commit hook.
- `~/.local/state/rain-themes/state.json` holds `current` (last palette applied
  with at least gtk+terminal) and `pending` (`{target: slug | "restore"}`).
  Geany and Brave go to `pending` when running; `rain pending` finishes them
  and runs from `~/.config/autostart/` at login, before those apps start.
- `rain_gui.py` has no logic of its own: every button runs a `rain` subcommand
  via `Gio.Subprocess` and streams its output into the log pane. Keep new
  behaviour in `apply_theme.py` / `rain` so the CLI and GUI stay the same.

## Snapshot / restore

The snapshot is taken on the first apply only, at
`~/.local/state/rain-themes/snapshot.json`, with copies of replaced files under
`files/`. It records:
- the 3 Cinnamon theme settings and the wallpaper
- the terminal `list` and `default` keys (empty = unset)
- `~/.config/gtk-4.0/{gtk.css,gtk-dark.css,assets}`
- Firefox `user.js` and the `chrome/` files
- Geany's `color_scheme`
- Brave's `browser.theme`
- Vesktop's `enabledThemes`

To make a new baseline (e.g. after deliberately changing the "normal"
desktop), delete the snapshot; the next apply takes a fresh one.

The icon theme is never changed, so it isn't
recorded. `~/.config/gtk-3.0/gtk.css` is never written; if one exists it
overrides every GTK3 theme, which is worth checking when colours look wrong.
