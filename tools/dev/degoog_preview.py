#!/usr/bin/env python3
"""Screenshot the Rain degoog theme in every palette, for the store card.

    python3 tools/dev/degoog_preview.py --url http://127.0.0.1:4455 --out ../degoog-rain/themes/rain/screenshots

Needs a running degoog (a throwaway container, not a live instance) with the Rain theme
active and at least one search engine installed. The palette and light/dark are switched in
the page (html data attributes), so the instance's own settings are never changed.
Headless Chromium: no windows open on the desktop.

Writes 1.png (all palettes, the card thumbnail), 2.png and 3.png (one palette, dark and
its light flavour). Recipe for the container: tools/README.md ("degoog").
"""
import argparse
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from degoog_export import palettes  # noqa: E402

VIEW = (1280, 800)
QUERY = "/search?q=rain+clouds"
FEATURE = "catppuccin-mocha"


def shoot(page, url, slug, mode):
    page.goto(url + QUERY, wait_until="networkidle", timeout=60000)
    page.evaluate("([s, m]) => { const r = document.documentElement;"
                  " r.setAttribute('data-rain-palette', s); r.setAttribute('data-theme', m); }", [slug, mode])
    page.wait_for_timeout(300)
    return page.screenshot()


def grid(shots, cols=7, w=320, crop=(0, 0, 760, 570)):
    """Tiles of the page's top-left (logo, search bar, first results) so each palette reads."""
    h = round(w * (crop[3] - crop[1]) / (crop[2] - crop[0]))
    rows = -(-len(shots) // cols)
    sheet = Image.new("RGB", (cols * w, rows * h), "#000000")
    for i, png in enumerate(shots):
        im = Image.open(BytesIO(png)).convert("RGB").crop(crop).resize((w, h), Image.LANCZOS)
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    return sheet


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pals = palettes()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": VIEW[0], "height": VIEW[1]})
        shots = [shoot(page, a.url, s["slug"], "dark") for s, _ in pals]
        grid(shots).save(out / "1.png", optimize=True)
        (out / "2.png").write_bytes(shoot(page, a.url, FEATURE, "dark"))
        (out / "3.png").write_bytes(shoot(page, a.url, FEATURE, "light"))
        browser.close()
    print(f"degoog preview: {len(pals)} palettes -> {out}")


if __name__ == "__main__":
    main()
