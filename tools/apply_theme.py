#!/usr/bin/env python3
"""Apply a theme's desktop exports to this machine (Linux Mint / Cinnamon).

    tools/apply_theme.py <slug> [--only gtk,wallpaper,terminal,geany,firefox,brave,vesktop] [--dry-run]
    tools/apply_theme.py --restore [--dry-run]
    tools/apply_theme.py --build-gtk <slug> --dest DIR     # build the Colloid theme only

Run tools/desktop_export.py first. An apply on an unthemed desktop saves the
current settings to ~/.local/state/rain-themes/snapshot.json; --restore puts
back whatever rain still owns (anything changed since is left alone) and
retires the snapshot. Apps that rewrite their config on exit (Geany, Brave)
are skipped while running, with a note.

The GTK/Cinnamon theme is Colloid (GPL-3, vinceliuice/Colloid-gtk-theme) at a
pinned commit, cloned to ~/.cache/rain-themes and rebuilt with our palette.
"""
import argparse
import configparser
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
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


def atomic_write(path, text):
    """Replace path's content in one step: follows symlinks, keeps the file mode."""
    path = Path(os.path.realpath(path))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            shutil.copymode(path, tmp)
        else:
            mask = os.umask(0)
            os.umask(mask)
            os.chmod(tmp, 0o666 & ~mask)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, text)


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


# ---------- state: current palette + targets skipped while their app ran ----------
STATE_FILE = STATE / "state.json"


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return {"current": None, "pending": {}}


def save_state(st):
    if not DRY:
        write(STATE_FILE, json.dumps(st, indent=2))


def mark_pending(target, what):
    st = load_state()
    st.setdefault("pending", {})[target] = what
    save_state(st)


def clear_pending(target):
    st = load_state()
    if st.get("pending", {}).pop(target, None) is not None:
        save_state(st)


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


# ---------- what rain wrote: restore (and snapshot back-fill) only touch these ----------
WALLPAPERS = HOME / ".local/share/backgrounds/rain-themes"


def rain_uuids():
    return {str(uuid.uuid5(uuid.NAMESPACE_URL, f"rain-themes/{s}")) for s in exportable()}


def rain_gtk4(p):
    return p.is_symlink() and os.readlink(p).startswith(str(THEMES_DIR / "Rain-"))


def rain_css(p):
    """A userChrome/userContent.css that is byte-for-byte one of our exports."""
    if not p.is_file() or p.is_symlink():
        return False
    t = p.read_bytes()
    return any(t == e.read_bytes() for e in ROOT.glob(f"*/desktop/{p.name}"))


def rain_geany(scheme):
    return scheme in {f"geany-{s}.conf" for s in exportable()}


def rain_brave(theme):
    seeds = {json.loads((ROOT / s / "desktop/brave.json").read_text())["user_color2"] for s in exportable()}
    return (theme or {}).get("user_color2") in seeds


def rain_vesktop(name):
    f = VESKTOP / "themes" / name
    return name in {f"{s}.theme.css" for s in exportable()} or (
        f.is_file() and f.read_text(errors="replace").startswith("/**\n * @name Rain "))


def rain_gsetting(schema, key, val):
    if key == "picture-uri":
        return val.strip("'").startswith(f"file://{WALLPAPERS}/")
    return val.startswith("'Rain-")


def themed():
    """True if rain has already changed this desktop (a snapshot now would capture rain's own state)."""
    st = load_state()
    if st.get("current") or st.get("pending") or st.get("applied"):
        return True
    if run("gsettings", "get", "org.cinnamon.desktop.interface", "gtk-theme", check=False).startswith("'Rain-"):
        return True
    return any(rain_gtk4(GTK4 / f) for f in ("gtk.css", "gtk-dark.css", "assets"))


# ---------- snapshot / restore ----------
def backup_file(p, key, snap):
    if p.exists() and not p.is_symlink():
        b = STATE / "files" / key
        if not DRY:
            b.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, b)
        snap["files"][key] = {"path": str(p), "backup": str(b)}
    elif p.is_symlink():
        snap["files"][key] = {"path": str(p), "link": str(p.readlink())}
    else:
        snap["files"][key] = {"path": str(p), "absent": True}


def snapshot_apps(snap):
    """Record apps missing from snap (all on a fresh snapshot; ones installed since, on a later apply),
    unless they already hold rain's values. Returns the names added."""
    added = []
    if "geany_color_scheme" not in snap and GEANY_CONF.exists():
        m = re.search(r"^color_scheme=(.*)$", GEANY_CONF.read_text(), re.M)
        if not rain_geany(m.group(1) if m else ""):
            snap["geany_color_scheme"] = m.group(1) if m else ""
            added.append("Geany")
    ff = firefox_profile()
    if ff:
        for f in ("user.js", "chrome/userChrome.css", "chrome/userContent.css"):
            key = "firefox-" + f.replace("/", "-")
            if key not in snap["files"] and not rain_css(ff / f):
                backup_file(ff / f, key, snap)
                added.append(f"Firefox {f}")
    if "brave_theme" not in snap and BRAVE_PREFS.exists():
        th = json.loads(BRAVE_PREFS.read_text()).get("browser", {}).get("theme")
        if not rain_brave(th):
            snap["brave_theme"] = th
            added.append("Brave")
    vs = VESKTOP / "settings/settings.json"
    if "vesktop_enabled" not in snap and vs.exists():
        snap["vesktop_enabled"] = json.loads(vs.read_text()).get("enabledThemes", [])
        added.append("Vesktop")
    return added


def take_snapshot():
    if SNAPSHOT.exists():
        snap = json.loads(SNAPSHOT.read_text())
        added = snapshot_apps(snap)
        if added:
            act(f"add {', '.join(added)} to snapshot", write, SNAPSHOT, json.dumps(snap, indent=2))
        return
    if themed():
        log("warning: desktop already themed and no snapshot: not snapshotting (it would capture Rain "
            "state); `rain restore` stays unavailable until a restore/fresh start")
        return
    snap = {"gsettings": {}, "dconf": {}, "files": {}}
    for schema, key in GSETTINGS:
        snap["gsettings"][f"{schema} {key}"] = run("gsettings", "get", schema, key)
    for k in ("list", "default"):
        snap["dconf"][TERM_BASE + k] = run("dconf", "read", TERM_BASE + k)
    for f in ("gtk.css", "gtk-dark.css", "assets"):
        backup_file(GTK4 / f, f"gtk4-{f}", snap)
    snapshot_apps(snap)
    act(f"save snapshot -> {SNAPSHOT}", write, SNAPSHOT, json.dumps(snap, indent=2))


def retire_snapshot():
    """Keep the used snapshot (and its file copies) under a timestamp; the next apply takes a fresh one."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = 0
    while (STATE / f"snapshot.{ts}.json").exists() or (STATE / f"files.{ts}").exists():
        n += 1
        ts = ts.split("-")[0] + f"-{n}"
    files = STATE / "files"

    def go():
        SNAPSHOT.rename(STATE / f"snapshot.{ts}.json")
        if files.exists():
            files.rename(STATE / f"files.{ts}")
    act(f"retire snapshot -> snapshot.{ts}.json", go)


def left_alone(what):
    log(f"{what}: not what rain set (changed since apply?); left alone")


def restore_file(key, f):
    p = Path(f["path"])
    if key == "firefox-user.js":
        if not p.is_file():
            return

        def strip():
            t = "".join(ln for ln in p.read_text().splitlines(True) if ln.rstrip("\n") != USERJS_LINE)
            if t.strip():
                atomic_write(p, t)
            else:
                p.unlink()
        act(f"remove the rain-themes line from {p}", strip)
        return
    ours = rain_gtk4(p) if key.startswith("gtk4-") else rain_css(p)
    if not ours:
        if p.exists() or p.is_symlink():
            left_alone(str(p))
        return

    def put():
        if p.is_symlink() or p.is_file():
            p.unlink()
        else:
            shutil.rmtree(p)
        if "backup" in f:
            (shutil.copytree if Path(f["backup"]).is_dir() else shutil.copy2)(f["backup"], p)
        elif "link" in f:
            p.symlink_to(f["link"])
    act(f"restore {p}", put)


def restore_terminal(snap):
    lk, dk = TERM_BASE + "list", TERM_BASE + "default"
    ours = rain_uuids()
    cur = re.findall(r"'([^']+)'", run("dconf", "read", lk))
    ids = [i for i in cur if i not in ours]
    if ids != cur:
        if not snap["dconf"].get(lk) and len(ids) <= 1:
            act(f"dconf reset {lk}", run, "dconf", "reset", lk)
        else:
            val = "[" + ", ".join(f"'{i}'" for i in ids) + "]"
            act(f"dconf {lk} = {val}", run, "dconf", "write", lk, val)
    if run("dconf", "read", dk).strip("'") in ours:
        v = snap["dconf"].get(dk)
        if v:
            act(f"dconf {dk} = {v}", run, "dconf", "write", dk, v)
        else:
            act(f"dconf reset {dk}", run, "dconf", "reset", dk)
    else:
        left_alone(dk)


def restore():
    if not SNAPSHOT.exists():
        sys.exit("no snapshot; nothing to restore")
    snap = json.loads(SNAPSHOT.read_text())
    for sk, val in snap["gsettings"].items():
        schema, key = sk.split()
        if rain_gsetting(schema, key, run("gsettings", "get", schema, key)):
            act(f"gsettings {schema} {key} = {val}", run, "gsettings", "set", schema, key, val)
        else:
            left_alone(f"gsettings {schema} {key}")
    restore_terminal(snap)
    for key, f in snap["files"].items():
        restore_file(key, f)
    restore_geany(snap)
    restore_brave(snap)
    if "vesktop_enabled" in snap:
        vs = VESKTOP / "settings/settings.json"
        en = json.loads(vs.read_text()).get("enabledThemes", []) if vs.exists() else []
        act("vesktop: disable rain themes", set_vesktop_enabled, [x for x in en if not rain_vesktop(x)])
    st = load_state()
    st["current"] = None
    st.pop("applied", None)
    st["pending"] = {k: v for k, v in st.get("pending", {}).items() if v == "restore"}
    save_state(st)
    if st["pending"]:
        log(f"snapshot kept until `rain pending` restores {', '.join(st['pending'])}")
    else:
        retire_snapshot()
    log("restored. (Rain profiles/themes stay installed but unused; Firefox keeps the userChrome pref on.)")


def restore_geany(snap):
    if "geany_color_scheme" not in snap:
        return
    if running("geany"):
        log("Geany is running: queued, it will be restored by `rain pending` (runs at login)")
        mark_pending("geany", "restore")
        return
    m = re.search(r"^color_scheme=(.*)$", GEANY_CONF.read_text(), re.M) if GEANY_CONF.exists() else None
    if m and rain_geany(m.group(1)):
        act("geany color_scheme restore", set_geany, snap["geany_color_scheme"])
    else:
        left_alone("geany color_scheme")
    clear_pending("geany")


def restore_brave(snap):
    if snap.get("brave_theme") is None:
        return
    if running("brave"):
        log("Brave is running: queued, it will be restored by `rain pending` (runs at login)")
        mark_pending("brave", "restore")
        return
    if BRAVE_PREFS.exists() and rain_brave(json.loads(BRAVE_PREFS.read_text()).get("browser", {}).get("theme")):
        act("brave theme restore", set_brave_theme, snap["brave_theme"])
    else:
        left_alone("brave theme")
    clear_pending("brave")


# ---------- targets ----------
def set_geany(value):
    t = GEANY_CONF.read_text()
    atomic_write(GEANY_CONF, re.sub(r"^color_scheme=.*$", f"color_scheme={value}", t, flags=re.M))


def set_brave_theme(theme):
    p = json.loads(BRAVE_PREFS.read_text())
    p.setdefault("browser", {})["theme"] = theme
    atomic_write(BRAVE_PREFS, json.dumps(p, separators=(",", ":")))


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
        log("Geany is running: queued, it will be applied by `rain pending` (runs at login)")
        mark_pending("geany", slug)
        return
    src = exp / f"geany-{slug}.conf"
    dst = HOME / ".config/geany/colorschemes" / src.name
    act(f"geany scheme -> {dst}", lambda: (dst.parent.mkdir(parents=True, exist_ok=True), shutil.copy2(src, dst)))
    act(f"geany color_scheme={src.name}", set_geany, src.name)
    clear_pending("geany")


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
            atomic_write(uj, t + ("" if t.endswith("\n") or not t else "\n") + USERJS_LINE + "\n")
    act(f"firefox userChrome/userContent + user.js pref in {ff}", go)


def apply_brave(slug, exp):
    if not BRAVE_PREFS.exists():
        log("skip Brave: no Preferences file")
        return
    if running("brave"):
        log("Brave is running: queued, it will be applied by `rain pending` (runs at login)")
        mark_pending("brave", slug)
        return
    seed = json.loads((exp / "brave.json").read_text())

    def go():
        p = json.loads(BRAVE_PREFS.read_text())
        th = p.setdefault("browser", {}).setdefault("theme", {})
        th.update({"user_color2": seed["user_color2"], "color_scheme2": 2})
        p.setdefault("extensions", {}).setdefault("theme", {})["id"] = "user_color_theme_id"
        atomic_write(BRAVE_PREFS, json.dumps(p, separators=(",", ":")))
    act(f"brave seed colour {seed['seed']} (dark)", go)
    clear_pending("brave")


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


FNS = {"gtk": apply_gtk, "wallpaper": apply_wallpaper, "terminal": apply_terminal, "geany": apply_geany,
       "firefox": apply_firefox, "brave": apply_brave, "vesktop": apply_vesktop}


def exportable():
    """Slugs that have desktop exports, sorted."""
    return sorted(p.parent.parent.name for p in ROOT.glob("*/desktop/colloid.json"))


def apply(slug, only=None, dry=False):
    global DRY
    DRY = dry
    exp = ROOT / slug / "desktop"
    if not exp.exists():
        sys.exit(f"{slug}: no desktop exports (add ansi/terminal/syntax to its spec, then `rain build`)")
    only = only or TARGETS
    bad = set(only) - set(TARGETS)
    if bad:
        sys.exit(f"unknown targets {sorted(bad)}; valid: {','.join(TARGETS)}")
    take_snapshot()
    for t in TARGETS:
        if t in only:
            FNS[t](slug, exp)
    if not dry:
        st = load_state()
        st["applied"] = True
        if set(only) >= {"gtk", "terminal"}:
            st["current"] = slug
        save_state(st)
    print("\nManual steps (Dark Reader, Niagara, Claude Code): " + str(exp / "README.md"))


def run_pending(dry=False):
    """Finish targets that were skipped because their app was running."""
    global DRY
    DRY = dry
    pending = dict(load_state().get("pending", {}))
    if not pending:
        log("nothing pending")
        return
    snap = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else None
    restored = False
    for target, what in pending.items():
        if what == "restore" and snap is None:
            log(f"dropping pending {target} restore: no snapshot")
            clear_pending(target)
        elif what == "restore":
            {"geany": restore_geany, "brave": restore_brave}[target](snap)
            restored = True
        elif (ROOT / what / "desktop").exists():
            FNS[target](what, ROOT / what / "desktop")
        else:
            log(f"dropping pending {target}: {what} has no exports")
            clear_pending(target)
    # keep the snapshot while a later apply is live: the next restore still needs it
    st = load_state()
    if restored and "restore" not in st.get("pending", {}).values() and not st.get("current") \
            and not st.get("applied") and not DRY:
        retire_snapshot()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--only", help="comma list of " + ",".join(TARGETS))
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--pending", action="store_true", help="finish targets queued while their app was running")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--build-gtk", metavar="SLUG")
    ap.add_argument("--dest")
    a = ap.parse_args()
    global DRY
    DRY = a.dry_run
    if a.build_gtk:
        print(build_gtk(a.build_gtk, a.dest or THEMES_DIR))
    elif a.restore:
        restore()
    elif a.pending:
        run_pending(a.dry_run)
    elif a.slug:
        apply(a.slug, a.only.split(",") if a.only else None, a.dry_run)
    else:
        ap.error("slug, --restore or --pending required")


if __name__ == "__main__":
    main()
