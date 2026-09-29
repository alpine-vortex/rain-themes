# Desktop guide

How to put one palette on the whole Linux Mint (Cinnamon) desktop and the apps
around it, and how to get back. Written for Linux Mint with Cinnamon (GNOME
Terminal, Firefox, Brave Origin, Geany); paths assume that setup.

Palettes with desktop exports so far: **Librekai**, **Catppuccin Mocha**
(folders with a `desktop/` directory). Others need their spec extended first.
See [status.md](status.md).

## Quick start

**GUI:** open **Rain Themes** from the Cinnamon menu (or `tools/rain gui`).
Each palette card has a wallpaper thumbnail, colour swatches, **Apply**,
**Preview** and **Phone**. The header has **Restore original** and **Finish
pending**, and the *Phone (adb)* row has the Material You style picker and
**Restore phone**. The app has its own icon and can be pinned to the panel.

**Terminal:**

```sh
cd ~/github/rain-themes
tools/rain apply librekai --dry-run   # show what would change
tools/rain apply librekai             # do it
tools/rain restore                    # undo everything
tools/rain list                       # what's available / applied
```

Geany and Brave rewrite their config files on exit, so while they're open
their part is **queued** instead of applied. It's finished by **Finish pending**
in the GUI, by `tools/rain pending`, or automatically at the next login (an
autostart entry runs `rain pending`). Firefox can stay open; restart it
afterwards.

Apply only some parts:

```sh
tools/rain apply catppuccin-mocha --only gtk,terminal
```

`tools/rain install` sets up the menu entry, the login autostart, the app icon
(in `~/.local/share/icons/hicolor`) and a git pre-commit hook that runs `rain
check`. Undo: delete `~/.local/share/applications/rain-themes.desktop`,
`~/.config/autostart/rain-themes-pending.desktop`, `.git/hooks/pre-commit` and
`~/.local/share/icons/hicolor/*/apps/rain-themes.png`.

Targets: `gtk`, `wallpaper`, `terminal`, `geany`, `firefox`, `brave`, `vesktop`.

Switching palettes is just another apply. The snapshot is only taken once, so
`--restore` always goes back to the setup from before the *first* apply.

## What each target does

| Target | Result | Live? |
|---|---|---|
| `gtk` | Builds `~/.themes/Rain-<Name>-Dark` from Colloid and sets it as Cinnamon's desktop, applications and window-border theme. Links a libadwaita stylesheet into `~/.config/gtk-4.0/`. Covers Nemo, Geany's window, dialogs and the panel. | Immediately |
| `wallpaper` | Copies `wallpaper-desktop.png` (2560×1600) to `~/.local/share/backgrounds/rain-themes/` and sets it. | Immediately |
| `terminal` | Adds a GNOME Terminal profile "Rain <Name>" and makes it the default. Your existing profile stays. | New tabs/windows; switch open ones via the profile menu |
| `geany` | Installs the colour scheme and selects it. | Next Geany start |
| `firefox` | Writes `chrome/userChrome.css` + `userContent.css` into the default profile and enables them in `user.js`. | Next Firefox start |
| `brave` | Sets Brave's "Customize Brave → colour" seed to the palette accent, dark mode. | Next Brave start |
| `vesktop` | Copies the Discord theme CSS into Vesktop's `themes/` folder and enables it. Skipped if Vesktop has never run. | Live reload |

Firefox's default theme follows the GTK theme on Linux, so it roughly matches
after `gtk` alone. The userChrome files make it exact.

## One-time manual steps

Each palette's `desktop/README.md` has the exact values.

- **Claude Code**: `/theme` → the dark *ANSI colours only* option. From then on
  it uses the terminal's palette, so it follows every apply.
- **Dark Reader** (ChatGPT and other sites): on the site, open the Dark Reader
  popup → Theme → Colors, and enter the background/text values from the README.
  Import is avoided on purpose: it replaces all of Dark Reader's settings.
- **Niagara Launcher** (phone): set `wallpaper-phone.png` as the wallpaper. Then
  Niagara → Theme colour → pick the *Wallpaper and System* swatch closest to the
  accent, or the README's fallback *Standard* swatch. Export the `.nlt` and
  commit it into the palette folder so switching later is one tap.
- **Brave (alternative)**: if the seed colour looks off, set Brave to follow
  GTK in `brave://settings/appearance` instead; it then picks up the Colloid
  colours.

## Undo

```sh
tools/rain restore
```

This restores the three Cinnamon theme settings, the wallpaper, the terminal
profile list and default, `~/.config/gtk-4.0`, the Firefox files, Geany's scheme
and Brave's colour, from `~/.local/state/rain-themes/snapshot.json`. Geany and
Brave are queued if open, like on apply.

Things deliberately left behind: the `~/.themes/Rain-*` folders, the Rain
terminal profiles and the Firefox pref `toolkit.legacyUserProfileCustomizations.stylesheets`.
They do nothing unless selected.

Manual undo if the script isn't available: System Settings → Themes → set
your previous themes back. Delete the three links in
`~/.config/gtk-4.0/`. Terminal → Preferences → pick the old profile.

## Phone: installing Rain themes

In Rain → Themes → **+** → install from URL, use the **raw** URL:

```
https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/<slug>/<slug>.json
```

A `github.com/.../blob/...` link fails with "Failed to fetch theme", because it
is GitHub's HTML page, not the JSON. The repo README lists every install URL.

## Phone: system colours and apps

Connect the phone with **Wireless debugging** (Developer options), then check that `adb devices` lists it.

```sh
tools/rain phone librekai                  # Material You seed = the accent, and files copied over
tools/rain phone librekai --style VIBRANT  # TONAL_SPOT (default), VIBRANT, EXPRESSIVE, SPRITZ, ...
tools/rain phone --restore                 # the original setting (saved on the first run)
```

The GUI's **Phone** button does the same, using the style picked in its
*Phone (adb)* row. The files land in `Download/rain-themes/<slug>/` on the phone:

- `wallpaper-phone.png`: set it in Photos or the wallpaper picker (adb can't).
- `sync-theme.json`: copy its contents and paste them into Sync's Monet theme
  import. Sync only imports from the clipboard. The palette's
  `desktop/README.md` shows the same JSON, ready to copy.
- `<slug>.app-theme.json`: import it in an app that reads the app-theme format (such as redeye), or use the raw URL listed in the
  palette's `desktop/README.md`.

Termius and Niagara have no import. The palette's `desktop/README.md` names the
Termius built-in and the Niagara swatch to pick.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Geany or Brave unchanged | It was running and got skipped, or it overwrote the change on exit. Close it, `tools/rain pending`. |
| Firefox unchanged | Needs a full restart. Check `about:config` → `toolkit.legacyUserProfileCustomizations.stylesheets` is `true`. The profile used is the one in `~/.mozilla/firefox/installs.ini`. |
| Some Firefox parts wrong after a Firefox update | Firefox renames its theme variables now and then. Re-derive them (see [design.md](design.md#firefox)) and re-export. |
| GTK4/libadwaita apps still old colours | Check the links in `~/.config/gtk-4.0/`; the app must be restarted. |
| `apply_theme.py` can't clone Colloid | Needs network once; afterwards it uses `~/.cache/rain-themes/Colloid-gtk-theme`. |
| Terminal colours right, but bold text too bright | `bold-is-bright` is off by design; change it in the profile if you prefer it on. |

## Previewing without applying

```sh
tools/rain preview librekai --out /tmp/rain-preview
```

This opens a GTK test window, a throwaway Firefox profile and a separate Geany
instance, each for a few seconds, and saves screenshots. Your running apps and
settings aren't touched.
