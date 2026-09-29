# Rain Themes icon provenance

- Source model: `gpt-5.6-luna` (source inherited from s222; its original generation prompt is in commit `5e6f954`)
- Cleanup date: 2026-09-29
- Selected candidate: the cleaned source (`rain-themes-source.png`). It replaces the s222 version because the prior source had blurry white/dark smudges in the top-left and top-right tile corners.
- Cleanup method: deterministic Pillow edit. Rebuilt the rounded tile as a clean solid `#1E1E2E` RGBA silhouette, retained the largest connected colored raindrop component, removed all stray marks, then resized directly from the cleaned source.

## Prompt

```text
Use case: precise-object-edit
Asset type: Linux GTK desktop app icon cleanup
Primary request: preserve the existing Rain Themes icon exactly while removing the two blurry corner smudges from the dark rounded tile.
Input image: existing `rain-themes-source.png` as the edit target.
Method: deterministic pixel cleanup rather than a new composition; rebuild the tile background, preserve the centered four-band raindrop, and keep genuine transparency outside the rounded tile.
Constraints: change only stray tile artifacts; no text, letters, numbers, logos, watermark, fine detail, thin lines, scenery, or additional objects.
```

## Derivation

`rain-themes-source.png` is the cleaned 1254x1254 RGBA PNG. Each numbered icon was resized directly from that source using Pillow's Lanczos resampling (`Image.Resampling.LANCZOS`), then saved as an optimized RGBA PNG. The source and every numbered file have transparent corner pixels. Corner inspection found no bright background pixels in the four tile-corner windows; all seven numbered files were inspected at native size.

At 16x16, the rounded tile remains a strong dark silhouette and the drop remains a single readable shape with four broad colour bands; no fine detail is required to distinguish the rain/palette mark.

## SHA-256

| File | SHA-256 |
| --- | --- |
| `rain-themes-source.png` | `4d21d2216c448bd1e6f2f8c86e2dff16a1ee3d81b86759f417fb7633393821d2` |
| `rain-themes-256.png` | `e7b9d947d6153d1f7ce841a1ac3d5669a4044cb92b9e91daf6e0aebf5dd2d13e` |
| `rain-themes-128.png` | `3ef55481430aa8f82a31242078f33bcc5824ce65a8e596507dde44886295e7df` |
| `rain-themes-64.png` | `1b7a91c88bde27de3c70b06a822abd10a475f8b96085b98b1fb29bc880445231` |
| `rain-themes-48.png` | `0c2157921f3a6f499c84c6fb85f9e8bb6574fa210ee47259d0383b40911e3e1e` |
| `rain-themes-32.png` | `c41ba0c2a57cd3f1bc07f395bf04c7e3283881f78e4dcb32cd841264774f7d65` |
| `rain-themes-24.png` | `603b1daf5194d6fb94483db1b93ed4d0dbb0623ee44d6a286abd7c131b7ec4c4` |
| `rain-themes-16.png` | `d54fb0ef0b2b40babd58d4676eb7341f9477d493b58126f6ffe8af025a1c0c27` |
