# Status

Last updated 2026-09-28. Branch `desktop-exports` (not merged to `main`).

## Done

- Spec blocks `ansi` / `terminal` / `syntax` added for **Librekai** (from VS
  Code's built-in Monokai) and **Catppuccin Mocha** (from catppuccin/kitty and
  the Catppuccin style guide). Rebuilding all 21 Rain themes after the change
  gave byte-identical output.
- `tools/desktop_export.py`, `tools/apply_theme.py`,
  `tools/dev/preview_desktop.py`.
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

- **A real apply on spacer**: never run as of this writing. The Cinnamon panel,
  window borders under Muffin, GNOME Terminal profile and wallpaper can only be
  checked that way.
- **Brave**: that the seed edit survives a relaunch, and how close the
  generated colours look.
- **Vesktop**: not installed. Check the settings path, `enabledThemes`, and
  that the CSS selectors win (DevTools).
- **`--restore` for real**: only dry-run so far.
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

1. **Real apply of one palette**, then fix whatever looks off.
2. Extend the other 19 specs with `ansi` / `terminal` / `syntax` from each
   palette's upstream (record `ansi_source`), then `desktop_export.py` them.
   Rebuild all Rain themes afterwards and confirm no diff.
3. Brave GTK mode: find its pref key (toggle in the UI, diff `Preferences`) and
   offer it as an option.
4. After installing Vesktop: verify, then fix the path or selectors if needed.
5. Commit `.nlt` exports for the palettes actually used on the phone.
6. Optional: show desktop exports (wallpaper thumbnails) in `GALLERY.md`; an
   optional Stylus user style for chatgpt.com if Dark Reader isn't precise
   enough.
7. Merge `desktop-exports` into `main` once a real apply has been checked.

## Open questions

- Should the phone wallpaper stay "big accent blob" (good for Material You) or
  be subtler? It's a trade-off between looks and the extracted colour.
- Light variants: everything is dark-only today.
