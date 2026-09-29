#!/usr/bin/env python3
"""Export a palette spec to desktop app configs (Linux Mint / Cinnamon).

    python3 tools/desktop_export.py <theme-dir> [<theme-dir> ...]

Needs the Rain theme built first (reads <slug>.json for the Discord colours).
Only themes whose spec has "ansi", "terminal" and "syntax" blocks are
exported; others are skipped with a note. Writes <theme-dir>/desktop/:

    colloid-palette.scss     Colloid palette (GTK/Cinnamon theme is built by apply_theme.py)
    colloid.json             colours the Colloid build swaps into stock assets
    gnome-terminal.json      GNOME Terminal profile keys
    geany-<slug>.conf        Geany colour scheme
    userChrome.css           Firefox toolbar/tabs/menus
    userContent.css          Firefox new-tab page
    brave.json               Brave seed colour
    <slug>.theme.css         Vesktop / Vencord theme
    wallpaper-desktop.png    2560x1600
    wallpaper-phone.png      1440x3200 (also steers Android Material You / Niagara)
    sync-theme.json          Sync for Reddit Monet theme (seed + dark text overrides)
    <slug>.app-theme.json    Android app theme, format app-theme v1 (docs/app-theme.md; e.g. redeye)
    README.md                manual steps: Dark Reader, Niagara, Claude Code

See tools/README.md ("Desktop exports").
"""
import colorsys
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_theme import GROUPS, RAW, HEX, Resolver, SpecError, contrast, mix, over, rgb  # noqa: E402

ANSI_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
SYNTAX_KEYS = ["comment", "string", "number", "constant", "keyword", "storage", "type", "class", "function",
               "parameter", "operator", "builtin", "tag", "attribute", "preprocessor", "error",
               "added", "removed", "changed"]
# Niagara's fixed "Standard" swatches, sampled from the app's Theme colour screen.
NIAGARA_SWATCHES = {"grey": "#C8C8C8", "red": "#E86A5C", "orange": "#E8A25C", "yellow": "#E6D85E",
                    "green": "#A2E65C", "teal": "#62E6D0", "blue": "#5CB0E6", "indigo": "#6272E6",
                    "magenta": "#D05CE6"}
DESKTOP_SIZE = (2560, 1600)
PHONE_SIZE = (1440, 3200)


class Colours:
    """Resolved, opaque colours for one spec."""

    def __init__(self, spec):
        R = Resolver(spec["palette"], spec.get("palette_roles"))
        self.R = R
        roles = spec["roles"]
        self.main_bg = self._opaque(R(roles["main_bg"])[0], None)
        base = self.main_bg
        self.role = {}
        for rid, _, _ in GROUPS:
            self.role[rid] = self._opaque(R(roles[rid])[0], base)
        self.ansi = [self.ref(x) for x in spec["ansi"]]
        if len(self.ansi) != 16:
            raise SpecError("ansi must list 16 colours")
        t = spec["terminal"]
        self.term = {k: self.ref(t[k]) for k in ("background", "foreground", "cursor", "selection")}
        # optional: text under a block cursor (defaults to the background, i.e. reverse video)
        self.term["cursor_text"] = self.ref(t["cursor_text"]) if "cursor_text" in t else self.term["background"]
        missing = set(SYNTAX_KEYS) - set(spec["syntax"])
        if missing:
            raise SpecError(f"syntax missing {sorted(missing)}")
        self.syntax = {k: self.ref(spec["syntax"][k]) for k in SYNTAX_KEYS}

    def ref(self, x):
        if isinstance(x, str) and x.startswith("#"):
            if not HEX.match(x) or len(x) != 7:
                raise SpecError(f"bad hex {x!r}")
            return x.upper()
        return self._opaque(self.R(x)[0], self.main_bg)

    @staticmethod
    def _opaque(c, base):
        return c if len(c) == 7 else over(c, base or "#000000")


# ---------- helpers ----------
def hls(h):
    return colorsys.rgb_to_hls(*rgb(h))


def argb_int(h):
    """Chromium stores SkColor as a signed 32-bit int."""
    v = 0xFF000000 | int(h[1:], 16)
    return v - (1 << 32)


def nearest_swatch(h):
    hh, ll, ss = hls(h)
    if ss < 0.2:
        return "grey"
    best, bd = None, 9
    for name, sw in NIAGARA_SWATCHES.items():
        if name == "grey":
            continue
        d = abs(hh - hls(sw)[0])
        d = min(d, 1 - d)
        if d < bd:
            best, bd = name, d
    return best


# ---------- Colloid ----------
def colloid(c):
    """Palette for Colloid's _color-palette-default.scss (dark variant only)."""
    r, a = c.role, c.ansi
    red, green, yellow, blue, purple, teal = a[9], a[10], a[11], a[12], a[13], a[14]
    red_d, green_d, yellow_d, blue_d, purple_d, teal_d = a[1], a[2], a[3], a[4], a[5], a[6]
    pal = c.R.p
    orange = next((pal[k] for k in ("orange", "peach", "bright_orange") if k in pal), mix(red, yellow, 0.5))
    pink = mix(red, purple, 0.5)
    brand = r["brand"]
    brand_dark = mix(brand, r["main_bg"], 0.2)
    # Surfaces Colloid reads in dark mode: 650 surface, 700 window, 750 sidebar/titlebar, 800 panel/OSD.
    greys = {650: r["floating_bg"], 700: r["main_bg"], 750: r["secondary_bg"], 800: r["tertiary_bg"],
             850: mix(r["tertiary_bg"], "#000000", 0.25), 900: mix(r["tertiary_bg"], "#000000", 0.45),
             950: mix(r["tertiary_bg"], "#000000", 0.65)}
    ramp = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600]
    for i, g in enumerate(ramp):
        greys[g] = mix(r["text_strong"], r["nested_floating_bg"], i / (len(ramp) - 1))
    black = mix(r["tertiary_bg"], "#000000", 0.6)
    L = ["// Generated by tools/desktop_export.py — do not edit.", ""]
    for name, lt, dk in [("red", red, red_d), ("pink", pink, mix(pink, "#000000", 0.15)),
                         ("purple", purple, purple_d), ("blue", blue, blue_d), ("teal", teal, teal_d),
                         ("green", green, green_d), ("yellow", yellow, yellow_d),
                         ("orange", orange, mix(orange, "#000000", 0.15))]:
        L += [f"${name}-light: {lt};", f"${name}-dark: {dk};"]
    L += [""] + [f"$grey-{g:03d}: {greys[g]};" for g in sorted(greys)] + [""]
    L += [f"$white: {r['text_strong']};", f"$black: {black};", "",
          f"$button-close: {r['danger']};", f"$button-max: {r['positive']};", f"$button-min: {r['warning']};", "",
          f"$links: {r['link']};", "", f"$default-light: {brand};", f"$default-dark: {brand_dark};", ""]
    # Stock Colloid hex -> ours, for pre-drawn assets (svg/gtkrc/xml) the Sass build doesn't touch.
    swap = {"#5b9bf8": brand, "#3c84f7": brand_dark, "#2c2c2c": r["main_bg"], "#3c3c3c": r["floating_bg"],
            "#242424": r["secondary_bg"], "#464646": r["nested_floating_bg"], "#212121": r["tertiary_bg"],
            "#fd5f51": r["danger"], "#38c76a": r["positive"], "#fdbe04": r["warning"]}
    return "\n".join(L), {"swap": swap, "accent": brand}


# ---------- terminal ----------
def terminal(c, name):
    t = c.term
    return {
        "visible-name": f"Rain {name}",
        "use-theme-colors": False,
        "background-color": t["background"],
        "foreground-color": t["foreground"],
        "palette": c.ansi,
        "bold-is-bright": False,
        "bold-color-same-as-fg": True,
        "cursor-colors-set": True,
        "cursor-background-color": t["cursor"],
        "cursor-foreground-color": t["cursor_text"],
        "highlight-colors-set": True,
        "highlight-background-color": t["selection"],
        "highlight-foreground-color": t["foreground"],
    }


# ---------- Geany ----------
def geany(c, spec):
    r, s, t = c.role, c.syntax, c.term
    x = lambda h: "0x" + h[1:].lower()  # noqa: E731
    bg, fg = t["background"], t["foreground"]
    lines = f"""[theme_info]
name=Rain {spec['name']}
description={spec['name']} colours, generated from rain-themes theme.spec.json.
version=1
author={', '.join(spec['authors'])}
url={spec.get('source', '')}

[named_styles]
default={x(fg)};{x(bg)};false;false
error={x(s['error'])};{x(bg)};true;false

selection={x(fg)};{x(t['selection'])};false;true
current_line={x(fg)};{x(r['floating_bg'] if r['floating_bg'] != bg else r['secondary_bg'])};true
brace_good={x(r['brand'])};{x(bg)};true;false
brace_bad={x(s['error'])};{x(bg)};true;false
margin_line_number={x(r['text_muted'])};{x(r['secondary_bg'])}
margin_folding={x(r['text_muted'])};{x(r['secondary_bg'])}
fold_symbol_highlight={x(r['text_secondary'])}
indent_guide={x(r['nested_floating_bg'])}
caret={x(t['cursor'])};{x(t['cursor'])};false
marker_line={x(fg)};{x(mix(s['changed'], bg, 0.7))}
marker_search={x(bg)};{x(r['brand'])}
marker_mark={x(fg)};{x(r['floating_bg'])}
call_tips={x(r['text_secondary'])};{x(r['floating_bg'])};false;false
white_space={x(r['nested_floating_bg'])};{x(bg)};true;false

comment={x(s['comment'])}
comment_doc={x(s['comment'])}
comment_line=comment
comment_line_doc=comment_doc
comment_doc_keyword=comment_doc,bold
comment_doc_keyword_error=comment_doc,italic

number={x(s['number'])}
number_1=number
number_2=number_1

type={x(s['type'])}
class={x(s['class'])}
function={x(s['function'])}
parameter={x(s['parameter'])}

keyword={x(s['keyword'])}
keyword_1=keyword
keyword_2={x(s['builtin'])}
keyword_3={x(s['storage'])}
keyword_4=keyword_1

identifier=default
identifier_1=identifier
identifier_2=identifier_1
identifier_3=identifier_1
identifier_4=identifier_1

string={x(s['string'])}
string_1=string
string_2=string_1
string_3=default
string_4=default
string_eol={x(s['error'])};{x(bg)}
character=string_1
backticks=string_2
here_doc=string_2

label=default,bold
preprocessor={x(s['preprocessor'])}
regex=number_1
operator={x(s['operator'])}
decorator={x(s['preprocessor'])},bold
other={x(s['constant'])}

tag={x(s['tag'])}
tag_unknown=tag,bold
tag_end=tag,bold
attribute={x(s['attribute'])}
attribute_unknown=attribute,bold
value=string_1
entity={x(s['constant'])}

line_added={x(s['added'])}
line_removed={x(s['removed'])}
line_changed={x(s['changed'])}
"""
    return lines


# ---------- Firefox ----------
def firefox(c, name):
    r = c.role
    tb, sb, mb, fb = r["tertiary_bg"], r["secondary_bg"], r["main_bg"], r["floating_bg"]
    tx, ts, ac, on = r["text_normal"], r["text_strong"], r["brand"], r["text_on_brand"]
    # Names read from Firefox 156's omni.ja (design-system tokens); a few older aliases kept.
    v = {
        "--toolbox-background-color": tb, "--toolbox-background-color-inactive": tb,
        "--toolbox-text-color": tx, "--toolbox-text-color-inactive": r["text_secondary"],
        "--lwt-accent-color": tb, "--lwt-text-color": tx,
        "--toolbar-background-color": sb, "--toolbar-text-color": tx, "--toolbar-bgcolor": sb, "--toolbar-color": tx,
        "--tab-selected-bgcolor": mb, "--tab-selected-textcolor": ts,
        "--toolbar-field-background-color": mb, "--toolbar-field-text-color": tx,
        "--toolbar-field-border-color": r["nested_floating_bg"],
        "--toolbar-field-background-color-focus": mb, "--toolbar-field-text-color-focus": ts,
        "--toolbar-field-border-color-focus": ac,
        "--urlbar-box-background-color": fb,
        "--urlbarview-background-color-selected": ac, "--urlbarview-text-color-selected": on,
        "--panel-background-color": fb, "--panel-text-color": tx, "--panel-border-color": r["nested_floating_bg"],
        "--arrowpanel-background": fb, "--arrowpanel-color": tx,
        "--sidebar-background-color": sb, "--sidebar-text-color": tx, "--sidebar-border-color": tb,
        "--background-color-box": mb, "--text-color": tx, "--link-color": r["link"],
        "--color-accent-primary": ac, "--color-accent-primary-hover": r["brand_bright"],
        "--color-accent-primary-active": r["brand_bright"], "--focus-outline-color": ac,
        "--button-background-color-primary": ac, "--button-text-color-primary": on,
        "--button-background-color-primary-hover": r["brand_bright"],
        "--button-background-color-primary-active": r["brand_bright"],
        "--tab-loading-fill": ac, "--tab-attention-icon-color": ac,
        "--toolbarbutton-icon-fill": tx, "--toolbarbutton-icon-fill-attention": ac, "--icon-color": tx,
        "--toolbarbutton-background-color-hover": r["hover"], "--toolbarbutton-background-color-active": r["active"],
        "--chrome-content-separator-color": tb, "--tabs-navbar-separator-color": tb,
    }
    body = "\n".join(f"  {k}: {h} !important;" for k, h in v.items())
    chrome = f"""/* Rain {name} — generated by tools/desktop_export.py.
   Needs about:config toolkit.legacyUserProfileCustomizations.stylesheets = true (apply_theme.py sets it).
   Variables for the parts that read them; direct rules for the default theme, which sets its own. */
:root, :root:-moz-lwtheme, #navigator-toolbox, #nav-bar, #TabsToolbar, #PersonalToolbar,
.urlbar, #urlbar, #searchbar, panel, menupopup, #sidebar-main, #sidebar-box {{
{body}
}}
#navigator-toolbox, #TabsToolbar, #titlebar {{
  background-color: {r['tertiary_bg']} !important;
  color: {r['text_normal']} !important;
}}
#nav-bar, #PersonalToolbar, #sidebar-box, #sidebar-main {{
  background-color: {r['secondary_bg']} !important;
  color: {r['text_normal']} !important;
}}
.tabbrowser-tab {{ color: {r['text_secondary']} !important; }}
.tabbrowser-tab[selected] {{ color: {r['text_strong']} !important; }}
.tab-background[selected] {{ background-color: {r['main_bg']} !important; background-image: none !important; }}
.tabbrowser-tab:hover > .tab-stack > .tab-background:not([selected]) {{ background-color: {r['floating_bg']} !important; }}
.urlbar-background, #searchbar {{ background-color: {r['main_bg']} !important; }}
.urlbar[focused] > .urlbar-background {{ outline-color: {r['brand']} !important; }}
.urlbar, .urlbar-input {{ color: {r['text_normal']} !important; }}
"""
    content = f"""/* Rain {name} — new-tab page colours. */
@-moz-document url("about:home"), url("about:newtab"), url("about:blank"), url("about:privatebrowsing") {{
  :root, body {{
    --newtab-background-color: {r['main_bg']} !important;
    --newtab-background-color-secondary: {r['floating_bg']} !important;
    --newtab-text-primary-color: {r['text_normal']} !important;
    --newtab-primary-action-background: {r['brand']} !important;
    background-color: {r['main_bg']} !important;
  }}
}}
"""
    return chrome, content


# ---------- Firefox Color ----------
def _msgpack(o):
    """Minimal msgpack (what json-url packs before LZMA): dict/list/str/small int."""
    import struct
    if isinstance(o, bool):
        return b"\xc3" if o else b"\xc2"
    if isinstance(o, int):
        if 0 <= o < 128:
            return bytes([o])
        if 0 <= o < 256:
            return b"\xcc" + bytes([o])
        return b"\xcd" + struct.pack(">H", o)
    if isinstance(o, str):
        b = o.encode()
        return (bytes([0xA0 | len(b)]) if len(b) < 32 else b"\xd9" + bytes([len(b)])) + b
    if isinstance(o, list):
        return bytes([0x90 | len(o)]) + b"".join(_msgpack(x) for x in o)
    if isinstance(o, dict):
        head = bytes([0x80 | len(o)]) if len(o) < 16 else b"\xde" + struct.pack(">H", len(o))
        return head + b"".join(_msgpack(k) + _msgpack(v) for k, v in o.items())
    raise TypeError(type(o))


def firefox_color(c, name):
    """Firefox Color theme + share URL (color.firefox.com, json-url 'lzma' codec)."""
    import base64
    import lzma
    r = c.role
    m = {
        "toolbar": "secondary_bg", "toolbar_text": "text_normal", "frame": "tertiary_bg",
        "tab_background_text": "text_secondary", "toolbar_field": "main_bg", "toolbar_field_text": "text_normal",
        "tab_line": "brand", "popup": "floating_bg", "popup_text": "text_normal",
        "button_background_active": "nested_floating_bg", "button_background_hover": "floating_bg",
        "frame_inactive": "tertiary_bg", "icons": "text_normal", "icons_attention": "brand",
        "ntp_background": "main_bg", "ntp_text": "text_normal", "popup_border": "nested_floating_bg",
        "popup_highlight": "brand", "popup_highlight_text": "text_on_brand",
        "sidebar": "secondary_bg", "sidebar_border": "tertiary_bg", "sidebar_text": "text_normal",
        "sidebar_highlight": "brand", "sidebar_highlight_text": "text_on_brand",
        "tab_background_separator": "nested_floating_bg", "tab_loading": "brand", "tab_selected": "main_bg",
        "tab_text": "text_strong", "toolbar_bottom_separator": "tertiary_bg",
        "toolbar_field_border": "nested_floating_bg", "toolbar_field_border_focus": "brand",
        "toolbar_field_focus": "main_bg", "toolbar_field_highlight": "brand",
        "toolbar_field_highlight_text": "text_on_brand", "toolbar_field_separator": "nested_floating_bg",
        "toolbar_field_text_focus": "text_strong", "toolbar_top_separator": "tertiary_bg",
        "toolbar_vertical_separator": "nested_floating_bg",
    }
    colors = {k: dict(zip("rgb", (int(r[v][i:i + 2], 16) for i in (1, 3, 5)))) for k, v in m.items()}
    theme = {"colors": colors, "images": {"additional_backgrounds": []}, "title": f"Rain {name}"}
    packed = lzma.compress(_msgpack(theme), format=lzma.FORMAT_ALONE, preset=9)
    url = "https://color.firefox.com/?theme=" + base64.urlsafe_b64encode(packed).decode().rstrip("=")
    return theme, url


# ---------- Vesktop ----------
def vesktop(theme_json, spec):
    sem = theme_json["semanticColors"]
    raw = theme_json["rawColors"]
    decls = [f"  --{k.lower().replace('_', '-')}: {v[0]} !important;" for k, v in sem.items()]
    decls += [f"  --{k.lower().replace('_', '-')}: {v} !important;" for k, v in raw.items()]
    return f"""/**
 * @name Rain {spec['name']}
 * @author {', '.join(spec['authors'])}
 * @description {spec['description']} Generated from rain-themes (same mapping as the Rain mobile theme).
 * @version 1
 * @source https://github.com/alpine-vortex/rain-themes
 */
:root, .theme-dark, .theme-darker, .theme-midnight,
.visual-refresh.theme-dark, .visual-refresh .theme-dark {{
{chr(10).join(decls)}
}}
"""


# ---------- wallpaper ----------
def wallpaper(c, size, path, accent_share):
    from PIL import Image, ImageDraw, ImageFilter
    r = c.role
    w, h = size
    small = (w // 8, h // 8)  # draw small, blur, upscale: smooth and fast
    img = Image.new("RGB", small)
    top, bot = rgb(r["tertiary_bg"]), rgb(r["main_bg"])
    d = ImageDraw.Draw(img)
    for y in range(small[1]):
        t = y / max(1, small[1] - 1)
        d.line([(0, y), (small[0], y)], fill=tuple(round((a * (1 - t) + b * t) * 255) for a, b in zip(top, bot)))
    sw, sh = small
    # One big accent field (steers Material You), one secondary accent.
    rad = int(min(sw, sh) * accent_share)
    d.ellipse([sw - rad * 1.3, sh - rad * 1.2, sw + rad * 0.7, sh + rad * 0.8], fill=r["brand"])
    rad2 = int(rad * 0.45)
    d.ellipse([-rad2 * 0.6, -rad2 * 0.4, rad2 * 1.4, rad2 * 1.6], fill=r["link"])
    img = img.filter(ImageFilter.GaussianBlur(min(sw, sh) / 9))
    img = img.resize(size, Image.BICUBIC)
    img.save(path, optimize=True)


# ---------- README ----------
# ---------- Sync for Reddit ----------
def sync_theme(c):
    """Sync's Monet theme JSON (the format its theme export produces). Sync derives
    every surface from the seed, so only the accent and the dark text colours are
    exact; 0 means "no override". Light overrides stay 0: the themes are dark-only."""
    r = c.role
    return {
        "monet_override_light_secondary_text_color": 0,
        "monet_override_light_primary_text_color": 0,
        "monet_override_light_link_color": 0,
        "monet_boost_light_color": False,
        "monet_override_dark_secondary_text_color": r["text_secondary"],
        "monet_override_dark_primary_text_color": r["text_normal"],
        "monet_override_dark_link_color": r["link"],
        "monet_boost_dark_color": True,
        "monet_color_intensity": 1,
        "monet_manual_theme_color": r["brand"],
        "monet_system": False,
    }


# ---------- redeye ----------
RAW_BASE = "https://raw.githubusercontent.com/alpine-vortex/rain-themes/main"


def _close(a, b, tol=0.12):
    return sum((x - y) ** 2 for x, y in zip(rgb(a), rgb(b))) ** 0.5 < tol


def _same_hue(a, b, degrees):
    """Both saturated and within `degrees` of hue (so a grey never matches anything)."""
    (ha, _, sa), (hb, _, sb) = hls(a), hls(b)
    d = abs(ha - hb) * 360
    return sa > 0.25 and sb > 0.25 and min(d, 360 - d) < degrees


def _on(colour, dark, light):
    """Text colour for a filled `colour`: whichever of dark/light contrasts more."""
    return dark if contrast(colour, dark) >= contrast(colour, light) else light


def app_tags(c, avoid):
    """8 muted hues for subreddit dots / comment depth bars. Candidates in a fixed order
    (ANSI 1-6, ANSI 9-14, syntax colours), skipping greys, repeats and anything within
    12 degrees of hue of accent/state/danger; each blended 30% toward the background.
    Palettes with fewer than 8 usable hues are filled with the same hues blended 55%
    (then 12%, 70%, 0%), so neighbouring slots stay distinguishable. Order is
    stable: redeye picks a slot by hashing the subreddit name."""
    bg = c.role["main_bg"]
    cands = c.ansi[1:7] + c.ansi[9:15] + [c.syntax[k] for k in SYNTAX_KEYS]
    picked = []
    for h in cands:
        if hls(h)[2] < 0.25 or not 0.35 < hls(h)[1] < 0.9:
            continue  # greys, near-black diff backgrounds, near-white
        if any(_close(h, x) or _same_hue(h, x, 12) for x in avoid) \
                or any(_close(h, x) or _same_hue(h, x, 8) for x in picked):
            continue
        picked.append(h)
    tags = [mix(h, bg, 0.3) for h in picked[:8]]
    for t in (0.55, 0.12, 0.7, 0.0):
        for h in picked:
            if len(tags) < 8:
                tags.append(mix(h, bg, t))
    return tags


def app_theme(c, spec):
    """app-theme v1 (docs/app-theme.md; agreed with the redeye session 2026-09-29): flat JSON, #RRGGBB."""
    r, R = c.role, c.R
    bg, text = r["main_bg"], r["text_normal"]
    state = c.ref(spec["app_state"])
    if state == r["brand"]:
        raise SpecError("app_state must differ from the accent")
    t = {
        "format": "app-theme", "version": 1,
        "name": spec["name"], "slug": spec["slug"], "source": spec.get("source", ""),
        "mode": "dark",
        "background": bg, "text": text, "accent": r["brand"],
        "panel": r["secondary_bg"], "raised": r["floating_bg"],
        "selected": r["nested_floating_bg"], "on_selected": text,
        "line": r["floating_bg"], "border": r["interactive_muted"],
        "text_secondary": r["text_secondary"], "text_muted": r["text_muted"],
        "on_accent": r["text_on_brand"],
        "state": state, "on_state": _on(state, bg, text),
        "danger": r["danger"], "on_danger": _on(r["danger"], bg, text),
    }
    # snackbar action on a `text`-coloured container: only a palette value that reaches 4.5:1
    b560 = spec.get("raw", {}).get("BRAND_560")
    if b560 is not None:
        inv = c._opaque(R(b560)[0], bg)
        if contrast(inv, text) >= 4.5:
            t["accent_inverse"] = inv
    t.update({"link": r["link"], "positive": r["positive"], "warning": r["warning"],
              "tags": app_tags(c, [r["brand"], state, r["danger"], bg, text])})
    return t


def app_section(spec):
    return f"""## Android apps (app-theme)
Apps that read the app-theme format (such as redeye) import
`{spec['slug']}.app-theme.json` by file, clipboard, or this URL:
`{RAW_BASE}/{spec['slug']}/desktop/{spec['slug']}.app-theme.json`

"""


def termius_section(spec):
    """Termius (phone SSH) has no custom-theme import; point at the nearest built-in."""
    t = spec.get("termius")
    if not t:
        return ""
    if t["match"] == "closest":
        how = (f"Pick **{t['theme']}**, the closest built-in; Termius has no {spec['name']} theme, "
               "so colours differ somewhat from the terminal palette below.")
    else:
        how = f"Pick **{t['theme']}**; it's the same upstream palette."
    return f"""## Termius (phone)
Settings → Terminal theme & font → {how} Claude Code over SSH then follows it
(`/theme` → *ANSI colours only*).

"""


def readme(c, spec, slug):
    r = c.role
    sw = nearest_swatch(r["brand"])
    return f"""# {spec['name']} — desktop exports

Generated by `tools/desktop_export.py`. Apply with `tools/apply_theme.py {slug}`;
the steps below are the ones a script can't do.

## Dark Reader (ChatGPT and other sites)
On the site, open the Dark Reader popup → **Theme** → **Colors** (use its site-only option to keep other sites as they are):

| Setting | Value |
|---|---|
| Background | `{r['main_bg']}` |
| Text | `{r['text_normal']}` |
| Selection | `{r['brand']}` |

## Niagara Launcher (phone)
1. Set `wallpaper-phone.png` as the wallpaper.
2. Niagara → Theme colour → pick the **Wallpaper and System** swatch closest to `{r['brand']}`.
   Fallback in **Standard**: **{sw}**.
3. Export the theme (`.nlt`) and commit it here as `{slug}.nlt`.

## Sync for Reddit (phone)
Copy the JSON below (or `sync-theme.json`) and paste it into Sync's Monet theme
import; Sync only imports from the clipboard. It sets the seed `{r['brand']}` and the dark text colours; Sync derives
backgrounds and cards from the seed, so they are tinted near-black rather than
`{r['main_bg']}`.

```json
{json.dumps(sync_theme(c), indent=2)}
```

{termius_section(spec)}{app_section(spec)}## Firefox Color (other machines)
With `rain apply`, Firefox uses userChrome.css (exact colours). Elsewhere, install
the Firefox Color extension and open the `url` in `firefox-color.json`.
Firefox for Android doesn't support themes; use Dark Reader there (values above).

## Claude Code
Once: `/theme` → the *ANSI colours only* dark option. It then follows the terminal palette.

## Colours
| Role | Hex |
|---|---|
| Background | `{r['main_bg']}` |
| Sidebar / titlebar | `{r['secondary_bg']}` |
| Panel | `{r['tertiary_bg']}` |
| Text | `{r['text_normal']}` |
| Accent | `{r['brand']}` (text on accent contrast {contrast(r['brand'], r['text_on_brand']):.1f}) |
| Link | `{r['link']}` |

Terminal: {' '.join(f'`{h}`' for h in c.ansi)}
"""


def export(theme_dir, out=None, quiet=False, rain_dir=None):
    """Write <theme_dir>/desktop/ (or `out`). Returns False when the spec has no desktop blocks."""
    theme_dir = Path(theme_dir)
    spec = json.loads((theme_dir / "theme.spec.json").read_text())
    slug = spec["slug"]
    if not all(k in spec for k in ("ansi", "terminal", "syntax")):
        if not quiet:
            print(f"skip {slug}: spec has no ansi/terminal/syntax blocks")
        return False
    theme_json = json.loads((Path(rain_dir or theme_dir) / f"{slug}.json").read_text())
    c = Colours(spec)
    out = Path(out) if out else theme_dir / "desktop"
    out.mkdir(parents=True, exist_ok=True)
    scss, meta = colloid(c)
    (out / "colloid-palette.scss").write_text(scss)
    meta["name"] = spec["name"]
    meta["slug"] = slug
    meta["gtk_theme"] = "Rain-" + "".join(w.capitalize() for w in slug.split("-"))
    (out / "colloid.json").write_text(json.dumps(meta, indent=2) + "\n")
    (out / "gnome-terminal.json").write_text(json.dumps(terminal(c, spec["name"]), indent=2) + "\n")
    (out / f"geany-{slug}.conf").write_text(geany(c, spec))
    chrome, content = firefox(c, spec["name"])
    (out / "userChrome.css").write_text(chrome)
    (out / "userContent.css").write_text(content)
    (out / "brave.json").write_text(json.dumps(
        {"seed": c.role["brand"], "user_color2": argb_int(c.role["brand"])}, indent=2) + "\n")
    (out / f"{slug}.theme.css").write_text(vesktop(theme_json, spec))
    fc_theme, fc_url = firefox_color(c, spec["name"])
    (out / "firefox-color.json").write_text(json.dumps({"url": fc_url, "theme": fc_theme}, indent=2) + "\n")
    (out / f"{slug}.app-theme.json").write_text(json.dumps(app_theme(c, spec), indent=2) + "\n")
    (out / "sync-theme.json").write_text(json.dumps(sync_theme(c), indent=2) + "\n")
    wallpaper(c, DESKTOP_SIZE, out / "wallpaper-desktop.png", 0.55)
    wallpaper(c, PHONE_SIZE, out / "wallpaper-phone.png", 0.75)
    (out / "README.md").write_text(readme(c, spec, slug))
    if not quiet:
        print(f"exported {slug} -> {out}")
    return True


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for d in sys.argv[1:]:
        try:
            export(d)
        except SpecError as e:
            sys.exit(f"{d}: {e}")


if __name__ == "__main__":
    main()
