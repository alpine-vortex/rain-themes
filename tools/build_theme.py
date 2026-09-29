#!/usr/bin/env python3
"""Build a Rain (Bunny spec 2) theme from a palette spec.

    python3 tools/build_theme.py <theme-dir | spec.json> [--out DIR]

Reads <theme-dir>/theme.spec.json and writes, next to it:
    <slug>.json           the theme
    <slug>-preview.html   static mockup (colours read from the theme only)
    <slug>-notes.md       palette, mapping table, derived shades, contrast

Exits non-zero if a structural check fails; contrast failures are reported
(and marked FAIL) but do not stop the build. See tools/README.md for the
spec format.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent

# role id -> (legend label, semantic keys). Order here is legend order;
# key order in the output follows reference_keys.json.
GROUPS = [
    ("main_bg", "Main background", "BACKGROUND_PRIMARY BG_BASE_PRIMARY BACKGROUND_MOBILE_PRIMARY CHAT_BACKGROUND BACKGROUND_BASE_LOW CHANNEL_BACKGROUND_DEFAULT STANDALONE_CHANNEL_CONTENT_BACKGROUND"),
    ("secondary_bg", "Secondary background", "BACKGROUND_SECONDARY BG_BASE_SECONDARY BACKGROUND_MOBILE_SECONDARY BACKGROUND_BASE_LOWER CHAT_BANNER_BG BACKGROUND_SECONDARY_ALT"),
    ("tertiary_bg", "Tertiary background", "BACKGROUND_TERTIARY BG_BASE_TERTIARY BACKGROUND_BASE_LOWEST"),
    ("floating_bg", "Floating surfaces", "BACKGROUND_FLOATING BACKGROUND_SURFACE_HIGH MODAL_BACKGROUND MODAL_FOOTER_BACKGROUND MOBILE_ACTIONSHEET_BACKGROUND MOBILE_ACTIONSHEET_GRADIENT_BACKGROUND_DEFAULT CARD_PRIMARY_BG CARD_BACKGROUND_DEFAULT MOBILE_EMBED_BACKGROUND_DEFAULT BG_SURFACE_OVERLAY BG_SURFACE_OVERLAY_TMP"),
    ("nested_floating_bg", "Nested floating", "BACKGROUND_NESTED_FLOATING BACKGROUND_SURFACE_HIGHEST"),
    ("input_bg", "Inputs", "CHAT_INPUT_BACKGROUND REDESIGN_CHAT_INPUT_BACKGROUND CHAT_INPUT_CONTAINER_BACKGROUND INPUT_BACKGROUND INPUT_BACKGROUND_DEFAULT"),
    ("hover", "Hover / subtle / borders", "BACKGROUND_MODIFIER_HOVER BACKGROUND_MESSAGE_HOVER BACKGROUND_MOD_SUBTLE BG_MOD_SUBTLE BACKGROUND_MODIFIER_ACCENT BORDER_SUBTLE BORDER_FAINT BORDER_MUTED"),
    ("active", "Active", "BACKGROUND_MODIFIER_ACTIVE BACKGROUND_MOD_NORMAL"),
    ("faint", "Faint", "BG_MOD_FAINT BACKGROUND_MOD_MUTED"),
    ("selected", "Selected", "BACKGROUND_MODIFIER_SELECTED BACKGROUND_MOD_STRONG BG_MOD_STRONG MOBILE_CHANNEL_ITEM_BACKGROUND_SELECTED"),
    ("text_strong", "Text strong", "HEADER_PRIMARY TEXT_PRIMARY TEXT_STRONG ICON_STRONG INTERACTIVE_HOVER INTERACTIVE_TEXT_HOVER INTERACTIVE_ICON_HOVER"),
    ("text_normal", "Text normal", "TEXT_NORMAL TEXT_DEFAULT HEADER_SECONDARY ICON_DEFAULT"),
    ("text_secondary", "Text secondary", "TEXT_SECONDARY TEXT_SUBTLE ICON_SUBTLE CHANNELS_DEFAULT CHANNEL_ICON INTERACTIVE_NORMAL INTERACTIVE_TEXT_DEFAULT INTERACTIVE_ICON_DEFAULT"),
    ("text_muted", "Text muted", "TEXT_MUTED ICON_MUTED INPUT_PLACEHOLDER_TEXT INPUT_PLACEHOLDER_TEXT_DEFAULT CHANNEL_TEXT_AREA_PLACEHOLDER"),
    ("interactive_muted", "Interactive muted", "INTERACTIVE_MUTED"),
    ("brand", "Brand / accent", "BG_BRAND BACKGROUND_BRAND REDESIGN_BUTTON_PRIMARY_BACKGROUND CONTROL_PRIMARY_BACKGROUND_DEFAULT CONTROL_BRAND_FOREGROUND CHAT_INPUT_SEND_BUTTON_ACTIVE_BACKGROUND BADGE_BACKGROUND_BRAND FOCUS_PRIMARY BORDER_FOCUS INPUT_BORDER_ACTIVE"),
    ("brand_bright", "Brand bright (pressed, active, TEXT_BRAND)", "REDESIGN_BUTTON_PRIMARY_PRESSED_BACKGROUND CONTROL_PRIMARY_BACKGROUND_ACTIVE TEXT_BRAND INTERACTIVE_ACTIVE INTERACTIVE_TEXT_ACTIVE INTERACTIVE_ICON_ACTIVE"),
    ("text_on_brand", "Text on accent", "REDESIGN_BUTTON_PRIMARY_TEXT CONTROL_PRIMARY_TEXT_DEFAULT BADGE_TEXT_BRAND CHAT_INPUT_SEND_BUTTON_ICON_ACTIVE_TINT"),
    ("link", "Links", "TEXT_LINK"),
    ("danger", "Danger / DND", "TEXT_DANGER TEXT_FEEDBACK_CRITICAL ICON_FEEDBACK_CRITICAL INFO_DANGER_TEXT STATUS_DANGER INFO_DANGER_FOREGROUND STATUS_DANGER_BACKGROUND REDESIGN_BUTTON_DANGER_BACKGROUND CONTROL_CRITICAL_PRIMARY_BACKGROUND_DEFAULT STATUS_DND ICON_STATUS_DND"),
    ("positive", "Positive / online", "TEXT_POSITIVE TEXT_FEEDBACK_POSITIVE ICON_FEEDBACK_POSITIVE INFO_POSITIVE_TEXT STATUS_POSITIVE INFO_POSITIVE_FOREGROUND STATUS_ONLINE ICON_STATUS_ONLINE TEXT_STATUS_ONLINE"),
    ("warning", "Warning / idle", "TEXT_WARNING TEXT_FEEDBACK_WARNING ICON_FEEDBACK_WARNING INFO_WARNING_TEXT STATUS_WARNING INFO_WARNING_FOREGROUND STATUS_IDLE ICON_STATUS_IDLE"),
    ("mention", "Mentions", "BACKGROUND_MENTIONED MESSAGE_MENTIONED_BACKGROUND_DEFAULT"),
    ("mention_hover", "Mentions hover", "BACKGROUND_MENTIONED_HOVER MESSAGE_MENTIONED_BACKGROUND_HOVER"),
    ("backdrop", "Backdrops", "BG_BACKDROP MOBILE_BACKGROUND_SCRIM_OPAQUE"),
]
RAW = ["BRAND_500", "BRAND_530", "BRAND_560", "PRIMARY_630", "PRIMARY_660", "PRIMARY_700", "PRIMARY_800"]
RAW_DEFAULTS = {"BRAND_500": "brand", "BRAND_530": "brand_bright"}  # role ids
SURFACE_ROLES = {"main_bg", "secondary_bg", "tertiary_bg", "floating_bg", "nested_floating_bg", "input_bg"}
TEXT_ROLES = {"text_strong", "text_normal", "text_secondary", "text_muted", "interactive_muted",
              "text_on_brand", "link", "brand_bright", "danger", "positive", "warning"}

PREVIEW_DEFAULTS = {
    "subtitle": "", "server_name": "Theme Lounge", "server_initial": "", "tagline": "General chat",
    "users": ["alice", "bob_dev", "carol", "helper_bot", "dave"], "me": "you",
    "msg1": "Morning — switched my terminal over.", "mention_msg": "can you post your Rain theme?",
    "link_text": "", "embed_title": "", "embed_desc": "", "msg4": "Build passed ✔ theme validated.",
    "msg5": "Colours look great on OLED.",
}


class SpecError(Exception):
    pass


# ---------- colour helpers ----------
HEX = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


def rgb(h):
    return [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def alpha(h):
    return int(h[7:9], 16) / 255 if len(h) == 9 else 1.0


def over(fg, bg):
    """Composite fg (maybe 8-digit) over opaque bg -> 6-digit hex."""
    a = alpha(fg)
    return "#" + "".join("%02X" % round((x * a + y * (1 - a)) * 255) for x, y in zip(rgb(fg), rgb(bg[:7])))


def lum(h):
    return sum(w * (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
               for w, c in zip((0.2126, 0.7152, 0.0722), rgb(h)))


def contrast(a, b):
    x, y = sorted([lum(a), lum(b)])
    return (y + 0.05) / (x + 0.05)


def hue(h):
    import colorsys
    return colorsys.rgb_to_hls(*rgb(h))[0] * 360


def mix(a, b, t):
    return "#" + "".join("%02X" % round(x * 255 * (1 - t) + y * 255 * t) for x, y in zip(rgb(a), rgb(b)))


# ---------- spec resolution ----------
class Resolver:
    """Colour refs: "name", "name@AA" (hex alpha), {"mix": [a, b, t]} with optional "alpha"."""

    def __init__(self, palette, roles_doc):
        self.p = {k: v.upper() for k, v in palette.items()}
        self.roles_doc = roles_doc or {}
        self.derived = []
        for k, v in self.p.items():
            if not HEX.match(v) or len(v) != 7:
                raise SpecError(f"palette {k}: {v!r} is not a 6-digit hex")

    def name(self, n):
        return n

    def __call__(self, ref):
        if isinstance(ref, dict):
            a, b, t = ref["mix"]
            c = mix(self.p[a], self.p[b], t)
            frac = f"{round((1 - t) * 100)}% {a} + {round(t * 100)}% {b}"
            label = f"DERIVED: {frac}"
            if (c, label) not in self.derived:
                self.derived.append((c, label))
            if "alpha" in ref:
                c += ref["alpha"].upper()
                label += f" @ {round(int(ref['alpha'], 16) / 2.55)}%"
            return c, label
        n, _, a = ref.partition("@")
        if n not in self.p:
            raise SpecError(f"unknown palette colour {n!r}")
        if a:
            if not re.fullmatch(r"[0-9A-Fa-f]{2}", a):
                raise SpecError(f"bad alpha in {ref!r}")
            return self.p[n] + a.upper(), f"{n} @ {round(int(a, 16) / 2.55)}%"
        return self.p[n], self.name(n)


def build(spec_path, out_dir=None):
    spec_path = Path(spec_path)
    if spec_path.is_dir():
        spec_path = spec_path / "theme.spec.json"
    spec = json.loads(spec_path.read_text())
    out_dir = Path(out_dir) if out_dir else spec_path.parent
    slug = spec["slug"]
    ref_keys = json.loads((TOOLS / "reference_keys.json").read_text())
    R = Resolver(spec["palette"], spec.get("palette_roles"))
    roles = spec["roles"]
    bg = spec.get("background")

    # --- resolve groups
    resolved = {}  # role -> (hex, label)
    sem = {}
    for rid, label, keys in GROUPS:
        if rid not in roles:
            raise SpecError(f"roles.{rid} missing")
        resolved[rid] = R(roles[rid])
        for k in keys.split():
            if k in sem:
                raise SpecError(f"{k} assigned twice")
            sem[k] = resolved[rid][0]
    extra = set(roles) - {g[0] for g in GROUPS}
    if extra:
        raise SpecError(f"unknown roles: {sorted(extra)}")
    if set(sem) != set(ref_keys["semanticColors"]):
        raise SpecError(f"semantic key mismatch: {set(ref_keys['semanticColors']) ^ set(sem)}")

    raw_refs = spec["raw"]
    raw, raw_labels = {}, {}
    for k in RAW:
        if k in raw_refs:
            raw[k], raw_labels[k] = R(raw_refs[k])
        elif k in RAW_DEFAULTS:
            raw[k], raw_labels[k] = resolved[RAW_DEFAULTS[k]]
        else:
            raise SpecError(f"raw.{k} missing")
        if len(raw[k]) != 7:
            raise SpecError(f"raw.{k} must be opaque")
    if set(raw) != set(ref_keys["rawColors"]):
        raise SpecError("raw key mismatch")

    # --- background-image rules
    for rid in SURFACE_ROLES:
        c = resolved[rid][0]
        if bg and len(c) != 9:
            raise SpecError(f"{rid}: background image set, surfaces need 8-digit hex (got {c})")
        if not bg and len(c) != 7:
            raise SpecError(f"{rid}: no background image, surfaces should be opaque (got {c})")
    for rid in TEXT_ROLES:
        if len(resolved[rid][0]) != 7:
            raise SpecError(f"{rid}: text/icon colours must be 6-digit hex")

    theme = {
        "spec": 2,
        "name": spec["name"],
        "description": spec["description"],
        "authors": [{"name": a} for a in spec["authors"]],
        "semanticColors": {k: [sem[k]] for k in ref_keys["semanticColors"]},
        "rawColors": {k: raw[k] for k in ref_keys["rawColors"]},
    }
    if bg:
        theme["background"] = {"url": bg["url"], "blur": bg["blur"], "alpha": bg["alpha"]}
    text = json.dumps(theme, indent=2) + "\n"
    json.loads(text)
    (out_dir / f"{slug}.json").write_text(text)

    # --- contrast
    base = raw["PRIMARY_800"]
    if bg:
        # worst case for light text: a white image pixel at the theme's alpha over the base
        under = over("#FFFFFF" + "%02X" % round(bg["alpha"] * 255), base)
    else:
        under = base

    def eff(c, beneath=None):
        return over(c, beneath or under) if len(c) == 9 else c

    C = {r: resolved[r][0] for r in resolved}
    surf = {r: eff(C[r]) for r in SURFACE_ROLES}
    rows = []

    def chk(name, fg, bgc, need):
        r = contrast(fg, bgc)
        status = ("PASS" if r >= need else "FAIL") if need else "info"
        rows.append((name, fg, bgc, r, need, status))

    for s in ("main_bg", "secondary_bg", "floating_bg", "input_bg"):
        chk(f"text_normal on {s}", C["text_normal"], surf[s], 4.5)
    chk("text_normal on nested_floating_bg", C["text_normal"], surf["nested_floating_bg"], 4.5)
    chk("text_secondary on secondary_bg", C["text_secondary"], surf["secondary_bg"], 4.5)
    chk("text_strong on selected (composited on secondary)", C["text_strong"], over(C["selected"], surf["secondary_bg"]), 4.5)
    chk("text_normal on mention (composited on main)", C["text_normal"], over(C["mention"], surf["main_bg"]), 4.5)
    chk("link on main_bg", C["link"], surf["main_bg"], 4.5)
    chk("text_on_brand on brand", C["text_on_brand"], C["brand"], 4.5)
    chk("text_on_brand on brand_bright", C["text_on_brand"], C["brand_bright"], 4.5)
    chk("brand_bright (TEXT_BRAND) on main_bg", C["brand_bright"], surf["main_bg"], 4.5)
    for r in ("danger", "positive", "warning"):
        chk(f"{r} on main_bg", C[r], surf["main_bg"], 3.0)
    chk("danger on secondary_bg", C["danger"], surf["secondary_bg"], 3.0)
    chk("text_muted on main_bg", C["text_muted"], surf["main_bg"], None)
    chk("text_muted (placeholder) on input_bg", C["text_muted"], surf["input_bg"], None)
    chk("interactive_muted on secondary_bg", C["interactive_muted"], surf["secondary_bg"], None)

    on_danger_opts = {"TEXT_STRONG": C["text_strong"], "REDESIGN_BUTTON_PRIMARY_TEXT": C["text_on_brand"]}
    on_danger = max(on_danger_opts, key=lambda k: contrast(on_danger_opts[k], C["danger"]))
    chk(f"{on_danger} on danger (preview danger button)", on_danger_opts[on_danger], C["danger"], None)

    warnings = []
    for r in ("danger", "positive", "warning"):
        dh = abs(hue(C["brand"]) - hue(C[r]))
        dh = min(dh, 360 - dh)
        if dh < 20:
            warnings.append(f"brand and {r} hues are only {dh:.0f}° apart — may be hard to tell apart")
    if contrast(C["brand"], C["link"]) < 1.2 and abs(hue(C["brand"]) - hue(C["link"])) < 20:
        warnings.append("link colour is very close to brand")
    if C["brand"] == C["link"]:
        warnings.append("link colour equals brand")

    # --- preview
    pv = dict(PREVIEW_DEFAULTS)
    pv.update(spec.get("preview", {}))
    src = spec.get("source", "")
    short = re.sub(r"^https?://", "", src).rstrip("/")
    pv["link_text"] = pv["link_text"] or short or "example.com"
    pv["embed_title"] = pv["embed_title"] or re.sub(r"^github\.com/", "", short) or spec["name"]
    pv["embed_desc"] = pv["embed_desc"] or spec["description"][:60]
    pv["server_initial"] = pv["server_initial"] or spec["name"][0].upper()
    pv["subtitle"] = pv["subtitle"] or spec.get("variant", "")
    root = [f"  --{k}: {v[0]};" for k, v in theme["semanticColors"].items()]
    root += [f"  --{k}: {v};" for k, v in theme["rawColors"].items()]
    root.append(f"  --PREVIEW_ON_DANGER: var(--{on_danger});")
    root.append(f"  --PREVIEW_PHONE_BASE: var(--{'PRIMARY_800' if bg else 'BACKGROUND_PRIMARY'});")
    legend = []
    for rid, label, keys in GROUPS:
        c, lab = resolved[rid]
        legend.append(f'    <div class="row"><span class="sw"><i style="background:var(--{keys.split()[0]})"></i></span>'
                      f'<div><b>{html.escape(label)}</b><small>{html.escape(lab)}</small></div><code>{c}</code></div>')
    legend.append(f'    <div class="row"><span class="sw"><i style="background:var(--BRAND_560)"></i></span>'
                  f'<div><b>BRAND_560 (raw)</b><small>{html.escape(raw_labels["BRAND_560"])}</small></div><code>{raw["BRAND_560"]}</code></div>')
    bg_layer = ""
    if bg:
        bg_layer = (f'<div class="bgimg" style="background-image:url(&quot;{html.escape(bg["url"])}&quot;);'
                    f'filter:blur({bg["blur"]}px);opacity:{bg["alpha"]}"></div>')
    subs = {
        "TITLE": f"{spec['name']} Preview", "NAME": spec["name"], "SUBTITLE": pv["subtitle"],
        "SERVER_NAME": pv["server_name"], "SERVER_INITIAL": pv["server_initial"], "TAGLINE": pv["tagline"],
        "MSG1": pv["msg1"], "MENTION_MSG": pv["mention_msg"], "LINK_TEXT": pv["link_text"],
        "EMBED_TITLE": pv["embed_title"], "EMBED_DESC": pv["embed_desc"], "MSG4": pv["msg4"], "MSG5": pv["msg5"],
        "ME": pv["me"], "ME_INITIAL": pv["me"][0].upper(),
    }
    for i, u in enumerate(pv["users"][:5], 1):
        subs[f"USER{i}"] = u
    page = (TOOLS / "preview_template.html").read_text()
    page = page.replace("__ROOT__", "\n".join(root)).replace("__LEGEND__", "\n".join(legend))
    page = page.replace("{{BG_LAYER}}", bg_layer)
    for k, v in subs.items():
        page = page.replace("{{" + k + "}}", html.escape(v))
    left = re.findall(r"\{\{\w+\}\}", page)
    if left:
        raise SpecError(f"unfilled template placeholders: {set(left)}")
    # no colour outside :root (legend <code> hex text and the bg-image style excluded)
    body = re.sub(r":root \{.*?\n\}", "", page, count=1, flags=re.S)
    body = re.sub(r"<code>#[0-9A-F]+</code>", "", body)
    body = re.sub(r'<div class="bgimg"[^>]*>', "", body)
    body = re.sub(r"<(p|small|h1|h2)[^>]*>.*?</\1>", "", body)  # prose may say "black"
    leak = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|(?<![-\w])(?:white|black|transparent)(?![-\w])", body)
    if leak:
        raise SpecError(f"hard-coded colours in preview: {leak[:5]}")
    defined = set(re.findall(r"--([A-Z_0-9]+):", page))
    undefined = set(re.findall(r"var\(--([A-Z_0-9]+)", page)) - defined
    if undefined:
        raise SpecError(f"undefined CSS vars: {undefined}")
    (out_dir / f"{slug}-preview.html").write_text(page)

    # --- notes
    n = [f"# {spec['name']} — theme notes", "",
         f"- Source: {src}", f"- Variant: {spec.get('variant', '')}", f"- Generated by `tools/build_theme.py` from `theme.spec.json`.", ""]
    if spec.get("notes"):
        n += ["## Notes", ""] + [f"- {x}" for x in spec["notes"]] + [""]
    n += ["## Derived shades", ""]
    n += [f"- `{c}` — {lab}" for c, lab in R.derived] or ["- None: every colour is a palette colour."]
    n += ["", "## Mapping", "", "| Key group | Hex | Palette colour |", "|---|---|---|"]
    n += [f"| {label} | `{resolved[rid][0]}` | {resolved[rid][1]} |" for rid, label, _ in GROUPS]
    n += [f"| {k} (raw) | `{raw[k]}` | {raw_labels[k]} |" for k in RAW]
    n += ["", "## Contrast (WCAG)", ""]
    if bg:
        n += [f"Translucent surfaces judged over a worst-case white image pixel (`{under}` effective).", ""]
    n += ["| Pair | FG | BG | Ratio | Need | |", "|---|---|---|---|---|---|"]
    n += [f"| {a} | `{f}` | `{b}` | {r:.2f} | {nd or '—'} | {s} |" for a, f, b, r, nd, s in rows]
    if warnings:
        n += ["", "## Warnings", ""] + [f"- {w}" for w in warnings]
    n += ["", "## Full source palette", "", "| Name | Hex | Role |", "|---|---|---|"]
    n += [f"| {k} | `{v}` | {R.roles_doc.get(k, '')} |" for k, v in R.p.items()]
    n += ["", "## Install", "", f"Host `{slug}.json` at a raw URL (e.g. raw.githubusercontent.com), then add it by URL in Rain → Themes.", ""]
    (out_dir / f"{slug}-notes.md").write_text("\n".join(n))

    # --- console summary
    print(f"{slug}: wrote {slug}.json, {slug}-preview.html, {slug}-notes.md in {out_dir}")
    for a, f, b, r, nd, s in rows:
        if s != "PASS":
            print(f"  {s:4} {r:5.2f}  {a}  {f} on {b}")
    for w in warnings:
        print(f"  WARN {w}")
    for c, lab in R.derived:
        print(f"  derived {c}  {lab}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="+", help="theme dir(s) or theme.spec.json path(s)")
    ap.add_argument("--out", help="output dir (default: next to the spec)")
    args = ap.parse_args()
    rc = 0
    for s in args.spec:
        try:
            build(s, args.out)
        except (SpecError, KeyError) as e:
            print(f"{s}: ERROR {e}", file=sys.stderr)
            rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
