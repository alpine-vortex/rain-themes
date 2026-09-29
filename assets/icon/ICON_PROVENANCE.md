# Rain Themes icon provenance

- Generating model: `gpt-5.6-luna`
- Generation date: 2026-09-29
- Selected candidate: the single generated candidate (kept as `rain-themes-source.png`). No alternate candidates were retained because this candidate met the small-size readability and transparency requirements.
- Generation mode: built-in image generation tool.

## Prompt

```text
Use case: logo-brand
Asset type: Linux GTK desktop app icon
Primary request: an original bold flat square icon for Rain Themes: one large raindrop divided into four chunky horizontal colour bands, centered on a dark rounded-square tile.
Style/medium: polished flat raster icon, geometric, highly legible at 16x16.
Composition/framing: centered drop, generous padding, transparent outside tile.
Color palette: tile #1E1E2E; bands #F93B7F, #CBA6F7, #94E2D5, #89B4FA.
Constraints: no text, letters, numbers, logos, watermark, brand likeness, fine detail, thin lines, gradients, scenery, or multiple objects; genuinely transparent outside the rounded tile.
```

## Derivation

`rain-themes-source.png` is the generated 1254x1254 RGBA PNG. Each numbered icon was resized directly from that source using Pillow's Lanczos resampling (`Image.Resampling.LANCZOS`), then saved as an optimized RGBA PNG. The source and every numbered file have transparent corner pixels.

At 16x16, the rounded tile remains a strong dark silhouette and the drop remains a single readable shape with four broad colour bands; no fine detail is required to distinguish the rain/palette mark.

## SHA-256

| File | SHA-256 |
| --- | --- |
| `rain-themes-source.png` | `1260d33afdef24e9725c46f74a342f42e756a61465c8fc45e25b368398005057` |
| `rain-themes-256.png` | `db3b168dc7af642d0da58ff75f7337547936b7fc1257c021720eac7913afd52b` |
| `rain-themes-128.png` | `c998a1907497b8936eab00b1d746d60b6337d126f7fcd6c811240e8fad709622` |
| `rain-themes-64.png` | `d8115e4262d02791a365389254e067964354212661c162106ed92ae7326059bf` |
| `rain-themes-48.png` | `d250d3f74cb80dbcd08f1b435cdfb0cceb3524affb9d0e4bfcf79e653624bcf3` |
| `rain-themes-32.png` | `46b29f2b5bc57d2ccad0dc3ebeab14af1eb306ef32be4e70cf5ba099252433d5` |
| `rain-themes-24.png` | `7f608f5f7cf6dd62f8f1eb0a470ff240ae5b7c7b6acb33cb3b83cfe0563593f4` |
| `rain-themes-16.png` | `fff1c0dec3be94205f0fd38c4a615a2d660dc75bb909a11fdb08414fcc079cf4` |
