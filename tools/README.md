# Rain theme builder

Turns a palette spec into a Rain / Bunny (spec 2) theme, a static preview
mockup, and a notes file.

```sh
python3 tools/build_theme.py <theme-dir> [<theme-dir> ...]
```

Each theme folder holds a `theme.spec.json`; the script writes next to it:

| File | What |
|---|---|
| `<slug>.json` | the theme (host this at a raw URL, add by URL in Rain → Themes) |
| `<slug>-preview.html` | channel list + chat mockup, colours read only from the theme |
| `<slug>-notes.md` | palette, mapping table, derived shades, contrast table, spec notes |

Workflow for a new scheme: fetch the scheme's official palette → write
`<name>/theme.spec.json` (copy an existing one) → run the script → read the
FAIL/WARN lines and adjust roles.

## Checks the script enforces

- Every key in `reference_keys.json` (taken from the Maple-Blade theme) is filled,
  no key twice, no extra keys; valid JSON.
- No `background`: surfaces must be opaque 6-digit hex. With `background`:
  surfaces must be 8-digit (translucent). Text/icon colours are always 6-digit.
- Preview contains no colour outside its `:root` block and no undefined `var()`.
- Contrast table (WCAG): body text on each surface, text on composited
  mention/selected, links, button text on brand. Translucent surfaces are judged
  over a worst-case white image pixel. FAILs are reported, not fatal.
- Warns when brand and a status colour are within 20° of hue.

## Spec format

```jsonc
{
  "slug": "gruvbox",                 // output file prefix
  "name": "Gruvbox",
  "description": "...",
  "authors": ["emeet"],
  "source": "https://github.com/morhetz/gruvbox",
  "variant": "Dark · medium · accent: bright orange",   // preview subtitle
  "palette": { "dark0": "#282828", ... },               // the FULL official palette
  "palette_roles": { "dark0": "bg0; Normal background" }, // optional, shown in notes
  "roles": { ... all 25 role ids ... },
  "raw": { "BRAND_560": "...", "PRIMARY_630": "...", "PRIMARY_660": "...",
           "PRIMARY_700": "...", "PRIMARY_800": "..." },  // BRAND_500/530 default to brand/brand_bright
  "background": { "url": "https://...", "blur": 0, "alpha": 0.7 },  // optional
  "preview": { "server_name": "...", "users": [5 names], "me": "...", ... }, // optional text
  "notes": ["variant/accent choices, substitutions, ..."]           // copied to notes.md
}
```

Colour refs (in `roles` and `raw`):

- `"dark0"`: a palette colour
- `"bright_orange@33"`: palette colour + hex alpha
- `{"mix": ["bright_orange", "light0", 0.333]}`: derived shade (weight of the 2nd
  colour); optional `"alpha": "E0"`. Derived shades are listed in the notes automatically.

Role ids: `main_bg secondary_bg tertiary_bg floating_bg nested_floating_bg
input_bg hover active faint selected text_strong text_normal text_secondary
text_muted interactive_muted brand brand_bright text_on_brand link danger
positive warning mention mention_hover backdrop`. The key lists for each are in
`GROUPS` at the top of `build_theme.py`.

## Gallery

```sh
python3 tools/gallery.py
```

Screenshots every theme's preview to `<slug>/<slug>-preview.png`, then writes
`GALLERY.md` and `index.html` at the repo root and refreshes the theme table in
`README.md`. Run it after adding or changing a theme.
