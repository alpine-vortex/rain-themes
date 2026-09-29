# Status

Last updated 2026-09-28 (second session: desktop support for all 21 palettes).

- Everything is on `main`: desktop exports, docs, Firefox Color links,
  `tools/rain`, the pending queue and the GUI (`unified-cli` merged the same day).
- The 19-palette desktop work (`desktop-all-palettes`) was merged to `main` on
  2026-09-28.

## Phone (branch `phone-sync`, 2026-09-29)

- `sync-theme.json` (Sync for Reddit Monet import), a Termius built-in per palette
  (spec `termius`), and `redeye-theme.json` (redeye v1) are generated for all 21.
- Not yet: the system accent through adb (the phone isn't paired yet), and
  importing any of these on the phone.

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
- **All 21 palettes now have desktop exports.** On 2026-09-28 the other 19
  gained `ansi_source` / `ansi` / `terminal` / `syntax` blocks. Each value was
  taken from the palette's own upstream terminal file (kitty / alacritty /
  `g:terminal_color_*` / VS Code `terminal.ansi*`) and colorscheme highlight
  groups; `ansi_source` in each spec names the files. Every ANSI hex matched
  a colour already in the spec's palette. Rain outputs stayed byte-identical.
  - Deliberate deviations from upstream:
    - **Selection:** Catppuccin Frappé/Macchiato use `surface2` (as Mocha
      does) and Tokyodark uses its Visual `bg2`, because upstream uses a
      light selection with dark selected text and the exporter always draws
      selected text in the foreground colour.
    - **Monokai Dimmed:** its selection is upstream's 50%-alpha colour
      flattened onto the background.
    - **Rosé Pine:** it uses the new `terminal.cursor_text`, keeping its
      light text on a dark cursor.
  - Filled where upstream has no rule:
    - **Dracula:** operator, preprocessor and added/changed.
    - **Gruvbox:** parameter (Identifier) and tag/attribute (htmlTagName/htmlArg).
    - **Monokai Dimmed:** operator and preprocessor (keyword.control purple).
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

Of the other 19, only four were screenshotted: Gruvbox, Rosé Pine, Kanagawa
Dragon and Solarized Osaka. Each got a Geany shot and a GTK shot, and all
eight looked right. The Geany shots only show the shebang and docstring, so
they confirm that the scheme loads with the right string and comment colours.
Keyword, function and type colours were not on screen. The rest are covered by
`rain check` and a contrast scan.

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

- Some upstream syntax colours are low-contrast on their own background, and
  were kept as upstream has them:
  - Monokai Dimmed type/class `#9B0000`, 1.9:1.
  - Nord comment `#616E88`, 2.4:1.
  - Tokyodark comment, 2.3:1.
  - Tokyo Night Storm comment 2.4:1 and git-delete 2.3:1.
- Rosé Pine (main and moon) uses upstream's dark block cursor (`highlight_high`,
  about 2.2:1). That's fine in the terminal, but it makes a faint caret in Geany.

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
2. ~~The other 19 palettes~~: done on 2026-09-28. Next is Firefox previews
   (`tools/rain preview <slug>`) for the palettes the owner actually picks.
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
