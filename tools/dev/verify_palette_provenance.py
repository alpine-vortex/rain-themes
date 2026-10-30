#!/usr/bin/env python3
"""Verify palette source hashes and value checks in docs/palette-provenance.json."""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/palette-provenance.json"
HEX = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b")


def fetch(url):
    if not url.startswith("https://github.com/") or "/blob/" not in url:
        raise ValueError(f"not a pinned GitHub blob URL: {url}")
    owner_repo, rest = url.removeprefix("https://github.com/").split("/blob/", 1)
    revision, path = rest.split("/", 1)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(f"source revision is not a full commit id: {url}")
    raw = f"https://raw.githubusercontent.com/{owner_repo}/{revision}/{path}"
    with urlopen(raw, timeout=30) as response:
        return response.read()


def resolved_checks(spec, keys, palette, source_hexes):
    result = {}
    for key in keys:
        value = spec.get(key, {})
        entries = list(enumerate(value)) if isinstance(value, list) else list(value.items()) if isinstance(value, dict) else []
        checks = []
        for field, ref in entries:
            if isinstance(ref, str) and ref in palette:
                color = palette[ref].lower()
                checks.append({"field": str(field), "paletteKey": ref, "hex": color,
                               "presentInPinnedSource": color in source_hexes})
            elif isinstance(ref, str) and "#" in ref:
                color = ref.lower()
                checks.append({"field": str(field), "paletteKey": None, "hex": color,
                               "presentInPinnedSource": color in source_hexes})
        result[key] = checks
    return result


def main():
    evidence = json.loads(MANIFEST.read_text())
    problems = []
    cache = {}
    source_count = 0
    palette_count = 0
    field_count = 0
    derived_count = 0
    unmatched_fields = set()

    for slug, record in evidence["palettes"].items():
        spec = json.loads((ROOT / slug / "theme.spec.json").read_text())
        files = []
        for source in record["sourceFiles"]:
            source_count += 1
            url = source["url"]
            try:
                if url not in cache:
                    cache[url] = fetch(url)
                raw = cache[url]
                digest = hashlib.sha256(raw).hexdigest()
                if digest != source["sha256"]:
                    problems.append(f"{slug}: hash changed for {source['path']}")
                files.append(raw.decode("utf-8", "replace"))
            except Exception as exc:  # report all unavailable sources in one run
                problems.append(f"{slug}: cannot verify {source['path']}: {exc}")
        source_text = "\n".join(files).lower()
        source_hexes = {value.lower() for value in HEX.findall(source_text)}

        light = spec.get("light") or {}
        for section, key in ((spec.get("palette", {}), "localPaletteFields"),
                             (light.get("palette", {}), "lightPaletteFields")):
            palette_count += len({v.lower() for v in section.values()
                                  if isinstance(v, str) and HEX.fullmatch(v)})
            fields = {k: v for k, v in section.items()
                      if isinstance(v, str) and HEX.fullmatch(v)}
            if fields != record[key]:
                problems.append(f"{slug}: palette fields differ from manifest")
            values = {v.lower() for v in section.values()
                      if isinstance(v, str) and HEX.fullmatch(v)}
            if not values <= source_hexes:
                problems.append(f"{slug}: palette values absent from pinned source files: "
                                + ", ".join(sorted(values - source_hexes)))
            if len(values) != record["localHexValues" if key == "localPaletteFields"
                                     else "lightHexValues"]:
                problems.append(f"{slug}: palette value count differs from manifest")

        expected_dark = resolved_checks(spec, ("ansi", "terminal", "syntax"),
                                        spec.get("palette", {}), source_hexes)
        expected_light = resolved_checks(light, ("ansi", "app"),
                                         light.get("palette", {}), source_hexes)
        field_count += sum(map(len, expected_dark.values())) + sum(map(len, expected_light.values()))
        if expected_dark != record["sourceFieldChecks"]:
            problems.append(f"{slug}: dark ANSI/terminal/syntax evidence differs from spec or source")
        if expected_light != record["lightSourceFieldChecks"]:
            problems.append(f"{slug}: light ANSI/app evidence differs from spec or source")
        for field_checks in (*expected_dark.values(), *expected_light.values()):
            unmatched_fields.update((slug, check["field"], check["hex"])
                                    for check in field_checks if not check["presentInPinnedSource"])

    documented_derivations = set()
    for item in evidence.get("derivedChecks", []):
        derived_count += 1
        documented_derivations.add((item["slug"], item["field"].split(".")[-1], item["local"].lower()))
        # Match build_theme.over's round-to-nearest alpha composite.
        source, background = item["source"], item["background"]
        alpha = int(source[7:9], 16) / 255
        computed = "#" + "".join(
            f"{round(int(source[i:i+2], 16) * alpha + int(background[i:i+2], 16) * (1-alpha)):02X}"
            for i in (1, 3, 5)
        )
        if computed.lower() != item["local"].lower() or computed.lower() != item["computed"].lower():
            problems.append(f"{item['slug']}: derived value changed for {item['field']}")
        if not item["verified"]:
            problems.append(f"{item['slug']}: derived check is not marked verified")
        spec = json.loads((ROOT / item["slug"] / "theme.spec.json").read_text())
        if spec.get("terminal", {}).get(item["field"].split(".")[-1], "").lower() != item["local"].lower():
            problems.append(f"{item['slug']}: derived value differs from the theme spec")
        if item["source"].lower() not in " ".join(
                fetch(source["url"]).decode("utf-8", "replace").lower()
                for source in evidence["palettes"][item["slug"]]["sourceFiles"]):
            problems.append(f"{item['slug']}: derivation input is absent from pinned source files")

    if unmatched_fields != documented_derivations:
        problems.append("source-field mismatches differ from the documented derivation set")

    if problems:
        print("Palette provenance verification failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        return 1
    print(f"OK: {len(evidence['palettes'])} palettes, {source_count} pinned source records, "
          f"{palette_count} palette hex values, {field_count} source-field checks, "
          f"{derived_count} derived checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
