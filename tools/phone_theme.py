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

The first run on a phone that isn't already themed saves its original setting to
~/.local/state/rain-themes/phone-snapshot.<ro.serialno>.json; --restore writes it back.
Snapshots and phone-state.json are kept per device (ro.serialno, which unlike the
Wireless debugging address doesn't change between pairings). Needs one adb device.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from apply_theme import atomic_write  # noqa: E402
from desktop_export import Colours  # noqa: E402

KEY = "theme_customization_overlay_packages"
P = "android.theme.customization."
STYLES = ["TONAL_SPOT", "VIBRANT", "EXPRESSIVE", "SPRITZ", "RAINBOW", "FRUIT_SALAD",
          "CONTENT", "MONOCHROMATIC", "FIDELITY"]
STATE_DIR = Path.home() / ".local/state/rain-themes"
LEGACY_SNAPSHOT = STATE_DIR / "phone-snapshot.json"  # before per-device keys: one flat snapshot
STATE = STATE_DIR / "phone-state.json"  # {ro.serialno: {"current": slug, "style": ...}}
REMOTE = "/sdcard/Download/rain-themes"
FILES = ["wallpaper-phone.png", "sync-theme.json", "{slug}.app-theme.json",
         "{slug}.heliboard.json", "{slug}-light.heliboard.json",
         "{slug}.heliboard-simple.json", "{slug}-light.heliboard-simple.json"]  # missing files are skipped


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
    """Pick the phone: $ANDROID_SERIAL if set, else the only device, else the only non-emulator
    (an emulator started by another session shouldn't block this). Exported so every adb call uses it."""
    if os.environ.get("ANDROID_SERIAL"):
        return
    devs = [ln.split()[0] for ln in adb("devices").splitlines()[1:] if ln.strip().endswith("device")]
    phones = [d for d in devs if not d.startswith("emulator-")]
    pick = devs if len(devs) == 1 else phones
    if len(pick) != 1:
        sys.exit(f"can't pick a phone from {devs or 'no devices'}; pair via Wireless debugging, "
                 "or set ANDROID_SERIAL")
    os.environ["ANDROID_SERIAL"] = pick[0]


def read_setting():
    v = adb("shell", "settings", "get", "secure", KEY)
    return {} if v in ("", "null") else json.loads(v)


def write_setting(value, dry):
    value = dict(value, _applied_timestamp=int(time.time() * 1000))  # SystemUI re-applies on change
    text = json.dumps(value, separators=(",", ":"))
    adb("shell", f"settings put secure {KEY} '{text}'", dry=dry)
    return value


def legacy(st):
    return "current" in st or "style" in st


def load_state():
    """{device id: {"current", "style"}}; a pre-per-device flat state shows up under "legacy"."""
    try:
        st = json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}
    return {"legacy": st} if legacy(st) else st


def summary():
    """For the GUI (no adb): slugs applied on any device, and the style of the last apply."""
    devs = list(load_state().values())
    return {d.get("current") for d in devs} - {None}, (devs[-1].get("style") if devs else None)


def save_state(dev, entry, dry):
    if dry:
        return
    st = load_state()
    st.pop(dev, None)
    if entry:
        st[dev] = entry  # last applied device last, for summary()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(STATE, json.dumps(st, indent=2) + "\n")


def device_id():
    """ro.serialno of the picked device, as used in file names."""
    serial = adb("shell", "getprop", "ro.serialno")
    if not serial:
        sys.exit("adb: device reports no ro.serialno")
    return re.sub(r"[^\w.-]", "_", serial)


def snapshot_path(dev):
    return STATE_DIR / f"phone-snapshot.{dev}.json"


def migrate(dev, dry):
    """Move the flat pre-per-device snapshot/state to this device, but never to an emulator."""
    st = load_state()
    if not LEGACY_SNAPSHOT.exists() and "legacy" not in st:
        return
    if os.environ["ANDROID_SERIAL"].startswith("emulator-"):
        sys.exit(f"{LEGACY_SNAPSHOT.name} predates per-device snapshots and belongs to the phone; "
                 "connect the phone once (rain phone <slug>) so it moves there, then retry the emulator")
    print(f"migrate {LEGACY_SNAPSHOT.name} and {STATE.name} to device {dev}")
    if dry:
        return
    if LEGACY_SNAPSHOT.exists():  # keep an existing per-device one; the flat file is then only an old copy
        LEGACY_SNAPSHOT.rename(snapshot_path(dev) if not snapshot_path(dev).exists()
                               else STATE_DIR / f"phone-snapshot.{dev}.legacy.json")
    if "legacy" in st:
        save_state("legacy", None, dry)
        if dev not in load_state():
            save_state(dev, st["legacy"], dry)


def rain_seeds():
    return {seed(p.parent.name).lstrip("#").lower() for p in ROOT.glob("*/theme.spec.json")
            if "ansi" in json.loads(p.read_text())}


def seed(slug):
    spec = json.loads((ROOT / slug / "theme.spec.json").read_text())
    if "ansi" not in spec:
        sys.exit(f"{slug} has no desktop blocks")
    return Colours(spec).role["brand"]


def apply(slug, style, files, dry):
    check_device()
    dev = device_id()
    migrate(dev, dry)
    snap = snapshot_path(dev)
    cur = read_setting()
    if not snap.exists():
        if load_state().get(dev, {}).get("current") or \
                str(cur.get(P + "system_palette", "")).lower() in rain_seeds():
            print("warning: phone already themed and no snapshot: not snapshotting (it would capture Rain "
                  "state); `rain phone --restore` stays unavailable for this device")
        else:
            print(f"save original setting -> {snap}")
            if not dry:
                snap.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(snap, json.dumps(cur, indent=2) + "\n")
    hexs = seed(slug).lstrip("#")
    new = {k: v for k, v in cur.items() if not k.startswith("_")}
    new.update({P + "color_source": "preset", P + "system_palette": hexs,
                P + "accent_color": hexs, P + "theme_style": style})
    new.setdefault(P + "color_both", "1")
    print(f"system colours: seed #{hexs}, style {style}")
    write_setting(new, dry)
    save_state(dev, {"current": slug, "style": style}, dry)
    if files:
        dest = f"{REMOTE}/{slug}"
        adb("shell", "mkdir", "-p", dest, dry=dry)
        for f in FILES:
            f = f.format(slug=slug)
            src = ROOT / slug / "desktop" / f
            if src.exists():
                adb("push", str(src), f"{dest}/{f}", dry=dry)
                # adb-pushed files stay is_pending=1 in MediaStore (hidden from file pickers,
                # e.g. HeliBoard's Load showed an empty folder) until they're scanned
                adb("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                    "-d", f"file://{dest}/{f}", dry=dry)
        print(f"files in {dest}: set the wallpaper, import sync/redeye themes on the phone")


def restore(dry):
    check_device()
    dev = device_id()
    migrate(dev, dry)
    if not snapshot_path(dev).exists():
        sys.exit(f"no phone snapshot for device {dev}; nothing to restore")
    snap = json.loads(snapshot_path(dev).read_text())
    print("restore original system colour setting")
    write_setting({k: v for k, v in snap.items() if not k.startswith("_")}, dry)
    save_state(dev, None, dry)


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
