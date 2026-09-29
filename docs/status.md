# Status

Last updated 2026-09-28 (end of the first session).

- Everything is on `main`: desktop exports, docs, Firefox Color links,
  `tools/rain`, the pending queue and the GUI (`unified-cli` merged the same day).

## Live state on spacer

- **Librekai applied** to every target: Cinnamon/GTK (`Rain-Librekai-Dark`),
  wallpaper, GNOME Terminal profile "Rain Librekai" (default), Geany,
  Firefox userChrome, Brave seed `#F93B7F`, Vesktop.
- Owner's Firefox also has the **Firefox Color** extension, whose default theme
  caused the green icons. They were given the Librekai Color link; whether
  they kept the extension is unknown.
- **Installed:** "Rain Themes" menu entry, login autostart (`rain pending`),
  and the repo's pre-commit hook (`rain check`).
- **Snapshot of the original setup** is in
  `~/.local/state/rain-themes/snapshot.json`; `rain restore` returns to it.
- Changes are logged in `~/CLAUDE-work.md` (2026-09-28 entries).

## Done

- Spec blocks `ansi` / `terminal` / `syntax` added for **Librekai** (from VS
  Code's built-in Monokai) and **Catppuccin Mocha** (from catppuccin/kitty and
  the Catppuccin style guide). Rebuilding all 21 Rain themes after the change
  gave byte-identical output.
- `tools/desktop_export.py`, `tools/apply_theme.py`,
  `tools/dev/preview_desktop.py`.
- `tools/rain` (single CLI incl. `check`), pending queue + login autostart, the
  "Rain Themes" GUI (`tools/rain_gui.py`); `rain install` was run on spacer.
- Exports committed for both palettes.
- A snapshot of spacer's pre-theme setup was taken on 2026-09-28 (Orchis-Dark
  desktop/apps, Mint-Y borders, wallpaper `~/Downloads/13514189.png`, implicit
  terminal profile, Brave seed `-14244198`, no Firefox userChrome, Geany
  default scheme). `--restore` returns to this.

## Verified (by screenshot, without touching the live desktop)

| Target | Librekai | Mocha |
|---|---|---|
| GTK3 widgets and headerbar (Colloid build) | ✅ | ✅ |
| libadwaita stylesheet compiles with our colours | ✅ (by inspection) | — |
| Firefox 156 tab strip, toolbar, URL bar + focus ring, new-tab page | ✅ | ✅ |
| Geany editor scheme + GTK chrome | ✅ | ✅ |
| Wallpapers | ✅ | ✅ |

## Not yet verified

- **Live look on spacer.** Librekai was applied for real on 2026-09-28, all
  targets. Only the Firefox toolbar has been reviewed with the owner so far
  (fixed: icons were green from the Firefox Color extension's default theme).
  The panel, Nemo, terminal and Vesktop still need a look.
- **Brave**: that the seed edit survives a relaunch, and how close the
  generated colours look.
- **Vesktop**: installed and themed on 2026-09-28 (native path
  `~/.config/vesktop`, `enabledThemes` written). Still to confirm that the CSS
  selectors win everywhere (DevTools).
- **`rain restore` for real**: only dry-run so far.
- **Login autostart** (`rain pending`): installed, not yet seen running at a real login.
- **GUI Apply/Restore buttons**: the window was screenshotted; the buttons run
  the same `rain` commands that were tested, but haven't been clicked yet.
- **Material You / Niagara**: whether the phone wallpaper yields the accent as a
  "Wallpaper and System" swatch.

## Known issues / rough edges

- Firefox: the bookmarks-toolbar notice link stays Firefox-blue. The new-tab
  page's own purple accents (buttons) are page content, not ours.
- GTK2 widget PNGs keep Colloid's stock colours.
- In Librekai, `secondary_bg` and `tertiary_bg` are the same colour, so the
  panel and titlebars don't differ. That's a spec choice, fixable in the spec.
- `apply_theme.py` assumes Brave Origin's `Default` profile and Firefox's
  install default; other profiles are ignored.

## Next steps

1. Review the live Librekai apply (panel, Nemo, terminal, Vesktop, Brave) with
   the owner and fix what looks off.
2. **The other 19 palettes** (the planned next session): add `ansi_source`,
   `ansi`, `terminal`, `syntax` to each spec from the palette's upstream
   (families and shortcuts are listed in `CLAUDE.md`), then `tools/rain build`
   and `tools/rain check`. Existing Rain outputs must not change. Spot-check
   with `tools/rain preview <slug>`. They then appear in the GUI automatically.
3. Brave GTK mode: find its pref key (toggle in the UI, diff `Preferences`) and
   offer it as an option.
4. Vesktop: check in DevTools that the theme's variables win; fix selectors if needed.
5. Commit `.nlt` exports for the palettes actually used on the phone.
6. Optional: show desktop exports (wallpaper thumbnails) in `GALLERY.md`; an
   optional Stylus user style for chatgpt.com if Dark Reader isn't precise
   enough.

## Open questions

- Should the phone wallpaper stay "big accent blob" (good for Material You) or
  be subtler? It's a trade-off between looks and the extracted colour.
- Light variants: everything is dark-only today.
