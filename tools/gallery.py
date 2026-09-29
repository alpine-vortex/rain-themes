#!/usr/bin/env python3
"""Screenshot every theme preview and build the comparison gallery.

    python3 tools/gallery.py

For each folder with a theme.spec.json, renders <slug>-preview.html in headless
Chromium (Playwright) and saves the two phone screens as <slug>/<slug>-preview.png.
Then writes, at the repo root:
    GALLERY.md   renders on GitHub (images + install URLs)
    index.html   same gallery as a standalone page (open locally or via GitHub Pages)
and refreshes the theme table in README.md between the <!-- themes --> markers.
"""
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/alpine-vortex/rain-themes/main"


def themes():
    out = []
    for spec_path in sorted(ROOT.glob("*/theme.spec.json")):
        spec = json.loads(spec_path.read_text())
        slug = spec["slug"]
        theme = json.loads((spec_path.parent / f"{slug}.json").read_text())
        sc = theme["semanticColors"]
        out.append({
            "slug": slug, "name": spec["name"], "variant": spec.get("variant", ""),
            "dir": spec_path.parent.name,
            "swatches": [sc[k][0][:7] for k in ("BACKGROUND_PRIMARY", "BACKGROUND_SECONDARY", "TEXT_NORMAL",
                                                "BG_BRAND", "TEXT_LINK", "STATUS_DANGER", "STATUS_ONLINE", "STATUS_IDLE")],
        })
    return out


def screenshot(ts):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1320, "height": 1000}, device_scale_factor=1)
        for t in ts:
            page.goto((ROOT / t["dir"] / f"{t['slug']}-preview.html").as_uri())
            page.wait_for_timeout(300)
            box = page.evaluate("""() => {
                const [a, b] = document.querySelectorAll('.phone');
                const r1 = a.getBoundingClientRect(), r2 = b.getBoundingClientRect();
                return {x: r1.left, y: Math.min(r1.top, r2.top),
                        width: r2.right - r1.left, height: Math.max(r1.bottom, r2.bottom) - Math.min(r1.top, r2.top)};
            }""")
            for attempt in range(3):  # Chromium occasionally fails a capture; retry
                try:
                    page.screenshot(path=str(ROOT / t["dir"] / f"{t['slug']}-preview.png"), clip=box)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    page.wait_for_timeout(500)
            print("shot", t["slug"])
        browser.close()


def write_md(ts):
    lines = ["# Theme gallery", "",
             "Previews of every theme (channel list + chat view). Install: copy the URL, then add it by URL in Rain → Themes.",
             "", "Regenerate with `python3 tools/gallery.py`.", ""]
    lines += [f"- [{t['name']}](#{t['slug']})" for t in ts]
    for t in ts:
        lines += ["", f'<a id="{t["slug"]}"></a>', f"## {t['name']}", "", f"*{t['variant']}*", "",
                  f"![{t['name']} preview]({t['dir']}/{t['slug']}-preview.png)", "",
                  f"```\n{RAW}/{t['dir']}/{t['slug']}.json\n```",
                  f"[Notes]({t['dir']}/{t['slug']}-notes.md) · [Spec]({t['dir']}/theme.spec.json)"]
    (ROOT / "GALLERY.md").write_text("\n".join(lines) + "\n")


def write_html(ts):
    cards = []
    for t in ts:
        sw = "".join(f'<i style="background:{c}" title="{c}"></i>' for c in t["swatches"])
        url = f"{RAW}/{t['dir']}/{t['slug']}.json"
        cards.append(f"""  <article class="card" id="{t['slug']}">
    <header><h2>{html.escape(t['name'])}</h2><span class="sw">{sw}</span></header>
    <p class="variant">{html.escape(t['variant'])}</p>
    <a href="{t['dir']}/{t['slug']}-preview.html"><img src="{t['dir']}/{t['slug']}-preview.png" alt="{html.escape(t['name'])} preview" loading="lazy"></a>
    <div class="install"><code>{url}</code><button type="button" data-url="{url}">Copy</button></div>
  </article>""")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rain Theme Gallery</title>
<style>
:root {{ --bg: #111214; --card: #1b1c20; --line: #2c2e34; --text: #e6e6e9; --muted: #9a9ca5; --accent: #8ab4f8; }}
@media (prefers-color-scheme: light) {{ :root {{ --bg: #f4f4f6; --card: #ffffff; --line: #dcdde2; --text: #1c1d21; --muted: #5d606b; --accent: #1a5fd0; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
main {{ max-width: 1400px; margin: 0 auto; padding: 32px 16px 64px; }}
h1 {{ margin: 0 0 4px; font-size: 26px; }}
.lead {{ color: var(--muted); margin: 0 0 20px; }}
nav {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 28px; }}
nav a {{ color: var(--text); text-decoration: none; border: 1px solid var(--line); border-radius: 999px; padding: 4px 12px; font-size: 13px; }}
nav a:hover {{ border-color: var(--accent); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 520px), 1fr)); gap: 20px; }}
.card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px; min-width: 0; }}
.card header {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; }}
.card h2 {{ margin: 0; font-size: 18px; }}
.variant {{ margin: 2px 0 12px; color: var(--muted); font-size: 13px; }}
.sw {{ display: flex; gap: 3px; flex: none; }}
.sw i {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid var(--line); }}
.card img {{ width: 100%; height: auto; display: block; border-radius: 8px; }}
.install {{ display: flex; gap: 8px; align-items: center; margin-top: 12px; }}
.install code {{ flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: var(--muted); }}
.install button {{ flex: none; background: none; color: var(--accent); border: 1px solid var(--line); border-radius: 8px; padding: 4px 10px; cursor: pointer; font: inherit; font-size: 13px; }}
</style>
</head>
<body>
<main>
<h1>Rain Theme Gallery</h1>
<p class="lead">{len(ts)} themes for Rain (Bunny spec 2). Tap a preview for the full mockup and colour legend; copy the URL and add it in Rain → Themes.</p>
<nav>{''.join(f'<a href="#{t["slug"]}">{html.escape(t["name"])}</a>' for t in ts)}</nav>
<div class="grid">
{chr(10).join(cards)}
</div>
</main>
<script>
document.querySelectorAll('.install button').forEach(b => b.addEventListener('click', async () => {{
  try {{ await navigator.clipboard.writeText(b.dataset.url); b.textContent = 'Copied'; }}
  catch (e) {{ b.textContent = 'Copy failed'; }}
  setTimeout(() => b.textContent = 'Copy', 1500);
}}));
</script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page)


def write_readme(ts):
    p = ROOT / "README.md"
    s = p.read_text()
    a, b = s.index("<!-- themes -->") + len("<!-- themes -->"), s.index("<!-- /themes -->")
    rows = ["| Theme | Install URL |", "|---|---|"]
    rows += [f"| [{t['name']}](GALLERY.md#{t['slug']}) | `{RAW}/{t['dir']}/{t['slug']}.json` |" for t in ts]
    p.write_text(s[:a] + "\n" + "\n".join(rows) + "\n" + s[b:])


if __name__ == "__main__":
    ts = themes()
    screenshot(ts)
    write_md(ts)
    write_html(ts)
    write_readme(ts)
    print(f"gallery: {len(ts)} themes -> GALLERY.md, index.html")
