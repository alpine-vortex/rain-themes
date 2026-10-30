# Status

Last updated 2026-10-29. Historical verification notes keep the date on which
they were observed; generated coverage does not imply that every target has
been checked live.

- Everything is on `main`: desktop exports, docs, Firefox Color links,
  `tools/rain`, the pending queue and the GUI (`unified-cli` merged the same day).
- The 19-palette desktop work (`desktop-all-palettes`) was merged to `main` on
  2026-09-28.

## Palette source evidence

- Specs contain palette, ANSI/syntax, and light-flavour source URLs and notes.
- A provenance audit snapshot now pins source files to immutable upstream
  commits, records retrieval hashes, and checks all dark/light palette hexes
  plus ANSI, terminal, and syntax assignment values against those sources.
  Librekai Dimmed selection was corrected to the verified alpha composite
  (`#434548`). The snapshot records current verification references, not the
  historical revisions used at original extraction. Verified 2026-10-29:
  21 palettes, 64 pinned source records, 1,180 palette hex values, 1,301
  source-field checks, and one derived value. See [palette provenance](palette-provenance.md).
- The generated gallery now offers a collapsed, lazy-loaded desktop wallpaper
  thumbnail for each of the 21 themes in both `GALLERY.md` and `index.html`.

## Phone

- Generated for all 21 palettes:
  - `sync-theme.json` (Sync for Reddit Monet import)
  - a Termius built-in per palette (spec `termius`)
  - `<slug>.app-theme.json` (app-theme v1, renamed from redeye-theme 2026-09-29; raw URLs live on `main`)
  - `<slug>.heliboard.json` (+ `-light`): HeliBoard "all colors" (all 44 slots).
    `.heliboard-simple.json` is the 10-colour version. Both are matched to real exports;
    `librekai.heliboard.json` was imported through HeliBoard's own Load file flow on
    2026-10-29; HeliBoard showed the imported User-Defined set associated with
    `librekai` in its color list.
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
- **Live phone apply/restore (2026-10-29):** on a Pixel 10 Pro XL over ADB,
  applied Gruvbox (seed `#FE8019`), confirmed Rain's export files landed in its
  previously absent Download folder, restored the exact pre-test
  wallpaper-driven setting (`home_wallpaper`, `SPRITZ`), then returned system
  colours to the prior Librekai seed (`#F93B7F`). The test export folder was
  removed from storage; existing Librekai downloads and the original per-device
  snapshot remain. Media-scan broadcasts were sent.
- **Visual retry (2026-10-29):** the phone's Wallpaper & style screen showed
  the restored pink Librekai palette in its lock-screen and home-screen
  previews. The desktop was also captured unlocked with Gruvbox active; its
  Cinnamon panel and window chrome looked consistent. No palette was changed
  during either visual check. Android's system JSON picker showed the existing
  Librekai app-theme, HeliBoard, and Sync files. HeliBoard is installed. Its
  Appearance > Colors > Load > Load file flow opened Android's document picker;
  selecting `librekai.heliboard.json` loaded its User-Defined set. A reversible
  selection check applied it, then restored the original day color (Ocean) and
  night color (librekai).
  DocumentsUI retained an empty Gruvbox folder entry after the test files and
  directory were removed from storage.
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

## Valenced (2026-10-27)

- Valenced (Rain + Revenge) loads the existing Rain JSONs unchanged via its Legacy
  Themes plugin (`valenced.themes.legacy`, community repo). All 21 pass its parser.
  Imports don't update, and Discord's Light mode stays uncoloured.
- `tools/rain valenced` exports a native theme plugin (`rain-themes.palettes`) into
  the public `valenced-rain` plugin repo: 21 palettes in two groups (plain, with
  wallpaper), and the official light flavour in Light mode for 15 of them. See `tools/README.md` ("Valenced").
- Checked: the registration code runs against a fake themes API (42 themes, 130 tokens
  per mode, all valid hex; dark colours equal the Rain JSON). The repo's CI build
  published 1.0.0, and it was installed and confirmed working on a device (2026-10-27).

## Live state

What's applied on the owner's machines is kept out of the repo, in the local
(gitignored) `CLAUDE.md`.

## Done

- **Icons, Flatpak, Xed and LibreWolf** targets (2026-10-29): the icon theme
  follows the accent within its family (Yaru or Mint-Y), Flatpak apps get read
  access to the Rain GTK theme, Xed gets a GtkSourceView 4 scheme
  (`xed-<slug>.xml`), and LibreWolf gets the Firefox userChrome files.
- **Claude Code** target (2026-10-29): every palette exports
  `claude-code-theme.json`, a Claude Code custom theme; `rain apply --only
  claude-code` installs it as `~/.claude/themes/rain-themes.json` and selects it,
  and `rain restore` puts the previous `theme` back.
- **GNOME Text Editor** target (2026-10-29): every palette exports a
  GtkSourceView 5 scheme `gtksourceview-<slug>.xml`; `rain apply --only
  gnome-text-editor` installs and selects it (queued while the editor is open),
  and `rain restore` puts the previous scheme back.
- **kitty and Ghostty** targets (2026-10-28): every palette exports
  `kitty-theme.conf` and `ghostty-theme`; `rain apply` installs them, reloads
  running terminals, and `rain restore` puts the previous theme back.
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
- Validation on 2026-10-29: `tools/rain check` passed for all 21 palettes;
  `python3 tools/dev/test_tooling.py` passed all 51 tests; the provenance
  verifier passed all pinned-source and derived-value checks.
- The pre-commit hook checks the staged tree and is shared by all worktrees;
  the same hook checks merge commits, and a pre-push hook checks commits
  pushed to `main`. `rain install` refuses in a linked worktree. Acceptance tests for the hook,
  install, restore, snapshot guard, phone and atomic writes:
  `python3 tools/dev/test_tooling.py` (scratch dirs only).

- **degoog** (2026-10-24): `tools/rain degoog` exports all 21 palettes as
  one degoog theme with a palette picker. It's published as the
  `degoog-rain` store repo. 15 palettes switch to their official light
  flavour in degoog's light mode. Tested in a throwaway degoog 1.1.0
  container: add the repo, install, activate, change the palette. See
  `tools/README.md` ("degoog").

## Earlier screenshot verification

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

- **Live look.** Firefox toolbar was reviewed previously (fixed: icons were
  green from the Firefox Color extension's default theme). The retry screenshot
  showed the Gruvbox Cinnamon panel and window chrome. Nemo and terminal review
  are deferred; Vesktop's live Gruvbox variables are verified below.
- **Brave**: the theme seed, scheme, and Rain theme ID survived a real relaunch
  on 2026-10-29. Visual colour accuracy still needs an unlocked-screen review.
- **Vesktop**: installed and themed at `~/.config/vesktop`. On 2026-10-29,
  Vesktop 1.6.8 launched with `gruvbox.theme.css` enabled. Local DevTools
  inspection confirmed the live renderer's Gruvbox background, foreground,
  brand, and link variables (`#282828`, `#EBDBB2`, `#FE8019`, `#83A598`), plus
  the expected dark theme root, Gruvbox chat-surface backgrounds, and button
  text color. This confirms the theme loaded on representative live surfaces;
  dialogs and every screen state were not reviewed.
- **Live apply/restore round-trip (2026-10-29):** desktop Gruvbox apply and
  restore passed with a fresh snapshot; all three Brave fields were captured
  and restored, then the seed/scheme/theme ID survived a real Brave relaunch.
  The legacy pre-test snapshot also restored; its missing Brave extension
  theme ID was left unchanged as designed. The GNOME Text Editor target was
  excluded from final reapply to preserve its pre-existing user-selected
  scheme. On a Pixel 10 Pro XL, the Gruvbox seed and exports applied, restore
  matched the original wallpaper-driven setting, and the phone returned to its
  previous Librekai seed. The temporary export folder was removed. The unlocked
  visual retry confirmed the desktop shell/window chrome and phone wallpaper
  previews; HeliBoard's file-picker import was also completed through its UI.
- **Login autostart** (`rain pending`): installed; invoking its exact command
  returned `nothing pending`. A real login has not been observed.
- **GUI Apply/Restore buttons**: the live window opened centered, and palette
  actions expose distinct screen-reader names. Apply and Restore controls were
  not clicked; their underlying CLI round-trip is verified above.
- **Material You / Niagara**: whether the phone wallpaper yields the accent as a
  "Wallpaper and System" swatch.

## Known issues / rough edges

- The expanded contrast report currently flags **88 palette/pair combinations
  across all 21 palettes**. Most are muted text on input/background surfaces;
  several are danger/positive/warning text and low-contrast interactive icons.
  These are reported rather than changed because the values are upstream or
  intentional mappings. Review them before presenting the palettes as meeting
  WCAG AA for every role; `rain check` verifies generated-file consistency, not
  contrast compliance.

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
  install default; Firefox and LibreWolf can select another existing profile
  explicitly with `--firefox-profile` / `--librewolf-profile`; Brave accepts
  `--brave-preferences PATH`. Retargeting a browser during an active restore
  snapshot is refused so the original profile files remain recoverable.

## To-do checks

### Live desktop checks

- [ ] Exercise the GUI Apply and Restore controls safely.
- [ ] Observe `rain pending` during a real login; the installed command only
  returned `nothing pending` when invoked manually.
- [ ] Review additional Vesktop dialogs and screen states; representative
  Gruvbox surfaces and variables are verified.
- [ ] Review Brave's visual color accuracy **only when the owner is not using
  the computer and has explicitly authorized the review**.
- [ ] Review Nemo and terminal after the owner un-defers those targets.
- [ ] Decide whether Brave should offer a GTK-following mode; verify its
  preference only after the same explicit authorization.

### Phone checks

- [ ] Check whether Niagara offers the wallpaper-derived accent as a
  *Wallpaper and System* swatch.
- [ ] Export `.nlt` files manually from Niagara for phone palettes in use, then
  commit each export with its matching palette. The binary format is not
  generated by Rain.

### Palette quality and maintenance

- [ ] Review the 88 reported low-contrast palette/pair combinations and record
  which are intentional versus candidates for palette changes.
- [ ] Refresh the provenance snapshot when upstream sources change, reviewing
  every mismatch before updating a spec. See [palette provenance](palette-provenance.md).

### Optional

- [ ] Add a Stylus style for chatgpt.com only if Dark Reader proves insufficient.

## Open questions

- Should the phone wallpaper stay "big accent blob" (good for Material You) or
  be subtler? It's a trade-off between looks and the extracted colour.
- Light variants: 15 palettes export their official light flavour for selected
  integrations. The Rain theme and desktop application remain dark-first; the
  remaining six palettes have no official light flavour upstream.
