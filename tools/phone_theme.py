#!/usr/bin/env python3
"""Theme an Android phone (stock Android 12+) over adb. No root needed.

    python3 tools/phone_theme.py <slug> [--style TONAL_SPOT] [--no-files] [--dry-run]
    python3 tools/phone_theme.py --restore [--dry-run]

- System colours: writes the palette's accent as the Material You seed into
  `secure theme_customization_overlay_packages` (what Settings -> Wallpaper & style
  writes). SystemUI re-derives the system/app palettes from it. Checked on a
  stock Android 17 (2026-09-29).
- Files: copies wallpaper-phone.png, sync-theme.json, <slug>.app-theme.json and the HeliBoard
  colour files to
  /sdcard/Download/rain-themes/<slug>/ so they can be picked on the phone. adb
  can't set the wallpaper or import into apps; those taps stay manual.

The first run saves the phone's original setting to
~/.local/state/rain-themes/phone-snapshot.json; --restore writes it back.
Needs one adb device (e.g. over Wireless debugging).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from desktop_export import Colours  # noqa: E402

KEY = "theme_customization_overlay_packages"
P = "android.theme.customization."
STYLES = ["TONAL_SPOT", "VIBRANT", "EXPRESSIVE", "SPRITZ", "RAINBOW", "FRUIT_SALAD",
          "CONTENT", "MONOCHROMATIC", "FIDELITY"]
SNAPSHOT = Path.home() / ".local/state/rain-themes/phone-snapshot.json"
STATE = Path.home() / ".local/state/rain-themes/phone-state.json"  # {"current": slug, "style": ...}
REMOTE = "/sdcard/Download/rain-themes"
FILES = ["wallpaper-phone.png", "sync-theme.json", "{slug}.app-theme.json",
         "{slug}.heliboard.json", "{slug}-light.heliboard.json"]  # missing files are skipped


def adb(*args, dry=False, capture=True):
    cmd = ["adb", *args]
    if dry:
        print("would run:", " ".join(cmd))
        return ""
    r = subprocess.run(cmd, capture_output=capture, text=True)
    if r.returncode:
        sys.exit(f"adb failed: {' '.join(cmd)}\n{r.stderr.strip()}")
    return (r.stdout or "").strip()


def check_device():
    devs = [ln for ln in adb("devices").splitlines()[1:] if ln.strip().endswith("device")]
    if len(devs) != 1:
        sys.exit(f"need exactly one adb device, found {len(devs)} (pair via Wireless debugging)")


def read_setting():
    v = adb("shell", "settings", "get", "secure", KEY)
    return {} if v in ("", "null") else json.loads(v)


def write_setting(value, dry):
    value = dict(value, _applied_timestamp=int(time.time() * 1000))  # SystemUI re-applies on change
    text = json.dumps(value, separators=(",", ":"))
    adb("shell", f"settings put secure {KEY} '{text}'", dry=dry)
    return value


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(st, dry):
    if not dry:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, indent=2) + "\n")


def seed(slug):
    spec = json.loads((ROOT / slug / "theme.spec.json").read_text())
    if "ansi" not in spec:
        sys.exit(f"{slug} has no desktop blocks")
    return Colours(spec).role["brand"]


def apply(slug, style, files, dry):
    check_device()
    cur = read_setting()
    if not SNAPSHOT.exists():
        print(f"save original setting -> {SNAPSHOT}")
        if not dry:
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT.write_text(json.dumps(cur, indent=2) + "\n")
    hexs = seed(slug).lstrip("#")
    new = {k: v for k, v in cur.items() if not k.startswith("_")}
    new.update({P + "color_source": "preset", P + "system_palette": hexs,
                P + "accent_color": hexs, P + "theme_style": style})
    new.setdefault(P + "color_both", "1")
    print(f"system colours: seed #{hexs}, style {style}")
    write_setting(new, dry)
    save_state({"current": slug, "style": style}, dry)
    if files:
        dest = f"{REMOTE}/{slug}"
        adb("shell", "mkdir", "-p", dest, dry=dry)
        for f in FILES:
            f = f.format(slug=slug)
            src = ROOT / slug / "desktop" / f
            if src.exists():
                adb("push", str(src), f"{dest}/{f}", dry=dry)
        # make the wallpaper show up in Photos / the wallpaper picker
        adb("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", f"file://{dest}/wallpaper-phone.png", dry=dry)
        print(f"files in {dest}: set the wallpaper, import sync/redeye themes on the phone")


def restore(dry):
    if not SNAPSHOT.exists():
        sys.exit("no phone snapshot; nothing to restore")
    check_device()
    snap = json.loads(SNAPSHOT.read_text())
    print("restore original system colour setting")
    write_setting({k: v for k, v in snap.items() if not k.startswith("_")}, dry)
    save_state({}, dry)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--style", default="TONAL_SPOT", choices=STYLES,
                    help="Material You style (VIBRANT stays closest to the accent)")
    ap.add_argument("--no-files", action="store_true", help="only set the system colours")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.restore:
        restore(a.dry_run)
    elif a.slug:
        apply(a.slug, a.style, not a.no_files, a.dry_run)
    else:
        ap.error("give a slug or --restore")


if __name__ == "__main__":
    main()
