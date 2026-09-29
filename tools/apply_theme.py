#!/usr/bin/env python3
"""Apply a theme's desktop exports to this machine (Linux Mint / Cinnamon).

    tools/apply_theme.py <slug> [--only gtk,wallpaper,terminal,geany,firefox,brave,vesktop] [--dry-run]
    tools/apply_theme.py --restore [--dry-run]
    tools/apply_theme.py --build-gtk <slug> --dest DIR     # build the Colloid theme only

Run tools/desktop_export.py first. The first apply saves the current settings
to ~/.local/state/rain-themes/snapshot.json; --restore puts them back. Apps
that rewrite their config on exit (Geany, Firefox, Brave) are skipped while
running, with a note.

The GTK/Cinnamon theme is Colloid (GPL-3, vinceliuice/Colloid-gtk-theme) at a
pinned commit, cloned to ~/.cache/rain-themes and rebuilt with our palette.
"""
import argparse
import configparser
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
STATE = HOME / ".local/state/rain-themes"
SNAPSHOT = STATE / "snapshot.json"
CACHE = HOME / ".cache/rain-themes"
COLLOID_URL = "https://github.com/vinceliuice/Colloid-gtk-theme.git"
COLLOID_COMMIT = "fe11342f37f124f1b29d44cf33e9a06053f4bba2"
THEMES_DIR = HOME / ".themes"
GTK4 = HOME / ".config/gtk-4.0"
GEANY_CONF = HOME / ".config/geany/geany.conf"
BRAVE_PREFS = HOME / ".config/BraveSoftware/Brave-Origin/Default/Preferences"
VESKTOP = next((d for d in (HOME / ".config/vesktop", HOME / ".var/app/dev.vencord.Vesktop/config/vesktop")
                if d.exists()), HOME / ".config/vesktop")
TERM_BASE = "/org/gnome/terminal/legacy/profiles:/"
GSETTINGS = [("org.cinnamon.theme", "name"), ("org.cinnamon.desktop.interface", "gtk-theme"),
             ("org.cinnamon.desktop.wm.preferences", "theme"), ("org.cinnamon.desktop.background", "picture-uri")]
TARGETS = ["gtk", "wallpaper", "terminal", "geany", "firefox", "brave", "vesktop"]
USERJS_LINE = 'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true); // rain-themes'
DRY = False


def log(msg):
    print(("[dry-run] " if DRY else "") + msg)


def run(*cmd, check=True):
    return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout.strip()


def act(desc, fn, *a):
    log(desc)
    if not DRY:
        fn(*a)


def running(name):
    return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# ---------- Colloid build ----------
def colloid_src():
    src = CACHE / "Colloid-gtk-theme"
    if not src.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "-q", COLLOID_URL, str(src))
    if run("git", "-C", str(src), "rev-parse", "HEAD") != COLLOID_COMMIT:
        run("git", "-C", str(src), "fetch", "-q", "origin", COLLOID_COMMIT, check=False)
        run("git", "-C", str(src), "checkout", "-q", COLLOID_COMMIT)
    return src


STOCK = re.compile(r"#(?:5b9bf8|3c84f7|2c2c2c|3c3c3c|242424|464646|212121|fd5f51|38c76a|fdbe04)\b", re.I)


def build_gtk(slug, dest):
    """Build Rain-<Name>-Dark into dest; returns the theme dir."""
    exp = ROOT / slug / "desktop"
    meta = json.loads((exp / "colloid.json").read_text())
    name = meta["gtk_theme"]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "colloid"
        shutil.copytree(colloid_src(), work, ignore=shutil.ignore_patterns(".git"))
        sass = work / "src/sass"
        shutil.copy(exp / "colloid-palette.scss", sass / "_color-palette-default.scss")
        tw = sass / "_tweaks.scss"
        # fixed = use our colours, not the libadwaita system accent
        tw.write_text(re.sub(r"(\$colortype:\s*)'system'", r"\1'fixed'", tw.read_text()))
        out = Path(tmp) / "out"
        out.mkdir()
        subprocess.run(["bash", str(work / "install.sh"), "-d", str(out), "-n", name, "-c", "dark", "-t", "default"],
                       check=True, capture_output=True, text=True)
        built = out / f"{name}-Dark"
        # What Colloid's -l would write to ~/.config/gtk-4.0; kept in the theme so apply can link it.
        (built / "libadwaita").mkdir()
        subprocess.run(["sassc", "-M", "-t", "expanded", str(work / "src/main/libadwaita/libadwaita-Dark.scss"),
                        str(built / "libadwaita/gtk.css")], check=True, capture_output=True, text=True)
        # Pre-drawn assets keep Colloid's stock colours; swap them in one pass.
        swap = {k.lower(): v for k, v in meta["swap"].items()}
        left = []
        for f in built.rglob("*"):
            if f.is_file() and not f.is_symlink():
                try:
                    t = f.read_text()
                except UnicodeDecodeError:
                    continue
                n = STOCK.sub(lambda m: swap[m.group(0).lower()], t)
                if n != t:
                    f.write_text(n)
                if STOCK.search(n):
                    left.append(f)
        if left:
            print(f"warning: stock Colloid colours left in {len(left)} files", file=sys.stderr)
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        # The -hdpi/-xhdpi siblings are Xfce window borders only; Cinnamon doesn't need them.
        tgt = dest / built.name
        if tgt.exists():
            shutil.rmtree(tgt)
        shutil.copytree(built, tgt, symlinks=True)
    return Path(dest) / f"{name}-Dark"


# ---------- snapshot / restore ----------
def firefox_profile():
    ini = HOME / ".mozilla/firefox/installs.ini"
    if not ini.exists():
        return None
    cp = configparser.ConfigParser()
    cp.read(ini)
    for s in cp.sections():
        if cp[s].get("Default"):
            return HOME / ".mozilla/firefox" / cp[s]["Default"]
    return None


def backup_file(p, key, snap):
    if p.exists() and not p.is_symlink():
        b = STATE / "files" / key
        b.parent.mkdir(parents=True, exist_ok=True)
        if not DRY:
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, b)
        snap["files"][key] = {"path": str(p), "backup": str(b)}
    elif p.is_symlink():
        snap["files"][key] = {"path": str(p), "link": str(p.readlink())}
    else:
        snap["files"][key] = {"path": str(p), "absent": True}


def take_snapshot():
    if SNAPSHOT.exists():
        # Apps installed after the first snapshot: record their original state now.
        snap = json.loads(SNAPSHOT.read_text())
        vs = VESKTOP / "settings/settings.json"
        if "vesktop_enabled" not in snap and vs.exists():
            snap["vesktop_enabled"] = json.loads(vs.read_text()).get("enabledThemes", [])
            act("add Vesktop to snapshot", write, SNAPSHOT, json.dumps(snap, indent=2))
        return
    snap = {"gsettings": {}, "dconf": {}, "files": {}}
    for schema, key in GSETTINGS:
        snap["gsettings"][f"{schema} {key}"] = run("gsettings", "get", schema, key)
    for k in ("list", "default"):
        snap["dconf"][TERM_BASE + k] = run("dconf", "read", TERM_BASE + k)
    for f in ("gtk.css", "gtk-dark.css", "assets"):
        backup_file(GTK4 / f, f"gtk4-{f}", snap)
    if GEANY_CONF.exists():
        m = re.search(r"^color_scheme=(.*)$", GEANY_CONF.read_text(), re.M)
        snap["geany_color_scheme"] = m.group(1) if m else ""
    ff = firefox_profile()
    if ff:
        for f in ("user.js", "chrome/userChrome.css", "chrome/userContent.css"):
            backup_file(ff / f, "firefox-" + f.replace("/", "-"), snap)
    if BRAVE_PREFS.exists():
        p = json.loads(BRAVE_PREFS.read_text())
        snap["brave_theme"] = p.get("browser", {}).get("theme")
    vs = VESKTOP / "settings/settings.json"
    if vs.exists():
        snap["vesktop_enabled"] = json.loads(vs.read_text()).get("enabledThemes", [])
    act(f"save snapshot -> {SNAPSHOT}", write, SNAPSHOT, json.dumps(snap, indent=2))


def restore():
    if not SNAPSHOT.exists():
        sys.exit("no snapshot; nothing to restore")
    snap = json.loads(SNAPSHOT.read_text())
    for sk, val in snap["gsettings"].items():
        schema, key = sk.split()
        act(f"gsettings {schema} {key} = {val}", run, "gsettings", "set", schema, key, val)
    for k, v in snap["dconf"].items():
        if v:
            act(f"dconf {k} = {v}", run, "dconf", "write", k, v)
        else:
            act(f"dconf reset {k}", run, "dconf", "reset", k)
    for key, f in snap["files"].items():
        p = Path(f["path"])

        def put(p=p, f=f):
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            if "backup" in f:
                (shutil.copytree if Path(f["backup"]).is_dir() else shutil.copy2)(f["backup"], p)
            elif "link" in f:
                p.symlink_to(f["link"])
            if key == "firefox-user.js" and "backup" not in f and p.exists():
                p.unlink()
        act(f"restore {p}", put)
    if "geany_color_scheme" in snap:
        if running("geany"):
            log("skip Geany: running (close it and re-run --restore)")
        else:
            act("geany color_scheme restore", set_geany, snap["geany_color_scheme"])
    if snap.get("brave_theme") is not None:
        if running("brave"):
            log("skip Brave: running")
        else:
            act("brave theme restore", set_brave_theme, snap["brave_theme"])
    if "vesktop_enabled" in snap:
        act("vesktop enabledThemes restore", set_vesktop_enabled, snap["vesktop_enabled"])
    log("restored. (Rain profiles/themes stay installed but unused; Firefox keeps the userChrome pref on.)")


# ---------- targets ----------
def set_geany(value):
    t = GEANY_CONF.read_text()
    GEANY_CONF.write_text(re.sub(r"^color_scheme=.*$", f"color_scheme={value}", t, flags=re.M))


def set_brave_theme(theme):
    p = json.loads(BRAVE_PREFS.read_text())
    p.setdefault("browser", {})["theme"] = theme
    BRAVE_PREFS.write_text(json.dumps(p, separators=(",", ":")))


def set_vesktop_enabled(names):
    f = VESKTOP / "settings/settings.json"
    d = json.loads(f.read_text()) if f.exists() else {}
    d["enabledThemes"] = names
    write(f, json.dumps(d, indent=4))


def apply_gtk(slug, exp):
    meta = json.loads((exp / "colloid.json").read_text())
    tdir = THEMES_DIR / f"{meta['gtk_theme']}-Dark"
    act(f"build Colloid -> {tdir}", build_gtk, slug, THEMES_DIR)
    name = tdir.name
    for schema, key in GSETTINGS[:3]:
        act(f"gsettings {schema} {key} {name}", run, "gsettings", "set", schema, key, name)

    def link4():
        GTK4.mkdir(parents=True, exist_ok=True)
        for f in ("gtk.css", "gtk-dark.css", "assets"):
            p = GTK4 / f
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            p.symlink_to(tdir / ("gtk-4.0/assets" if f == "assets" else "libadwaita/gtk.css"))
    act(f"link {GTK4}/{{gtk.css,gtk-dark.css,assets}} -> {tdir} (libadwaita)", link4)


def apply_wallpaper(slug, exp):
    dst = HOME / ".local/share/backgrounds/rain-themes" / f"{slug}.png"

    def go():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exp / "wallpaper-desktop.png", dst)
        run("gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", f"'file://{dst}'")
    act(f"wallpaper -> {dst}", go)


def apply_terminal(slug, exp):
    prof = json.loads((exp / "gnome-terminal.json").read_text())
    pid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"rain-themes/{slug}"))
    path = f"{TERM_BASE}:{pid}/"

    def gv(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            return "[" + ", ".join(f"'{x}'" for x in v) + "]"
        return "'" + str(v).replace("'", "\\'") + "'"

    def go():
        for k, v in prof.items():
            run("dconf", "write", path + k, gv(v))
        cur = run("dconf", "read", TERM_BASE + "list")
        ids = re.findall(r"'([^']+)'", cur)
        if not ids:  # implicit single profile: keep it listed
            ids = [p.strip(":/") for p in run("dconf", "list", TERM_BASE).split() if p.startswith(":")]
        if pid not in ids:
            ids.append(pid)
        run("dconf", "write", TERM_BASE + "list", gv(ids))
        run("dconf", "write", TERM_BASE + "default", f"'{pid}'")
    act(f"terminal profile '{prof['visible-name']}' ({pid}) as default", go)


def apply_geany(slug, exp):
    if running("geany"):
        log("skip Geany: running — close it and re-run with --only geany")
        return
    src = exp / f"geany-{slug}.conf"
    dst = HOME / ".config/geany/colorschemes" / src.name
    act(f"geany scheme -> {dst}", lambda: (dst.parent.mkdir(parents=True, exist_ok=True), shutil.copy2(src, dst)))
    act(f"geany color_scheme={src.name}", set_geany, src.name)


def apply_firefox(slug, exp):
    ff = firefox_profile()
    if not ff:
        log("skip Firefox: no profile found")
        return
    if running("firefox"):
        log("note: Firefox is running; restart it to load the new userChrome.css")

    def go():
        (ff / "chrome").mkdir(exist_ok=True)
        shutil.copy2(exp / "userChrome.css", ff / "chrome/userChrome.css")
        shutil.copy2(exp / "userContent.css", ff / "chrome/userContent.css")
        uj = ff / "user.js"
        t = uj.read_text() if uj.exists() else ""
        if USERJS_LINE not in t:
            uj.write_text(t + ("" if t.endswith("\n") or not t else "\n") + USERJS_LINE + "\n")
    act(f"firefox userChrome/userContent + user.js pref in {ff}", go)


def apply_brave(slug, exp):
    if not BRAVE_PREFS.exists():
        log("skip Brave: no Preferences file")
        return
    if running("brave"):
        log("skip Brave: running — close it and re-run with --only brave")
        return
    seed = json.loads((exp / "brave.json").read_text())

    def go():
        p = json.loads(BRAVE_PREFS.read_text())
        th = p.setdefault("browser", {}).setdefault("theme", {})
        th.update({"user_color2": seed["user_color2"], "color_scheme2": 2})
        p.setdefault("extensions", {}).setdefault("theme", {})["id"] = "user_color_theme_id"
        BRAVE_PREFS.write_text(json.dumps(p, separators=(",", ":")))
    act(f"brave seed colour {seed['seed']} (dark)", go)


def apply_vesktop(slug, exp):
    css = exp / f"{slug}.theme.css"
    dst = VESKTOP / "themes" / css.name
    if not VESKTOP.exists():
        log(f"skip Vesktop: not installed (run Vesktop once, then re-run with --only vesktop)")
        return
    if running("vesktop"):
        log("note: Vesktop is running; the theme file reloads live, the enable toggle may need a restart")

    def go():
        dst.parent.mkdir(parents=True, exist_ok=True)
        for old in dst.parent.glob("*.theme.css"):
            if old.read_text().startswith("/**\n * @name Rain ") and old.name != css.name:
                old.unlink()
        shutil.copy2(css, dst)
        f = VESKTOP / "settings/settings.json"
        d = json.loads(f.read_text()) if f.exists() else {}
        en = [x for x in d.get("enabledThemes", []) if not (VESKTOP / "themes" / x).exists() or x == css.name
              or not (VESKTOP / "themes" / x).read_text().startswith("/**\n * @name Rain ")]
        if css.name not in en:
            en.append(css.name)
        d["enabledThemes"] = en
        write(f, json.dumps(d, indent=4))
    act(f"vesktop theme -> {dst} (enabled)", go)


def main():
    global DRY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--only", help="comma list of " + ",".join(TARGETS))
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--build-gtk", metavar="SLUG")
    ap.add_argument("--dest")
    a = ap.parse_args()
    DRY = a.dry_run
    if a.build_gtk:
        print(build_gtk(a.build_gtk, a.dest or THEMES_DIR))
        return
    if a.restore:
        restore()
        return
    if not a.slug:
        ap.error("slug required")
    exp = ROOT / a.slug / "desktop"
    if not exp.exists():
        sys.exit(f"{exp} missing — run tools/desktop_export.py {a.slug}")
    only = a.only.split(",") if a.only else TARGETS
    bad = set(only) - set(TARGETS)
    if bad:
        ap.error(f"unknown targets {sorted(bad)}")
    take_snapshot()
    fns = {"gtk": apply_gtk, "wallpaper": apply_wallpaper, "terminal": apply_terminal, "geany": apply_geany,
           "firefox": apply_firefox, "brave": apply_brave, "vesktop": apply_vesktop}
    for t in TARGETS:
        if t in only:
            fns[t](a.slug, exp)
    print("\nManual steps (Dark Reader, Niagara, Claude Code): " + str(exp / "README.md"))


if __name__ == "__main__":
    main()
