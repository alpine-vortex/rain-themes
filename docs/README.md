# rain-themes docs

| Doc | For |
|---|---|
| [desktop-guide.md](desktop-guide.md) | **Using it.** Apply a palette to the Mint desktop and apps, undo it, do the manual steps, fix common problems. Also installing the Rain themes on the phone. |
| [design.md](design.md) | **How it works and why.** Pipeline, the Colloid build, per-app mechanics, decisions and the research behind them (including dead ends). |
| [status.md](status.md) | **Where things stand.** What's verified, what isn't, known issues, next steps, open questions. |
| [../tools/README.md](../tools/README.md) | Reference for the spec format and every script's inputs/outputs. |

## The project in one paragraph

One `theme.spec.json` per palette (official colours + a role mapping) is the
single source of truth. `tools/build_theme.py` turns it into a Rain/Bunny theme
for Discord on Android. `tools/desktop_export.py` turns the same spec into
configs for the Linux Mint desktop: Cinnamon/GTK (a recoloured
[Colloid](https://github.com/vinceliuice/Colloid-gtk-theme) build), GNOME
Terminal (and Claude Code through it), Geany, Firefox, Brave, Vesktop, plus
wallpapers that also steer Android's Material You colours (Niagara Launcher).
`tools/apply_theme.py` applies it all with one command and can restore the
previous setup.

```
theme.spec.json ──build_theme.py──▶ <slug>.json (Rain)  ──▶ phone: Discord
        │                                  │
        └────────desktop_export.py◀────────┘ (Vesktop reuses the Discord mapping)
                        │
                        ▼
                <slug>/desktop/*  ──apply_theme.py──▶ Cinnamon, GTK, terminal,
                                                      Geany, Firefox, Brave,
                                                      Vesktop, wallpaper
```
