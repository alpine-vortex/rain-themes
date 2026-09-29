# rain-themes docs

| Doc | For |
|---|---|
| [desktop-guide.md](desktop-guide.md) | **Using it.** Apply a palette to the Mint desktop and apps, undo it, do the manual steps, fix common problems. Also installing the Rain themes on the phone. |
| [design.md](design.md) | **How it works and why.** Pipeline, the Colloid build, per-app mechanics, decisions and the research behind them (including dead ends). |
| [app-theme.md](app-theme.md) | **The app-theme format** (v1) for Android apps, which this repo owns (redeye's parser follows it). |
| [status.md](status.md) | **Where things stand.** What's verified, what isn't, known issues, next steps, open questions. |
| [../tools/README.md](../tools/README.md) | Reference for the spec format and every script's inputs/outputs. |

## The project in one paragraph

One `theme.spec.json` per palette (official colours + a role mapping) is the
single source of truth. `tools/build_theme.py` turns it into a Rain/Bunny theme
for Discord on Android. `tools/desktop_export.py` turns the same spec into
configs for the Linux Mint desktop: Cinnamon/GTK (a recoloured
[Colloid](https://github.com/vinceliuice/Colloid-gtk-theme) build), GNOME
Terminal (and Claude Code through it), Geany, Firefox, Brave, Vesktop, plus
wallpapers. The same exports cover the phone: `sync-theme.json` (Sync for
Reddit), `<slug>.app-theme.json` (Android apps such as redeye), a Termius built-in per palette, and a
Niagara swatch. `tools/rain apply` applies the desktop with one command and can
restore the previous setup. `tools/rain phone` sets the phone's Material You
seed over adb and copies the phone files over. The **Rain Themes** GTK app
(`tools/rain gui`) wraps both.

```
theme.spec.json ──build_theme.py──▶ <slug>.json (Rain)  ──▶ phone: Discord
        │                                  │
        └────────desktop_export.py◀────────┘ (Vesktop reuses the Discord mapping)
                        │
                        ▼
                <slug>/desktop/*  ──rain apply──▶ Cinnamon, GTK, terminal,
                        │                          Geany, Firefox, Brave,
                        │                          Vesktop, wallpaper
                        └─────────rain phone──▶ Android: Material You seed,
                                                 wallpaper, Sync, redeye files
```
