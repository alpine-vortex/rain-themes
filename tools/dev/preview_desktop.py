#!/usr/bin/env python3
"""Screenshot a theme's desktop exports without touching the live desktop.

    python3 tools/dev/preview_desktop.py <slug> [--out DIR] [--only gtk,firefox,geany]

Builds the Colloid theme into a scratch XDG dir and screenshots:
    gtk      a small GTK3 window (headerbar, sidebar, entry, buttons, check, switch,
             slider, progress, link) run with GTK_THEME set
    firefox  a throwaway Firefox profile with the theme's userChrome/userContent
             (uses --no-remote, so a running Firefox is not affected)
    geany    a separate Geany instance (-i) with a scratch config dir, so a
             running Geany and ~/.config/geany are not affected

Windows open briefly on the current display (needs an X session; there is no
Xvfb on spacer) and close themselves. PNGs go to --out (default: a temp dir,
printed at the end).
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

GTK_WINDOW = r'''
import gi, sys
gi.require_version("Gtk", "3.0"); from gi.repository import Gtk, GLib, Gdk
out = sys.argv[1]
w = Gtk.Window(title="Rain theme test"); w.set_default_size(560, 360)
hb = Gtk.HeaderBar(title="Rain theme test", show_close_button=True); w.set_titlebar(hb)
pan = Gtk.Paned(); side = Gtk.ListBox()
for t in ["Home", "Documents", "Downloads", "Pictures"]:
    side.add(Gtk.Label(label=t, xalign=0, margin=8))
side.select_row(side.get_row_at_index(1)); pan.pack1(side, False, False)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=14)
box.add(Gtk.Entry(text="Search files…"))
row = Gtk.Box(spacing=8)
b = Gtk.Button(label="Open"); b.get_style_context().add_class("suggested-action"); row.add(b)
row.add(Gtk.Button(label="Cancel"))
d = Gtk.Button(label="Delete"); d.get_style_context().add_class("destructive-action"); row.add(d)
box.add(row)
box.add(Gtk.CheckButton(label="Show hidden files", active=True))
box.add(Gtk.Switch(active=True, halign=Gtk.Align.START))
sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1); sc.set_value(60); box.add(sc)
box.add(Gtk.ProgressBar(fraction=0.4))
lk = Gtk.LinkButton(uri="https://example.com", label="A link"); lk.set_halign(Gtk.Align.START); box.add(lk)
pan.pack2(box, True, False); w.add(pan); w.show_all()
def snap():
    win = w.get_window(); _, _, ww, hh = win.get_geometry()
    Gdk.pixbuf_get_from_window(win, 0, 0, ww, hh).savev(out, "png", [], [])
    Gtk.main_quit(); return False
GLib.timeout_add(900, snap); Gtk.main()
'''


def grab(title, out):
    """Capture an X window by exact title via GDK (PIL can't read xwd output)."""
    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkX11", "3.0")
    from gi.repository import Gdk, GdkX11
    info = subprocess.run(["xwininfo", "-name", title], capture_output=True, text=True).stdout
    m = re.search(r"Window id: (0x[0-9a-f]+)", info)
    if not m:
        print(f"window {title!r} not found", file=sys.stderr)
        return False
    w = GdkX11.X11Window.foreign_new_for_display(GdkX11.X11Display.get_default(), int(m.group(1), 16))
    _, _, ww, hh = w.get_geometry()
    Gdk.pixbuf_get_from_window(w, 0, 0, ww, hh).savev(str(out), "png", [], [])
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--out")
    ap.add_argument("--only", default="gtk,firefox,geany")
    a = ap.parse_args()
    from apply_theme import build_gtk  # noqa: E402
    import json
    exp = ROOT / a.slug / "desktop"
    theme = json.loads((exp / "colloid.json").read_text())["gtk_theme"] + "-Dark"
    work = Path(tempfile.mkdtemp(prefix="rain-preview-"))
    out = Path(a.out) if a.out else work
    out.mkdir(parents=True, exist_ok=True)
    build_gtk(a.slug, work / "xdg/themes")
    env = {"XDG_DATA_DIRS": f"{work / 'xdg'}:/usr/share", "GTK_THEME": theme}
    import os
    env = {**os.environ, **env}
    only = a.only.split(",")

    if "gtk" in only:
        (work / "gtk_window.py").write_text(GTK_WINDOW)
        subprocess.run([sys.executable, str(work / "gtk_window.py"), str(out / f"{a.slug}-gtk.png")],
                       env=env, timeout=15, capture_output=True)

    if "firefox" in only:
        prof = work / "ffprof"
        (prof / "chrome").mkdir(parents=True)
        for f in ("userChrome.css", "userContent.css"):
            shutil.copy(exp / f, prof / "chrome" / f)
        (prof / "user.js").write_text("\n".join([
            'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);',
            'user_pref("browser.shell.checkDefaultBrowser", false);',
            'user_pref("browser.aboutwelcome.enabled", false);',
            'user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);']) + "\n")
        p = subprocess.Popen(["firefox", "--no-remote", "--new-instance", "--profile", str(prof), "about:home"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(8)
        grab("Mozilla Firefox", out / f"{a.slug}-firefox.png")
        p.terminate()

    if "geany" in only:
        cfg = work / "geanycfg"
        (cfg / "colorschemes").mkdir(parents=True)
        shutil.copy(exp / f"geany-{a.slug}.conf", cfg / "colorschemes")
        (cfg / "geany.conf").write_text(f"[geany]\ncolor_scheme=geany-{a.slug}.conf\n")
        sample = work / "sample.py"
        shutil.copy(ROOT / "tools/desktop_export.py", sample)
        p = subprocess.Popen(["geany", "-i", "-c", str(cfg), str(sample)], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        grab(f"sample.py - {work} - Geany (new instance)", out / f"{a.slug}-geany.png")
        p.terminate()

    for f in sorted(out.glob(f"{a.slug}-*.png")):
        print(f)


if __name__ == "__main__":
    main()
