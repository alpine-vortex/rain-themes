# rain-themes

<img src="assets/icon/rain-themes-128.png" alt="" width="96" align="right">

One colour palette, themed everywhere. Each of the **21 dark palettes** here
(Catppuccin, Dracula, Everforest, Gruvbox, Kanagawa, Librekai/Monokai, Nord,
Rosé Pine, Solarized Osaka, Tokyo Night, Tokyodark) is generated from a single
spec into matching themes for:

- **Discord on Android**: a [Rain](#discord-on-android-rain) theme (Bunny theme
  format, spec 2). This is where the repo started.
- **The Linux Mint desktop**: Cinnamon/GTK, wallpaper, terminal, editor,
  browsers and Discord, applied and undone with one command or the
  **Rain Themes** app.
- **The Android phone**: system colours (Material You), Sync for Reddit,
  Termius, redeye and Niagara Launcher.

All 21 palettes have generated exports for the targets listed below. Runtime
availability depends on the apps installed on the machine; see the desktop
guide and status page for scope and verification limits. Specs record source
URLs and adaptation notes, but those URLs are not all pinned to immutable
upstream revisions.

See the **[gallery](GALLERY.md)** for previews of every Discord theme side by side.

## What each palette provides

| Where | Target | How it's applied |
|---|---|---|
| Phone | Discord (Rain) | Add the install URL below in Rain's Themes settings |
| Phone | Discord (Valenced) | Add the Rain Themes plugin repository (below), or import the Rain URL with Legacy Themes |
| Phone | System colours (Material You) | `tools/rain phone <slug>` over adb: the accent becomes the system seed |
| Phone | Wallpaper, Niagara Launcher | `wallpaper-phone.png` (pushed by `rain phone`), plus a Niagara swatch hint |
| Phone | Sync for Reddit | Paste `sync-theme.json` into Sync's Monet theme import |
| Phone | Android apps (e.g. redeye) | `<slug>.app-theme.json` ([format](docs/app-theme.md)): file, clipboard, raw URL or adb |
| Phone | HeliBoard keyboard | `<slug>.heliboard.json` (+ `-light`, all 44 colours; `-simple` = 10): Colors → Load, from a file or the clipboard |
| Phone | Termius | The matching built-in theme, named in the palette's README |
| Phone | Firefox (web pages) | Dark Reader values in the palette's README |
| Desktop | Cinnamon, GTK 2/3/4, window borders | A recoloured [Colloid](https://github.com/vinceliuice/Colloid-gtk-theme) build |
| Desktop | Wallpaper | `wallpaper-desktop.png` |
| Desktop | GNOME Terminal (and Claude Code) | A "Rain <Name>" profile; Claude Code follows it via `/theme` → ANSI colours only |
| Desktop | Geany | Editor colour scheme |
| Desktop | Firefox | `userChrome.css` / `userContent.css`, plus a Firefox Color link for other machines |
| Desktop | Brave | Theme seed colour |
| Desktop | Vesktop (Discord) | A Vencord theme reusing the Rain mapping |
| Desktop | ChatGPT and other sites | Dark Reader values in the palette's README |

Per palette, `<slug>/` holds the Rain theme (`<slug>.json`), a colour mockup
(`<slug>-preview.html`) and notes (`<slug>-notes.md`: mapping and contrast
checks). `<slug>/desktop/` holds every desktop and phone export plus a
`README.md` with the manual steps and values.

## Palettes

<!-- themes -->
| Theme | Install URL |
|---|---|
| [Catppuccin Frappé](GALLERY.md#catppuccin-frappe) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/catppuccin-frappe/catppuccin-frappe.json` |
| [Catppuccin Macchiato](GALLERY.md#catppuccin-macchiato) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/catppuccin-macchiato/catppuccin-macchiato.json` |
| [Catppuccin Mocha](GALLERY.md#catppuccin-mocha) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/catppuccin-mocha/catppuccin-mocha.json` |
| [Dracula](GALLERY.md#dracula) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/dracula/dracula.json` |
| [Everforest Dark](GALLERY.md#everforest-dark) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/everforest-dark/everforest-dark.json` |
| [Gruvbox](GALLERY.md#gruvbox) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/gruvbox/gruvbox.json` |
| [Gruvbox Material Dark](GALLERY.md#gruvbox-material-dark) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/gruvbox-material-dark/gruvbox-material-dark.json` |
| [Kanagawa Dragon](GALLERY.md#kanagawa-dragon) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/kanagawa-dragon/kanagawa-dragon.json` |
| [Kanagawa Wave](GALLERY.md#kanagawa-wave) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/kanagawa-wave/kanagawa-wave.json` |
| [Librekai](GALLERY.md#librekai) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/librekai/librekai.json` |
| [Librekai Dimmed](GALLERY.md#librekai-dimmed) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/librekai-dimmed/librekai-dimmed.json` |
| [Librekai Refined](GALLERY.md#librekai-refined) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/librekai-refined/librekai-refined.json` |
| [Nord Frost](GALLERY.md#nord-frost) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/nord-frost/nord-frost.json` |
| [Nord Polar Night](GALLERY.md#nord-polar-night) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/nord-polar-night/nord-polar-night.json` |
| [Rosé Pine](GALLERY.md#rose-pine) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/rose-pine/rose-pine.json` |
| [Rosé Pine Moon](GALLERY.md#rose-pine-moon) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/rose-pine-moon/rose-pine-moon.json` |
| [Solarized Osaka](GALLERY.md#solarized-osaka) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/solarized-osaka/solarized-osaka.json` |
| [Tokyo Dark](GALLERY.md#tokyodark) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/tokyodark/tokyodark.json` |
| [Tokyo Night Moon](GALLERY.md#tokyonight-moon) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/tokyonight-moon/tokyonight-moon.json` |
| [Tokyo Night Night](GALLERY.md#tokyonight-night) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/tokyonight-night/tokyonight-night.json` |
| [Tokyo Night Storm](GALLERY.md#tokyonight-storm) | `https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/tokyonight-storm/tokyonight-storm.json` |
<!-- /themes -->

## Discord on Android (Rain)

Copy an install URL from the table above, then add it by URL in Rain's Themes
settings. Rain needs the `raw.githubusercontent.com` URL; `github.com/.../blob/`
links fail with "Failed to fetch theme".

### Valenced

[Valenced](https://github.com/Valenced/valenced) (Rain + Revenge) has two routes:

- **Rain Themes plugin (recommended).** In **Settings → Valenced → Plugins**, add the
  repository `https://alpine-vortex.github.io/valenced-rain/index.json`, then install
  **Rain Themes**. Every palette appears in the theme picker, under *Rain Themes* or
  *Rain Themes with wallpaper*, and updates arrive on their own. Discord's Light mode
  uses the palette's official light flavour where it has one.
- **Legacy Themes.** Install **Legacy Themes** from the preinstalled community
  repository and import a raw install URL from the table above. All 21 pass its
  parser. An import is a one-time copy that doesn't update, and it only colours
  Dark, Darker and Midnight, so keep Discord on a dark appearance.

## Desktop (Linux Mint / Cinnamon)

**App:** run `tools/rain install` once, then open **Rain Themes** from the menu
(it can be pinned to the panel). Search the palette list, then select a palette
to see its wallpaper, colour swatches and whether it is applied. **Apply to
desktop** applies it; **Preview** opens screenshots in temporary windows and
changes nothing. Phone controls are grouped in the **Phone** section. **Activity**
shows command output, **Finish pending** appears when an app change is waiting,
and desktop restore is under the header menu. The layout stacks the list above
the preview in a narrow window. Use **Ctrl+F** to search and **Escape** to clear
the search.

**Terminal:**

```sh
tools/rain list                          # palettes, and which is applied
tools/rain apply librekai --dry-run      # show what would change
tools/rain apply librekai                # apply to every desktop target
tools/rain apply librekai --only gtk,terminal
tools/rain restore                       # back to the setup before the first apply
tools/rain pending                       # finish apps that were open (Geany, Brave); also runs at login
tools/rain preview librekai              # screenshots only
```

The first apply saves a snapshot of the original setup, and `restore` always
returns to it. Details, manual steps and troubleshooting are in the
[desktop guide](docs/desktop-guide.md).

## Phone (Android)

With the phone connected over Wireless debugging (Developer options):

```sh
tools/rain phone librekai                  # system colours + files to Download/rain-themes/librekai/
tools/rain phone librekai --style VIBRANT  # Material You style; VIBRANT stays closest to the accent
tools/rain phone --restore                 # original system colour setting
```

This writes the same system setting as Settings → Wallpaper & style, with no
root; tested on stock Android 17 (vendor skins such as Samsung One UI may ignore it). Setting the
wallpaper and importing into Sync (paste the JSON) are taps on the phone. Each
palette's `desktop/README.md` names its Termius built-in, Niagara swatch and
Dark Reader values.

## How it works

```
<slug>/theme.spec.json ── build_theme.py ──▶ <slug>.json (Rain)
         │                                        │
         └────────── desktop_export.py ◀──────────┘
                            │
                            ▼
                    <slug>/desktop/* ── rain apply ──▶ Mint desktop and apps
                                     ── rain phone ──▶ Android (adb)
```

- **Spec:** one `theme.spec.json` per palette is the single source of truth:
  official colours, a role mapping, and terminal/syntax colours with their
  upstream source.
- **`tools/rain`** is the one entry point: `build`, `check`, `apply`,
  `restore`, `pending`, `preview`, `phone`, `gui`, `install`.
- **Generated files are never hand-edited.** `rain check` (also run by the
  commit, merge and push-to-main hooks) fails if any output is stale.

Requirements: Python 3 with PyGObject/GTK 3 and Pillow, `sassc` (Colloid
build), `dconf`/`gsettings` (Cinnamon), and `adb` for the phone. Playwright is
needed only for `rain build --gallery`.

## Documentation

- [docs/desktop-guide.md](docs/desktop-guide.md): using it, undoing it, and
  troubleshooting.
- [docs/design.md](docs/design.md): how each target works and why.
- [docs/app-theme.md](docs/app-theme.md): the app-theme format for Android apps, which
  this repo owns.
- [docs/status.md](docs/status.md): what's verified, known issues and next
  steps.
- [tools/README.md](tools/README.md): spec format and script reference.
