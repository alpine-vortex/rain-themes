# Status

Last updated 2026-09-28 (second session: desktop support for all 21 palettes).

- Everything is on `main`: desktop exports, docs, Firefox Color links,
  `tools/rain`, the pending queue and the GUI (`unified-cli` merged the same day).
- The 19-palette desktop work (`desktop-all-palettes`) was merged to `main` on
  2026-09-28.

## Phone

- Generated for all 21 palettes:
  - `sync-theme.json` (Sync for Reddit Monet import)
  - a Termius built-in per palette (spec `termius`)
  - `<slug>.app-theme.json` (app-theme v1, renamed from redeye-theme 2026-09-29; raw URLs live on `main`)
  - `<slug>.heliboard.json` (+ `-light`): HeliBoard "all colors" (all 44 slots).
    `.heliboard-simple.json` is the 10-colour version. Both are matched to real exports;
    importing one on the phone isn't confirmed yet.
  - Gotcha (fixed 2026-09-29): files pushed with adb stay `is_pending=1` in MediaStore, so
    file pickers (HeliBoard's Load) show the folder as empty until they're scanned.
    `rain phone` now scans every pushed file. It also picks the phone when an emulator is
    attached (else set `ANDROID_SERIAL`).
  - Nested `light` variants (official upstream light flavours) for 15 of the 21; see
    `docs/app-theme.md`. The merge is held until redeye accepts the app-theme names.
- `rain phone <slug>` (`tools/phone_theme.py`) sets the Material You seed over adb,
  which is checked on Android 17. It also copies the wallpaper, Sync and redeye
  files to `/sdcard/Download/rain-themes/<slug>/`.
  `rain phone --restore` puts back the original setting, saved on the first run
  per device (by `ro.serialno`) in `~/.local/state/rain-themes/phone-snapshot.<serial>.json`. Checked end to end on
  2026-09-29: the system colours applied and the Sync import (paste JSON) worked.
- GUI: every card has a **Phone** button, and there's a *Phone (adb)* row with a style picker and
  *Restore phone*. The "phone" badge comes from `phone-state.json` (any device). The Phone button
  hasn't been clicked yet.
- Not yet: Redeye's importer isn't built yet (the
  redeye session is using the files as test data).

- **redeye adb interface.** Agreed with the redeye session on 2026-09-29, and not built
  in redeye yet; it will message when a build has it.
  - Receiver: `dev.redeye/.theme.ThemeCommandReceiver`, protected by DUMP.
  - `SET_THEME` takes `--es slug`, `--es url` or `--es json_b64`, plus an optional
    `--es mode`. `GET_THEME` returns `{slug, mode, version}`.
  - Results (amended 2026-09-29 after a probe against redeye 0.5.0, which has no receiver
    yet): an explicit broadcast to a missing component still reports `result=0` with no
    data, so success is `-1` (RESULT_OK) and it always carries data. Failure is `1`, with
    an error string. Anything else means the receiver is missing or the build is old.
  - File drop name: `files/themes/<slug>.json`.
  - Plan for `rain phone`: if `pm path dev.redeye` finds the app, push
    `<slug>.app-theme.json` to `/sdcard/Android/data/dev.redeye/files/themes/<slug>.json` (the shell can
    write there on Android 17), then send `SET_THEME --es slug`. Never send `mode`.
    Keep `json_b64` as the fallback.

## Live state

What's applied on the owner's machines is kept out of the repo, in the local
(gitignored) `CLAUDE.md`.

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
  "Rain Themes" GUI (`tools/rain_gui.py`); `rain install` was run on the dev machine.
- Exports committed for both palettes.
- The first apply on an unthemed desktop saves a snapshot of the original setup
  (themes, wallpaper, terminal profile, Brave seed, Firefox/Geany state);
  `--restore` returns each part that still holds Rain's value to it, then
  retires the snapshot.
- The pre-commit hook checks the staged tree and is shared by all worktrees;
  the same hook checks merge commits, and a pre-push hook checks commits
  pushed to `main`. `rain install` refuses in a linked worktree. Acceptance tests for the hook,
  install, restore, snapshot guard, phone and atomic writes:
  `python3 tools/dev/test_tooling.py` (scratch dirs only).

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

- **Live look.** A palette was applied for real on 2026-09-28, all targets.
  Only the Firefox toolbar has been reviewed so far (fixed: icons were green
  from the Firefox Color extension's default theme).
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

1. Review the live apply (panel, Nemo, terminal, Vesktop, Brave) with the owner
   and fix what looks off.
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
