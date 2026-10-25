#!/usr/bin/env python3
"""Forgejo web UI themes, and the command that gathers them for a server.

    python3 tools/forgejo_export.py [--out DIR] [--check]

desktop_export.py calls themes() for each palette and writes the files into
<slug>/desktop/: theme-rain-<slug>.css (dark), plus theme-rain-<slug>-light.css and
theme-rain-<slug>-auto.css (follows the browser) for palettes whose spec has an
official light flavour.

This script copies every palette's files into DIR (default ./forgejo-themes) and prints
the [ui] THEMES line for app.ini. DIR is meant to be Forgejo's
$FORGEJO_CUSTOM/public/assets/css. --check writes nothing and exits 1 if DIR differs.

Each theme imports Forgejo's own dark or light theme and overrides its colour
variables, so rules Forgejo ships (emoji fixes, labels) keep working. Dark themes also
recolour code (chroma) with the spec's syntax colours; light ones keep Forgejo's, as
specs have no light syntax colours. See tools/README.md ("Forgejo").
"""
import argparse
import filecmp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_theme import mix  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "theme-rain-"


def alpha(h, a):
    return f"{h}{a}"


def variables(t, c, dark):
    """Forgejo's colour variables (web_src/css/themes/theme-forgejo-*.css) from an app-theme v1 block.
    `c` is the palette's desktop Colours: the Actions console stays a dark terminal in both modes."""
    bg, text, acc, line = t["background"], t["text"], t["accent"], t["line"]
    raised, sel, panel = t["raised"], t["selected"], t["panel"]
    muted, sec = t["text_muted"], t["text_secondary"]
    term, r = c.term, c.role
    v = {"--is-dark-theme": "true" if dark else "false"}
    # Forgejo's "dark-N" steps move toward the text colour and "light-N" toward the page, in both modes.
    v["--color-primary"] = acc
    v["--color-primary-contrast"] = t["on_accent"]
    for i, w in enumerate((0.1, 0.2, 0.3, 0.4), 1):
        v[f"--color-primary-dark-{i}"] = mix(acc, text, w)
    for i, w in enumerate((0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7), 1):
        v[f"--color-primary-light-{i}"] = mix(acc, bg, w)
    for n, a in ((10, "19"), (20, "33"), (30, "4B"), (40, "66"), (50, "80"), (60, "99"), (70, "B3"), (80, "CC"),
                 (90, "E1")):
        v[f"--color-primary-alpha-{n}"] = alpha(acc, a)
    v["--color-secondary"] = line
    for i in range(1, 14):
        v[f"--color-secondary-dark-{i}"] = mix(line, text, min(i, 10) / 10)
    for i in range(1, 5):
        v[f"--color-secondary-light-{i}"] = mix(line, bg, i / 5)
    for n, a in ((10, "19"), (20, "33"), (30, "4B"), (40, "66"), (50, "80"), (60, "99"), (70, "B3"), (80, "CC"),
                 (90, "E1")):
        v[f"--color-secondary-alpha-{n}"] = alpha(line, a)
    v.update({
        "--color-console-fg": term["foreground"], "--color-console-fg-subtle": r["text_muted"],
        "--color-console-bg": r["tertiary_bg"], "--color-console-border": r["nested_floating_bg"],
        "--color-console-hover-bg": alpha(term["foreground"], "16"), "--color-console-active-bg": term["selection"],
        "--color-console-menu-bg": r["floating_bg"], "--color-console-menu-border": r["nested_floating_bg"],
    })
    names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    for i, h in enumerate(c.ansi):
        v[f"--color-ansi-{'bright-' if i > 7 else ''}{names[i % 8]}"] = h
    ok, bad, warn, info = t["positive"], t["danger"], t["warning"], t["link"]
    v.update({
        "--color-diff-removed-word-bg": mix(bad, bg, 0.6), "--color-diff-added-word-bg": mix(ok, bg, 0.6),
        "--color-diff-removed-row-bg": mix(bad, bg, 0.82), "--color-diff-moved-row-bg": mix(warn, bg, 0.82),
        "--color-diff-added-row-bg": mix(ok, bg, 0.82),
        "--color-diff-removed-row-border": mix(bad, bg, 0.6), "--color-diff-moved-row-border": mix(warn, bg, 0.55),
        "--color-diff-added-row-border": mix(ok, bg, 0.6), "--color-diff-inactive": raised,
    })
    for name, col in (("error", bad), ("success", ok), ("warning", warn), ("info", info)):
        v[f"--color-{name}-border"] = mix(col, bg, 0.5)
        v[f"--color-{name}-bg"] = mix(col, bg, 0.8)
        v[f"--color-{name}-text"] = mix(col, text, 0.5)
    v["--color-error-bg-active"] = v["--color-error-bg-hover"] = mix(bad, bg, 0.7)
    for name, col in (("red", bad), ("green", ok), ("yellow", warn), ("orange", t["state"])):
        v[f"--color-{name}-badge"] = col
        v[f"--color-{name}-badge-bg"] = alpha(col, "22")
        v[f"--color-{name}-badge-hover-bg"] = alpha(col, "44")
    box = mix(bg, raised, 0.35)
    head = mix(bg, raised, 0.7)
    hover = mix(raised, sel, 0.5)
    v.update({
        "--color-body": bg, "--color-box-header": head, "--color-box-body": box, "--color-box-body-highlight": raised,
        "--color-text-dark": text, "--color-text": text, "--color-text-light": sec, "--color-text-light-1": sec,
        "--color-text-light-2": mix(sec, muted, 0.5), "--color-text-light-3": muted,
        "--color-footer": panel, "--color-timeline": line,
        "--color-input-text": text, "--color-input-background": mix(bg, raised, 0.5) if dark else bg,
        "--color-input-toggle-background": mix(bg, raised, 0.5) if dark else bg,
        "--color-input-border": mix(line, t["border"], 0.4), "--color-input-border-hover": t["border"],
        "--color-header-wrapper": panel, "--color-header-wrapper-transparent": alpha(panel, "00"),
        "--color-hover": hover, "--color-active": sel, "--color-menu": head, "--color-card": box,
        "--fancy-card-bg": head, "--fancy-card-border": line,
        "--color-markup-code-block": panel, "--color-markup-code-inline": raised,
        "--color-button": raised, "--color-code-bg": bg, "--color-secondary-bg": head,
        "--color-placeholder-text": muted, "--color-editor-line-highlight": mix(bg, raised, 0.5),
        "--color-project-board-bg": panel, "--color-caret": text,
        "--color-reaction-bg": alpha(text, "12"),
        "--color-tooltip-text": bg, "--color-tooltip-bg": text,
        "--color-nav-bg": panel, "--color-nav-hover-bg": sel, "--color-secondary-nav-bg": bg,
        "--color-label-text": text, "--color-label-bg": raised, "--color-label-hover-bg": sel,
        "--color-label-active-bg": mix(sel, t["border"], 0.4), "--color-label-bg-alt": sel,
        "--color-accent": acc, "--color-small-accent": v["--color-primary-light-5"],
        "--color-highlight-fg": mix(acc, text, 0.3), "--color-highlight-bg": v["--color-primary-alpha-20"],
        "--color-selection-bg": term["selection"] if dark else mix(acc, bg, 0.65),
        "--color-selection-fg": term["foreground"] if dark else text,
        "--color-indicator-offline": muted, "--color-indicator-offline-20": alpha(muted, "1A"),
        "--color-indicator-idle": ok, "--color-indicator-idle-20": alpha(ok, "1A"),
        "--color-indicator-active": info, "--color-indicator-active-20": alpha(info, "33"),
    })
    return v


# chroma token classes (web_src/css/chroma/*.css) -> spec syntax key
CHROMA = {
    "c": "comment", "c1": "comment", "ch": "comment", "cm": "comment", "cs": "comment", "cpf": "string",
    "cp": "preprocessor", "k": "keyword", "kd": "storage", "kn": "keyword", "kp": "keyword", "kr": "keyword",
    "kt": "type", "kc": "constant", "s": "string", "s1": "string", "s2": "string", "sa": "string", "sb": "string",
    "sc": "string", "sd": "comment", "sh": "string", "sr": "string", "ss": "constant", "sx": "string",
    "dl": "string", "se": "constant", "si": "operator", "m": "number", "mb": "number", "mf": "number",
    "mh": "number", "mi": "number", "il": "number", "mo": "number", "o": "operator", "ow": "keyword",
    "na": "attribute", "nb": "builtin", "bp": "builtin", "nc": "class", "nd": "preprocessor", "ne": "class",
    "nf": "function", "fm": "function", "nn": "type", "no": "constant", "nt": "tag", "nl": "parameter",
    "gh": "keyword", "gu": "function", "gr": "error", "gt": "error", "err": "error",
}


def chroma(c):
    s, fg, bg = c.syntax, c.term["foreground"], c.term["background"]
    lines = [f".chroma .{k} {{ color: {s[v]}; }}" for k, v in CHROMA.items()]
    lines += [f".chroma .gi {{ color: {fg}; background-color: {mix(s['added'], bg, 0.75)}; }}",
              f".chroma .gd {{ color: {fg}; background-color: {mix(s['removed'], bg, 0.75)}; }}",
              ".chroma .ge { font-style: italic; }", ".chroma .gs { font-weight: bold; }"]
    return "\n".join(lines) + "\n"


def theme_css(t, c, name, dark):
    base = "dark" if dark else "light"
    body = "\n".join(f"  {k}: {v};" for k, v in variables(t, c, dark).items())
    css = (f"/* Rain {name} ({base}) for Forgejo. Generated by tools/desktop_export.py; do not edit. */\n"
           f'@import "./theme-forgejo-{base}.css";\n\n:root {{\n{body}\n  accent-color: var(--color-accent);\n'
           f"  color-scheme: {base};\n}}\n")
    if dark:
        css += "\n/* code: the palette's syntax colours */\n" + chroma(c)
    return css


def themes(c, at, spec):
    """{file name: css} for one palette; at is its app-theme v1 dict."""
    slug = spec["slug"]
    out = {f"{PREFIX}{slug}.css": theme_css(at, c, spec["name"], True)}
    if "light" in at:
        out[f"{PREFIX}{slug}-light.css"] = theme_css(at["light"], c, at["light"]["flavour"], False)
        out[f"{PREFIX}{slug}-auto.css"] = (
            f"/* Rain {spec['name']}, following the browser: {at['light']['flavour']} when light. */\n"
            f'@import "./{PREFIX}{slug}-light.css";\n'
            f'@import "./{PREFIX}{slug}.css" (prefers-color-scheme: dark);\n')
    return out


def collect():
    """{file name: source path} for every palette's exported Forgejo themes, sorted."""
    return {p.name: p for p in sorted(ROOT.glob(f"*/desktop/{PREFIX}*.css"))}


def theme_names(files):
    """Names for app.ini [ui] THEMES: each dark theme and its -auto; -light files exist for -auto to import."""
    names = [n[len("theme-"):-len(".css")] for n in files]
    return sorted((n for n in names if not n.endswith("-light")), key=lambda n: (n.removesuffix("-auto"), n))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="forgejo-themes")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    files = collect()
    if not files:
        sys.exit("no Forgejo themes exported; run `tools/rain build` first")
    out = Path(a.out)
    if a.check:
        bad = [n for n, src in files.items() if not (out / n).is_file() or not filecmp.cmp(src, out / n, shallow=False)]
        for n in bad:
            print(f"stale or missing: {out / n}")
        sys.exit(1 if bad else 0)
    out.mkdir(parents=True, exist_ok=True)
    for n, src in files.items():
        (out / n).write_bytes(src.read_bytes())
    names = theme_names(files)
    print(f"wrote {len(files)} files to {out}\n")
    print("Add to app.ini (keep the built-in themes you want), then restart Forgejo:\n")
    print("[ui]\nTHEMES = forgejo-auto,forgejo-light,forgejo-dark," + ",".join(names))
    print("\nThen pick a Rain theme in Settings -> Appearance.")


if __name__ == "__main__":
    main()
