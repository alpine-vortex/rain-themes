# redeye-theme v1

The theme format for redeye (an Android Reddit client). rain-themes owns
this format, and redeye's parser follows it. It was agreed with the redeye
session on 2026-09-29. `tools/desktop_export.py` (`redeye_theme()`) writes one
file per palette to `<slug>/desktop/redeye-theme.json`, which is served at
`https://raw.githubusercontent.com/alpine-vortex/rain-themes/main/<slug>/desktop/redeye-theme.json`.

## Syntax

- One theme per file, flat JSON object.
- Colours are strict `#RRGGBB`: case-insensitive, with no `#RGB`, no alpha and
  no names. rain-themes writes uppercase.
- Unknown keys are kept, and they round-trip through redeye's export untouched.

## Header

| Key | |
|---|---|
| `format` | `"redeye-theme"` (required) |
| `version` | `1` (required) |
| `name`, `slug` | required |
| `source` | optional URL; `""` = absent |
| `mode` | `"dark"` or `"light"`: which variant the top-level colours are |

## Colours

Only `background`, `text` and `accent` are required. A file that is missing one
of them, or that contains any malformed hex, is rejected with a list of errors.
Every other key is optional. An absent key is derived from background↔text
blends or contrast picks, never from Material's accent-seeded tones, so a
partial file still looks like its palette.

| Key | Material role(s) | Default when absent |
|---|---|---|
| `background` | background, surface, surfaceVariant | required |
| `text` | onBackground, onSurface | required |
| `accent` | primary, secondary | required |
| `on_accent` | onPrimary | contrast pick* |
| `panel` | surfaceContainerLow (drawer) | derived |
| `raised` | surfaceContainer, surfaceContainerHigh (menus, dialogs, top bar) | derived |
| `selected` | secondaryContainer | derived |
| `on_selected` | onSecondaryContainer | contrast pick* against `selected` |
| `line` | outlineVariant (hairlines) | derived. If it equals `raised`, dividers inside dialogs use a raised↔text blend |
| `border` | outline | 40% background→text |
| `text_secondary` | onSurfaceVariant | derived |
| `text_muted` | de-emphasised text (scores, icons) | derived |
| `state` | tertiary (NSFW / hidden / saved) | derived; must not equal `accent` |
| `on_state` | onTertiary | contrast pick* |
| `danger` | error | derived |
| `on_danger` | onError | contrast pick* |
| `accent_inverse` | inversePrimary (snackbar action on `text`) | derived. Only emit it if it reaches 4.5:1 on `text` |
| `link`, `positive`, `warning` | kept but not used yet | — |
| `tags` | subreddit dots, comment depth bars | list of 8. Order matters: the slot is a hash of the name. If there are fewer, cycle them |

\* A contrast pick is whichever of `background` / `text` has the higher contrast
against the fill.

The switch-off track (`surfaceContainerHighest`) is deliberately not a key.
It is always a neutral tone derived by redeye.

## Light / dark pairs

A dark theme may carry a light variant in a nested `light` object. The same
rules apply the other way round (`mode: "light"` with a nested `dark`).

- The top-level colours are the variant named by `mode`.
- The nested object must contain its own `background`, `text` and `accent`.
- Any other colour it leaves out is **derived from the nested object's own
  colours, not inherited** from the outer ones. The outer surfaces, `on_*`
  picks and `tags` are tuned to the other background, so they would be wrong.
- Header keys (`name`, `slug`, `source`) are inherited.

rain-themes generates dark palettes only for now (all 21 are `mode: "dark"`,
without a nested variant).

## How rain-themes fills it

- `panel` = secondary_bg; `raised` = `line` = floating_bg; `selected` =
  nested_floating_bg; `on_selected` = text; `border` = interactive_muted.
- `state` = spec `redeye_state`: the palette's orange, or yellow/gold where
  orange is the accent or has none.
- `tags` = ANSI 1–6, 9–14 and syntax colours, skipping greys and hues within
  12° of accent/state/danger. They are blended 30% toward the background and
  padded to 8 with other blend levels.
