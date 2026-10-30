# Palette source provenance

## Audit snapshot

`palette-provenance.json` records the source files used for this audit, their
upstream commit IDs, retrieval URLs, and SHA-256 hashes of the downloaded bytes.
The revisions are current upstream branch heads resolved on 2026-10-29. They
are immutable verification references; they do not claim to reconstruct the
historical revisions used when the Rain specs were first extracted.

The audit covered all 21 dark palette specs and all 15 included light palettes.
It compared each stored hex value against the exact pinned source files, then
resolved the spec's ANSI, terminal, and syntax assignments to their palette
hex values and checked them against those same files. All 867 dark and 313
light palette hex values were found. Of 821 dark and 480 light source-field
checks, 1,300 matched source literals directly; the remaining dark terminal
selection was verified by reproducing its documented alpha-composite
transformation. All source downloads succeeded and are hashed in the manifest.

This is a value-presence and assignment-value check. It proves that the
recorded values occur in the cited pinned source files; the source paths and
field mapping for each palette are kept in the corresponding `theme.spec.json`
notes. It does not infer semantic intent from a matching hex alone. Selection,
status, contrast, and role choices that deliberately differ from upstream are
documented in those notes and remain Rain mappings, not upstream canon.

## Documented adaptation

- **Librekai Dimmed selection:** upstream's `#676B7180` is an alpha color.
  Rain composites it over the source editor background (`#1E1E1E`) to produce
  `#434548`, so downstream consumers receive an opaque color. The audit caught
  and corrected a prior one-channel error (`#434448`) in the spec and generated
  exports. The source value and transformation are recorded in the spec notes
  and `palette-provenance.json`.
- **Solarized Osaka:** upstream palette data is expressed in HSL and resolved
  through the plugin's own `hslToHex` implementation. The checked local hexes
  match the pinned resolved theme and terminal source files; the HSL conversion
  and LuaJIT rounding rule are recorded in its spec notes.
- Other selection, contrast, accent, and absent-syntax-token choices are
  listed in the individual spec notes. They are intentional product mappings,
  not claims that upstream assigns those same roles.

## Repeating the audit

Run `python3 tools/dev/verify_palette_provenance.py` to re-download the pinned
files, check their hashes and repeat the value checks. To refresh the audit,
resolve each upstream repository's selected branch to a new commit and create a
new manifest snapshot with updated hashes and comparisons. Do not overwrite
this snapshot when updating sources; retain the old revision and hashes with
the change record.
