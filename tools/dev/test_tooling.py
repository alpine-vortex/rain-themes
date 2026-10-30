#!/usr/bin/env python3
"""Acceptance tests for the tooling: pre-commit/merge/push hooks, install, restore, snapshot guard, phone, atomic writes.

    python3 tools/dev/test_tooling.py [-v] [-k pattern]

Everything runs in scratch dirs. Git tests use a clone pruned to three palettes with this
tree's tools/ copied over. Desktop and phone tests run in a child python with HOME set before
import, run()/running()/build_gtk patched, no session bus, and fake gsettings/dconf/pgrep/adb
first on PATH (the first three fail loudly if a patch is missed). Nothing touches the live
desktop, phone or ~/.local/state.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
# Scratch clones must stay inside this checkout unless the caller selects another safe path.
os.environ.setdefault("TMPDIR", str(ROOT / ".test-scratch"))
Path(os.environ["TMPDIR"]).mkdir(parents=True, exist_ok=True)
KEEP = ("librekai", "dracula", "gruvbox")  # palettes left in the scratch clone (keeps `rain check` fast)
LOUD = "#!/bin/sh\necho \"$(basename \"$0\") $*\" >> \"$HOME/fake-calls.log\"\nexit 99\n"
FAKE_ADB = r'''#!/usr/bin/env python3
import json, os, sys
db = os.environ["FAKE_ADB"]
st = json.load(open(db))
a = sys.argv[1:]
open(db + ".log", "a").write(" ".join(a) + "\n")
if a == ["devices"]:
    print("List of devices attached")
    for t in st["devices"]:
        print(f"{t}\tdevice")
    sys.exit(0)
dev = st["devices"].get(os.environ.get("ANDROID_SERIAL", ""))
if dev is None:
    sys.exit("fake adb: no ANDROID_SERIAL device")
if a == ["shell", "getprop", "ro.serialno"]:
    print(dev["serial"])
elif a[:3] == ["shell", "settings", "get"]:
    print(dev["setting"])
elif len(a) == 2 and a[0] == "shell" and a[1].startswith("settings put secure "):
    dev["setting"] = a[1].split(" ", 4)[4].strip("'")
    json.dump(st, open(db, "w"))
'''


def bins(d, fakes):
    d.mkdir(parents=True, exist_ok=True)
    for name, text in fakes.items():
        (d / name).write_text(text)
        (d / name).chmod(0o755)
    return d


def env_for(home, bin_dir, **extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "ANDROID_", "XDG_", "DBUS_"))
           and k not in ("DISPLAY", "WAYLAND_DISPLAY", "CLAUDE_CONFIG_DIR")}
    env.update(HOME=str(home), PATH=f"{bin_dir}:{os.environ['PATH']}", GSETTINGS_BACKEND="memory",
               DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent", PYTHONDONTWRITEBYTECODE="1")
    env.update(extra)
    return env


# ---------- git: pre-commit hook and install (items 1, 2) ----------
class GitHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="rain-test-git-"))
        cls.gitconfig = cls.tmp / "gitconfig"
        cls.gitconfig.write_text("[user]\n\tname = test\n\temail = test@example.invalid\n"
                                 "[init]\n\tdefaultBranch = main\n[advice]\n\tdetachedHead = false\n")
        tpl = cls.tmp / "template"
        cls.git_env = env_for(cls.tmp / "h", "/nonexistent", GIT_CONFIG_GLOBAL=str(cls.gitconfig),
                              GIT_CONFIG_NOSYSTEM="1")
        cls.git(None, "clone", "-q", "--no-hardlinks", str(ROOT), str(tpl))
        for spec in tpl.glob("*/theme.spec.json"):
            if spec.parent.name not in KEEP:
                cls.git(tpl, "rm", "-rq", spec.parent.name)
        cls.git(tpl, "commit", "-qm", "prune palettes")
        cls.old = cls.git(tpl, "rev-parse", "HEAD").strip()  # the base branch's tools
        shutil.copytree(TOOLS, tpl / "tools", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        build_env = dict(cls.git_env, PATH=os.environ["PATH"])
        built = subprocess.run([str(tpl / "tools/rain"), "build"], cwd=tpl, env=build_env,
                               capture_output=True, text=True)
        if built.returncode:
            raise AssertionError(f"scratch fixture build failed: {built.stdout}{built.stderr}")
        cls.git(tpl, "add", "-A")
        cls.git(tpl, "commit", "-qm", "this tree's tools", "--allow-empty")
        cls.template = tpl

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def git(cls, cwd, *args, check=True):
        r = subprocess.run(["git", *args], cwd=cwd, env=cls.git_env, capture_output=True, text=True)
        if check and r.returncode:
            raise AssertionError(f"git {' '.join(args)}: {r.stdout}{r.stderr}")
        return r.stdout

    def setUp(self):
        self.s = Path(tempfile.mkdtemp(prefix="t-", dir=self.tmp))
        self.c = self.s / "c"
        self.git(None, "clone", "-q", str(self.template), str(self.c))

    def install(self, where=None, *extra, home=None):
        where = where or self.c
        return subprocess.run([str(where / "tools/rain"), "install", *extra], capture_output=True, text=True,
                              env=dict(self.git_env, HOME=str(home or self.s / "h")))

    def commit(self, *args, cwd=None):
        return subprocess.run(["git", "commit", "-qm", "test", *args], cwd=cwd or self.c, env=self.git_env,
                              capture_output=True, text=True)

    def ok(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def fails(self, r, stale=None):
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"stale: {stale}" if stale else "stale:", r.stdout + r.stderr)

    def installed(self):
        r = self.install()
        self.ok(r)
        return r

    def hook(self, name="pre-commit"):
        return Path(self.git(self.c, "rev-parse", "--path-format=absolute", "--git-path", f"hooks/{name}").strip())

    def stale_commit(self):
        """Commit a stale generated file past the hooks, then put the good file back in index + tree."""
        notes = self.c / "dracula/dracula-notes.md"
        good = notes.read_text()
        notes.write_text(good + "junk\n")
        self.git(self.c, "add", "dracula/dracula-notes.md")
        self.ok(self.commit("--no-verify"))
        notes.write_text(good)
        self.git(self.c, "add", "dracula/dracula-notes.md")

    def edit_spec(self, slug="librekai"):
        f = self.c / slug / "theme.spec.json"
        t = f.read_text()
        m = re.search(r"#([0-9A-Fa-f]{6})", t)
        new = "#123456" if m.group(1).lower() != "123456" else "#654321"
        f.write_text(t[:m.start()] + new + t[m.end():])
        self.ok(subprocess.run([str(self.c / "tools/rain"), "build", slug], capture_output=True, text=True,
                               env=self.git_env))
        changed = self.git(self.c, "status", "--porcelain", slug).splitlines()
        self.assertGreater(len(changed), 1, changed)

    def test_01_install_writes_hook_and_only_under_home(self):
        hook = Path(self.git(self.c, "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-commit").strip())
        self.assertTrue(str(hook).startswith(str(self.s)))
        r = self.installed()
        for ln in r.stdout.splitlines():
            if ln.startswith("wrote "):
                self.assertTrue(ln[6:].startswith((str(self.s / "h"), str(hook.parent))), ln)
        self.assertIn('git checkout-index -a --ignore-skip-worktree-bits --prefix="$tmp/"', hook.read_text())
        self.assertTrue(os.access(hook, os.X_OK))
        merge, push = self.hook("pre-merge-commit"), self.hook("pre-push")
        self.assertEqual(merge.read_text(), hook.read_text())
        self.assertIn("refs/heads/main", push.read_text())
        self.assertTrue(os.access(merge, os.X_OK) and os.access(push, os.X_OK))
        self.assertTrue((self.s / "h/.local/share/applications/rain-themes.desktop").exists())

    def test_02_generated_staged_without_spec_fails(self):
        self.installed()
        self.edit_spec()
        self.git(self.c, "add", "librekai")
        self.git(self.c, "reset", "-q", "librekai/theme.spec.json")
        self.fails(self.commit())

    def test_03_spec_and_outputs_staged_succeeds(self):
        self.installed()
        self.edit_spec()
        self.git(self.c, "add", "librekai")
        self.ok(self.commit())

    def test_04_unstaged_and_untracked_wip_elsewhere_does_not_block(self):
        self.installed()
        self.edit_spec()
        self.git(self.c, "add", "librekai")
        with open(self.c / "dracula/dracula-notes.md", "a") as f:
            f.write("wip\n")
        (self.c / "newpal").mkdir()
        (self.c / "newpal/theme.spec.json").write_text("{}")
        self.ok(self.commit())

    def stale_index_fixed_in_worktree(self):
        self.edit_spec()
        self.git(self.c, "add", "librekai")
        notes = self.c / "librekai/librekai-notes.md"
        good = notes.read_text()
        notes.write_text(good + "junk\n")
        self.git(self.c, "add", "librekai/librekai-notes.md")
        notes.write_text(good)

    def test_05_commit_a_and_paths_use_the_temporary_index(self):
        self.installed()
        self.stale_index_fixed_in_worktree()
        self.fails(self.commit(), "librekai/librekai-notes.md")
        self.ok(self.commit("librekai"))
        self.git(self.c, "reset", "-q", "--hard", "HEAD~1")
        self.stale_index_fixed_in_worktree()
        self.ok(self.commit("-a"))

    def test_06_staged_tool_change_without_rebuild_fails(self):
        self.installed()
        f = self.c / "tools/build_theme.py"
        f.write_text(f.read_text().replace('"## Derived shades"', '"## Derived Shades"'))
        self.git(self.c, "add", "tools/build_theme.py")
        self.fails(self.commit())

    def test_07_generated_file_removed_from_index_fails(self):
        self.installed()
        self.git(self.c, "rm", "-q", "--cached", "librekai/librekai-notes.md")
        self.fails(self.commit(), "librekai/librekai-notes.md")

    def test_08_install_from_linked_worktree_refuses_before_writing(self):
        wt = self.s / "wt"
        self.git(self.c, "worktree", "add", "-q", str(wt), "-b", "t")
        r = self.install(wt, home=self.s / "h2")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("linked worktree", r.stderr)
        self.assertFalse((self.s / "h2").exists())
        for name in ("pre-commit", "pre-merge-commit", "pre-push"):
            self.assertFalse(self.hook(name).exists(), name)

    def test_09_shared_hook_checks_the_worktree_index(self):
        self.installed()
        wt = self.s / "wt"
        self.git(self.c, "worktree", "add", "-q", str(wt), "-b", "t")
        with open(wt / "dracula/dracula-notes.md", "a") as f:
            f.write("junk\n")
        self.git(wt, "add", "dracula/dracula-notes.md")
        self.fails(self.commit(cwd=wt), "dracula/dracula-notes.md")
        self.assertEqual(self.git(self.c, "status", "--porcelain"), "")

    def test_10_old_branches_and_no_tools_rain(self):
        self.installed()
        self.git(self.c, "checkout", "-q", "-b", "old", self.old)
        with open(self.c / "README.md", "a") as f:
            f.write("\nmore\n")
        self.git(self.c, "add", "README.md")
        self.ok(self.commit())
        with open(self.c / "dracula/dracula-notes.md", "a") as f:
            f.write("junk\n")
        self.git(self.c, "add", "dracula/dracula-notes.md")
        self.fails(self.commit())  # the old branch's own `rain check` ran
        self.git(self.c, "rm", "-q", "tools/rain")
        self.ok(self.commit())  # no tools/rain in the index: nothing to check

    def test_11_existing_hooks_and_core_hookspath(self):
        names = ("pre-commit", "pre-merge-commit", "pre-push")
        mine = "#!/bin/sh\necho mine\n"
        for foreign in names:  # any one foreign hook refuses before anything is written
            for n in names:
                self.hook(n).unlink(missing_ok=True)
            self.hook(foreign).write_text(mine)
            r = self.install()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--force", r.stderr)
            self.assertIn(str(self.hook(foreign)), r.stderr)
            self.assertEqual(self.hook(foreign).read_text(), mine)
            self.assertEqual([n for n in names if self.hook(n).exists()], [foreign])
            self.assertFalse((self.s / "h").exists())
        for n in names:
            self.hook(n).write_text(mine)
        self.ok(self.install(None, "--force"))
        for n in names:
            self.assertIn("checkout-index", self.hook(n).read_text(), n)
        old = '#!/bin/sh\n# rain-themes: refuse commits with stale generated files\nexec "/x/rain" check\n'
        self.hook().write_text(old)
        self.hook("pre-merge-commit").unlink()
        dry = self.install(None, "--dry-run")
        self.ok(dry)
        self.assertIn(f"[dry-run] replace {self.hook()}", dry.stdout)
        self.assertIn(f"[dry-run] write {self.hook('pre-merge-commit')}", dry.stdout)
        self.assertIn(f"[dry-run] replace {self.hook('pre-push')}", dry.stdout)
        self.assertEqual(self.hook().read_text(), old)
        self.ok(self.install())
        self.assertIn("checkout-index", self.hook().read_text())
        self.git(self.c, "config", "core.hooksPath", ".githooks")
        self.ok(self.install())
        for n in names:
            self.assertIn("checkout-index", (self.c / ".githooks" / n).read_text(), n)

    def test_11b_merge_commits_are_checked(self):
        self.installed()
        base = self.git(self.c, "branch", "--show-current").strip()
        self.git(self.c, "checkout", "-q", "-b", "stale")
        self.stale_commit()
        self.git(self.c, "checkout", "-q", base)
        r = subprocess.run(["git", "merge", "--no-ff", "--no-edit", "stale"], cwd=self.c, env=self.git_env,
                           capture_output=True, text=True)
        self.fails(r, "dracula/dracula-notes.md")
        self.assertTrue((self.c / ".git/MERGE_HEAD").exists())
        self.git(self.c, "merge", "--abort")
        self.git(self.c, "checkout", "-q", "-b", "good")
        self.edit_spec()
        self.git(self.c, "add", "librekai")
        self.ok(self.commit())
        self.git(self.c, "checkout", "-q", base)
        self.ok(subprocess.run(["git", "merge", "--no-ff", "--no-edit", "good"], cwd=self.c, env=self.git_env,
                               capture_output=True, text=True))

    def test_11c_pushes_to_main_check_the_pushed_commit(self):
        origin = self.s / "origin.git"
        self.git(None, "clone", "-q", "--bare", str(self.template), str(origin))
        self.git(self.c, "remote", "set-url", "origin", str(origin))
        self.installed()

        def push(*args):
            return subprocess.run(["git", "push", "origin", *args], cwd=self.c, env=self.git_env,
                                  capture_output=True, text=True)
        base = self.git(self.c, "rev-parse", "HEAD").strip()
        self.ok(push("HEAD:refs/heads/main"))
        self.stale_commit()  # HEAD is stale; the index and working tree are good
        self.fails(push("HEAD:refs/heads/main"), "dracula/dracula-notes.md")
        self.ok(push("HEAD:refs/heads/side"))
        self.ok(push("--delete", "side"))
        self.git(self.c, "reset", "-q", "--hard", base)
        self.edit_spec()
        self.git(self.c, "add", "librekai")
        self.ok(self.commit())
        self.ok(push("HEAD:refs/heads/main"))
        self.assertEqual(self.git(origin, "rev-parse", "main"), self.git(self.c, "rev-parse", "HEAD"))

    def test_11d_hook_signals_exit_nonzero_and_clean_up(self):
        self.installed()
        # a check that passes: only the signal can make the hook fail. It goes to the hook shell alone
        # (as `kill <pid>` would), so the check finishes and dash then runs the trap
        (self.c / "tools/rain").write_text("#!/bin/sh\nsleep 1\n")
        self.git(self.c, "add", "tools/rain")
        tmpdir = self.s / "tmpdir"
        tmpdir.mkdir()
        for sig, rc in ((signal.SIGINT, 130), (signal.SIGTERM, 143), (signal.SIGHUP, 129)):
            p = subprocess.Popen([str(self.hook())], cwd=self.c, env=dict(self.git_env, TMPDIR=str(tmpdir)),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.time() + 10
            while not list(tmpdir.glob("tmp.*/tools/rain")) and time.time() < deadline:
                time.sleep(0.05)
            self.assertTrue(list(tmpdir.glob("tmp.*/tools/rain")), sig)
            time.sleep(0.2)  # let the hook reach `rain check`
            os.kill(p.pid, sig)
            self.assertEqual(p.wait(10), rc, sig)
            self.assertEqual(list(tmpdir.iterdir()), [], sig)

    def test_11e_sparse_checkout_still_checks_every_file(self):
        self.installed()
        self.git(self.c, "sparse-checkout", "set", "--cone", "librekai")
        self.assertFalse((self.c / "tools").exists())
        notes = self.c / "librekai/librekai-notes.md"
        good = notes.read_text()
        notes.write_text(good + "junk\n")
        self.git(self.c, "add", "librekai/librekai-notes.md")
        self.fails(self.commit(), "librekai/librekai-notes.md")
        notes.write_text(good)
        self.git(self.c, "add", "librekai/librekai-notes.md")
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.c, env=self.git_env, input="junk\n",
                              capture_output=True, text=True, check=True).stdout.strip()
        self.git(self.c, "update-index", "--cacheinfo", f"100644,{blob},dracula/dracula-notes.md")
        self.fails(self.commit(), "dracula/dracula-notes.md")


# ---------- desktop: restore, snapshot guard, atomic writes (items 3, 4) ----------
PRELUDE = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, TOOLS)
import apply_theme as A
H = Path.home()
B = A.TERM_BASE
G = {"org.cinnamon.theme name": "'Mint-Y-Dark'", "org.cinnamon.desktop.interface gtk-theme": "'Mint-Y'",
     "org.cinnamon.desktop.wm.preferences theme": "'Mint-Y'",
     "org.cinnamon.desktop.background picture-uri": "'file:///orig.png'",
     "org.gnome.TextEditor style-scheme": "'cobalt'", "org.x.editor.preferences.editor scheme": "'macchiato'",
     "org.cinnamon.desktop.interface icon-theme": "'Yaru-blue-dark'"}
D = {B + ":orig/visible-name": "'Default'"}
RUNNING = set()
KILLS = []


def run(*cmd, check=True):
    op = cmd[1]
    if cmd[0] == "gsettings":
        k = f"{cmd[2]} {cmd[3]}"
        if op == "get":
            return G.get(k, "")  # an unknown schema prints nothing (stderr only); callers use check=False
        G[k] = cmd[4] if cmd[4].startswith(("'", "[")) else f"'{cmd[4]}'"  # get prints GVariant text
    elif cmd[0] == "dconf":
        if op == "read":
            return D.get(cmd[2], "")
        if op == "write":
            D[cmd[2]] = cmd[3]
        elif op == "reset":
            D.pop(cmd[2], None)
        elif op == "list":
            return "\n".join(sorted({k[len(cmd[2]):].split("/")[0] + ("/" if "/" in k[len(cmd[2]):] else "")
                                     for k in D if k.startswith(cmd[2])}))
    elif cmd[0] == "pkill":
        KILLS.append(cmd)
    else:
        raise AssertionError(cmd)
    return ""


def build_gtk(slug, dest):
    t = Path(dest) / (json.loads((A.ROOT / slug / "desktop/colloid.json").read_text())["gtk_theme"] + "-Dark")
    (t / "gtk-4.0/assets").mkdir(parents=True, exist_ok=True)
    (t / "libadwaita").mkdir(exist_ok=True)
    (t / "libadwaita/gtk.css").write_text("/* rain */")
    return t


A.run, A.build_gtk, A.running = run, build_gtk, lambda n: n in RUNNING
FF = H / ".mozilla/firefox/p.default"
UJ = FF / "user.js"
GTK4 = H / ".config/gtk-4.0"
VS = H / ".config/vesktop/settings/settings.json"
KT = H / ".config/kitty/current-theme.conf"
KC = H / ".config/kitty/kitty.conf"
GC = H / ".config/ghostty/config.ghostty"
TE = "org.gnome.TextEditor style-scheme"
CS = H / ".claude/settings.json"
XK, IK = "org.x.editor.preferences.editor scheme", "org.cinnamon.desktop.interface icon-theme"
LW = A.LIBREWOLF / "lw.default"
A.ICON_DIRS = [H / ".icons"]
BRAVE = A.BRAVE_PREFS
ORIG_BRAVE = {"user_color2": -14244198, "color_scheme2": 1}
ORIG_BRAVE_EXTENSION_ID = "original-theme"


def rd(p):
    return json.loads(Path(p).read_text())
'''


def make_home(h, gtk4_assets=True):
    (h / ".mozilla/firefox/p.default").mkdir(parents=True)
    (h / ".mozilla/firefox/installs.ini").write_text("[ABC]\nDefault=p.default\n")
    (h / ".config/geany").mkdir(parents=True)
    (h / ".config/geany/geany.conf").write_text("[geany]\ncolor_scheme=mine.conf\n")
    brave = h / ".config/BraveSoftware/Brave-Origin/Default/Preferences"
    brave.parent.mkdir(parents=True)
    brave.write_text(json.dumps({"browser": {"theme": {"user_color2": -14244198, "color_scheme2": 1}},
                                "extensions": {"theme": {"id": "original-theme"}}}))
    brave.chmod(0o600)
    (h / ".config/vesktop/settings").mkdir(parents=True)
    (h / ".config/vesktop/themes").mkdir()
    (h / ".config/vesktop/settings/settings.json").write_text('{"enabledThemes": []}')
    (h / ".config/kitty").mkdir(parents=True)
    (h / ".config/kitty/kitty.conf").write_text("font_size 11\ninclude current-theme.conf\n")
    (h / ".config/kitty/current-theme.conf").write_text("## name: Gruvbox Dark\nbackground #282828\n")
    (h / ".claude").mkdir()
    for v in ("Yaru-blue-dark", "Yaru-red-dark", "Yaru-purple-dark", "Yaru-dark", "Mint-Y", "Mint-Y-Pink"):
        (h / ".icons" / v).mkdir(parents=True)
        (h / ".icons" / v / "index.theme").write_text("[Icon Theme]\n")
    lw = h / ".var/app/io.gitlab.librewolf-community/.librewolf"
    (lw / "lw.default").mkdir(parents=True)
    (lw / "installs.ini").write_text("[X]\nDefault=lw.default\n")
    (h / ".claude/settings.json").write_text('{\n  "model": "opus",\n  "theme": "light-ansi",\n  "x": "é"\n}\n')
    (h / ".config/ghostty").mkdir(parents=True)
    (h / ".config/ghostty/config.ghostty").write_text("font-size = 11\ntheme = Gruvbox Dark\nwindow-decoration = auto\n")
    if gtk4_assets:
        (h / ".config/gtk-4.0/assets").mkdir(parents=True)
        (h / ".config/gtk-4.0/assets/a.png").write_text("orig")


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.s = Path(tempfile.mkdtemp(prefix="rain-test-desk-"))
        self.h = self.s / "h"
        self.h.mkdir()
        self.bin = bins(self.s / "bin", {n: LOUD for n in ("gsettings", "dconf", "pgrep", "pkill", "adb")})

    def tearDown(self):
        shutil.rmtree(self.s, ignore_errors=True)

    def child(self, code, setup=True):
        if setup and not (self.h / ".mozilla").exists():
            make_home(self.h)
        src = f"TOOLS = {str(TOOLS)!r}\n" + PRELUDE + textwrap.dedent(code)
        r = subprocess.run([sys.executable, "-c", src], env=env_for(self.h, self.bin), capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.h / "fake-calls.log").exists(), "a real gsettings/dconf/pgrep/adb was called")
        return r.stdout

    def test_12_userjs_absent(self):
        self.child("""
            A.apply("librekai", ["firefox"])
            assert A.USERJS_LINE in UJ.read_text()
            UJ.write_text(UJ.read_text() + 'user_pref("x", 1);\\n')
            A.restore()
            assert UJ.read_text() == 'user_pref("x", 1);\\n', UJ.read_text()
        """)
        shutil.rmtree(self.h)
        self.h.mkdir()
        self.child("""
            A.apply("librekai", ["firefox"])
            A.restore()
            assert not UJ.exists()
        """)

    def test_13_userjs_backed_up_keeps_later_edits(self):
        self.child("""
            UJ.write_text('user_pref("a", 1);\\n')
            A.apply("librekai", ["firefox"])
            UJ.write_text(UJ.read_text() + 'user_pref("b", 2);\\n')
            A.restore()
            assert UJ.read_text() == 'user_pref("a", 1);\\nuser_pref("b", 2);\\n', UJ.read_text()
        """)

    def test_14_userchrome_replaced_by_user_is_left(self):
        self.child("""
            A.apply("librekai", ["firefox"])
            (FF / "chrome/userChrome.css").write_text("/* mine */")
            A.restore()
            assert (FF / "chrome/userChrome.css").read_text() == "/* mine */"
            assert not (FF / "chrome/userContent.css").exists()
        """)

    def test_15_gtk4_only_rain_links_are_touched(self):
        shutil.rmtree(self.h / ".config/gtk-4.0", ignore_errors=True)
        make_home(self.h, gtk4_assets=False)
        out = self.child("""
            A.apply("librekai", ["gtk"])
            assert all(os.readlink(GTK4 / f).startswith(str(A.THEMES_DIR / "Rain-"))
                       for f in ("gtk.css", "gtk-dark.css", "assets"))
            (GTK4 / "gtk.css").unlink()
            (GTK4 / "gtk.css").write_text("mine")
            (GTK4 / "gtk-dark.css").unlink()
            (GTK4 / "gtk-dark.css").symlink_to("/elsewhere.css")
            import shutil; shutil.rmtree(A.THEMES_DIR)  # dangling rain link
            A.restore()
            assert (GTK4 / "gtk.css").read_text() == "mine"
            assert os.readlink(GTK4 / "gtk-dark.css") == "/elsewhere.css"
            assert not (GTK4 / "assets").is_symlink() and not (GTK4 / "assets").exists()
        """)
        self.assertIn("left alone", out)

    def test_16_vesktop_keeps_user_themes(self):
        self.child("""
            A.apply("librekai", ["vesktop"])
            assert rd(VS)["enabledThemes"] == ["librekai.theme.css"]
            (VS.parent.parent / "themes/other.css").write_text("/* other */")
            A.set_vesktop_enabled(rd(VS)["enabledThemes"] + ["other.css"])
            A.restore()
            assert rd(VS)["enabledThemes"] == ["other.css"], rd(VS)
        """)
        shutil.rmtree(self.h)
        self.h.mkdir()
        self.child("""
            A.apply("librekai", ["vesktop"])
            (VS.parent.parent / "themes/librekai.theme.css").unlink()
            A.restore()
            assert rd(VS)["enabledThemes"] == [], rd(VS)
        """)

    def test_16b_kitty_theme_backfilled_and_restored(self):
        self.child("""
            A.apply("librekai", ["gtk"])
            snap = rd(A.SNAPSHOT)  # a snapshot from before kitty was installed
            snap["files"] = {k: v for k, v in snap["files"].items() if not k.startswith("kitty-")}
            A.write(A.SNAPSHOT, json.dumps(snap))
            orig, conf = KT.read_text(), KC.read_text()
            RUNNING.add("kitty")
            A.apply("librekai", ["kitty"])
            assert KT.read_text() == (A.ROOT / "librekai/desktop/kitty-theme.conf").read_text()
            assert KC.read_text() == conf  # already includes current-theme.conf
            assert KILLS == [("pkill", "-USR1", "-x", "kitty")], KILLS
            A.apply("dracula", ["kitty"])  # switching palettes keeps the original backup
            A.restore()
            assert KT.read_text() == orig and KC.read_text() == conf
            assert len(KILLS) == 3, KILLS
        """)

    def test_16c_kitty_include_added_and_stripped(self):
        self.child("""
            KC.write_text("font_size 11\\n")
            KT.unlink()
            A.apply("librekai", ["kitty"])
            assert KC.read_text() == "font_size 11\\n" + A.KITTY_BLOCK and KT.exists()
            KC.write_text(KC.read_text() + "font_family Mono\\n")
            A.restore()
            assert KC.read_text() == "font_size 11\\nfont_family Mono\\n", KC.read_text()
            assert not KT.exists()
        """)
        self.child("""
            A.apply("librekai", ["kitty"])
            KT.write_text("## picked with kitten themes\\n")
            A.restore()
            assert KT.read_text() == "## picked with kitten themes\\n"
        """)
        import shutil
        shutil.rmtree(self.h)
        self.h.mkdir()
        make_home(self.h)
        shutil.rmtree(self.h / ".config/kitty")
        out = self.child("""
            A.apply("librekai", ["kitty"])
            assert not KT.parent.exists()
        """)
        self.assertIn("skip kitty", out)

    def test_16d_ghostty_theme_line_swapped_and_restored(self):
        self.child("""
            orig = GC.read_text()
            RUNNING.add("ghostty")
            A.apply("librekai", ["ghostty"])
            assert GC.read_text() == orig.replace("theme = Gruvbox Dark", A.GHOSTTY_LINE), GC.read_text()
            th = GC.parent / "themes/rain-themes"
            assert th.read_text() == (A.ROOT / "librekai/desktop/ghostty-theme").read_text()
            assert KILLS == [("pkill", "-USR2", "-x", "ghostty")], KILLS
            A.apply("dracula", ["ghostty"])
            assert GC.read_text().count("theme =") == 1
            GC.write_text(GC.read_text() + "font-family = Mono\\n")
            A.restore()
            assert GC.read_text() == orig + "font-family = Mono\\n", GC.read_text()
        """)
        self.child("""
            A.apply("librekai", ["ghostty"])
            GC.write_text(GC.read_text().replace(A.GHOSTTY_LINE, "theme = Nord"))
            A.restore()
            assert "theme = Nord" in GC.read_text()
        """)
        import shutil
        shutil.rmtree(self.h)
        self.h.mkdir()
        make_home(self.h)
        (self.h / ".config/ghostty/config.ghostty").unlink()
        self.child("""
            A.apply("librekai", ["ghostty"])
            assert GC.read_text() == A.GHOSTTY_LINE + "\\n"
            A.restore()
            assert not GC.exists()
        """)
        shutil.rmtree(self.h / ".config/ghostty")
        shutil.rmtree(self.h / ".local/state")
        out = self.child("""
            A.shutil.which = lambda name: None  # the test PATH still has the real ghostty
            A.apply("librekai", ["ghostty"])
            assert not GC.parent.exists()
        """)
        self.assertIn("skip Ghostty", out)

    def test_16f_claude_code_theme_installed_and_restored(self):
        self.child("""
            orig = CS.read_text()
            A.apply("librekai", ["claude-code"])
            th = H / ".claude/themes/rain-themes.json"
            assert th.read_text() == (A.ROOT / "librekai/desktop/claude-code-theme.json").read_text()
            assert CS.read_text() == orig.replace('"light-ansi"', '"custom:rain-themes"'), CS.read_text()
            A.apply("dracula", ["claude-code"])  # switching palettes only rewrites the theme file
            assert rd(th)["name"] == "Rain Dracula" and rd(A.SNAPSHOT)["claude_theme"] == {"value": "light-ansi"}
            A.restore()
            assert CS.read_text() == orig, CS.read_text()
        """)
        self.child("""
            A.apply("librekai", ["claude-code"])
            s = rd(CS)
            s["theme"] = "dark"  # picked in /theme after the apply
            CS.write_text(json.dumps(s))
            A.restore()
            assert rd(CS)["theme"] == "dark"
        """)
        self.child("""
            CS.write_text('{"model": "opus"}')  # no theme: Claude Code's default
            A.apply("librekai", ["claude-code"])
            assert rd(CS) == {"model": "opus", "theme": "custom:rain-themes"}
            A.restore()
            assert rd(CS) == {"model": "opus"}, rd(CS)
        """)
        import shutil
        shutil.rmtree(self.h / ".claude")
        out = self.child("""
            A.apply("librekai", ["claude-code"])
            assert not CS.parent.exists()
        """)
        self.assertIn("skip Claude Code", out)

    def test_16g_xed_scheme_installed_and_restored(self):
        self.child("""
            A.apply("librekai", ["xed"])
            x = A.XED_STYLES / "xed-librekai.xml"
            assert G[XK] == "'rain-librekai'" and "<metadata>" not in x.read_text(), G[XK]
            A.apply("dracula", ["xed"])
            A.restore()
            assert G[XK] == "'macchiato'", G[XK]
        """)
        self.child("""
            RUNNING.add("xed")
            A.apply("librekai", ["xed"])
            assert G[XK] == "'macchiato'" and A.load_state()["pending"] == {"xed": "librekai"}
            RUNNING.clear()
            A.run_pending()
            assert G[XK] == "'rain-librekai'" and A.load_state()["pending"] == {}
            G[XK] = "'kate'"
            A.restore()
            assert G[XK] == "'kate'"
        """)

    def test_16h_icon_variant_follows_the_accent(self):
        self.child("""
            assert A.icon_variant("#F93B7F", A.ICON_FAMILIES["Yaru"]) == "Yaru-red"
            assert A.icon_variant("#FE8019", A.ICON_FAMILIES["Yaru"]) == "Yaru"
            assert A.icon_variant("#8BA4B0", A.ICON_FAMILIES["Mint-Y"]) == "Mint-Y-Grey"  # greyish accent
            A.apply("librekai", ["icons"])
            assert G[IK] == "'Yaru-red-dark'", G[IK]  # keeps the family and -dark
            A.apply("dracula", ["icons"])
            assert G[IK] == "'Yaru-purple-dark'", G[IK]
            assert rd(A.SNAPSHOT)["icon_theme"] == {"value": "'Yaru-blue-dark'", "rain": "Yaru-purple-dark"}
            A.restore()
            assert G[IK] == "'Yaru-blue-dark'"
        """)
        self.child("""
            A.apply("librekai", ["icons"])
            G[IK] = "'Papirus-Dark'"  # picked by hand after the apply
            A.restore()
            assert G[IK] == "'Papirus-Dark'"
            G[IK] = "'Mint-Y'"
            A.apply("librekai", ["icons"])
            assert G[IK] == "'Mint-Y-Pink'", G[IK]  # only installed variants are candidates
        """)
        out = self.child("""
            G[IK] = "'Papirus-Dark'"
            A.apply("librekai", ["icons"])
            assert G[IK] == "'Papirus-Dark'"
        """)
        self.assertIn("skip icons", out)

    def test_16i_flatpak_overrides_added_and_removed(self):
        self.child("""
            F = A.FLATPAK_GLOBAL
            F.parent.mkdir(parents=True)
            F.write_text("[Context]\\nfilesystems=home;~/.themes:ro;\\n\\n[Environment]\\nX=1\\n")
            orig = F.read_text()
            A.apply("librekai", ["flatpak"])
            assert A.flatpak_filesystems() == ["home", "~/.themes:ro", "xdg-config/gtk-4.0:ro"], F.read_text()
            A.apply("dracula", ["flatpak"])
            assert F.read_text().count("gtk-4.0") == 1
            A.restore()
            assert F.read_text() == orig, F.read_text()  # ~/.themes was there before: kept
        """)
        self.child("""
            F = A.FLATPAK_GLOBAL
            F.unlink()
            A.apply("librekai", ["flatpak"])
            assert A.flatpak_filesystems() == A.FLATPAK_FS
            A.restore()
            assert not F.exists()
        """)

    def test_16j_librewolf_profile_themed_and_restored(self):
        self.child("""
            A.apply("librekai", ["librewolf"])
            assert (LW / "chrome/userChrome.css").read_text() == (A.ROOT / "librekai/desktop/userChrome.css").read_text()
            assert A.USERJS_LINE in (LW / "user.js").read_text()
            assert not (FF / "chrome").exists()  # Firefox untouched
            A.restore()
            assert not (LW / "user.js").exists() and not (LW / "chrome/userChrome.css").exists()
        """)

    def test_16e_text_editor_scheme_installed_and_restored(self):
        self.child("""
            A.apply("librekai", ["gnome-text-editor"])
            assert G[TE] == "'rain-librekai'", G[TE]
            x = A.GTE_STYLES / "gtksourceview-librekai.xml"
            assert x.read_text() == (A.ROOT / "librekai/desktop/gtksourceview-librekai.xml").read_text()
            A.apply("dracula", ["gnome-text-editor"])  # switching palettes keeps the original
            assert G[TE] == "'rain-dracula'" and rd(A.SNAPSHOT)["gte_style_scheme"] == "'cobalt'"
            A.restore()
            assert G[TE] == "'cobalt'", G[TE]
        """)
        self.child("""
            A.apply("librekai", ["gnome-text-editor"])
            G[TE] = "'kate'"  # picked in Text Editor's preferences after the apply
            A.restore()
            assert G[TE] == "'kate'"
        """)
        self.child("""
            RUNNING.add(A.GTE_PROC)
            A.apply("librekai", ["gnome-text-editor"])
            assert G[TE] == "'cobalt'"
            assert A.load_state()["pending"] == {"gnome-text-editor": "librekai"}
            RUNNING.clear()
            A.run_pending()
            assert G[TE] == "'rain-librekai'" and A.load_state()["pending"] == {}
            RUNNING.add(A.GTE_PROC)
            A.restore()  # a running Text Editor already has cobalt loaded: no need to queue
            assert G[TE] == "'cobalt'"
        """)
        out = self.child("""
            del G[TE]
            A.apply("librekai", ["gnome-text-editor"])
            assert TE not in G
        """)
        self.assertIn("skip GNOME Text Editor", out)

    def test_17_gsettings_and_dconf_user_changes_survive(self):
        self.child("""
            A.apply("librekai", ["gtk", "wallpaper", "terminal"])
            pid = sorted(A.rain_uuids() & set(D[B + "list"].strip("[]").replace("'", "").split(", ")))[0]
            assert D[B + "default"] == f"'{pid}'"
            G["org.cinnamon.desktop.interface gtk-theme"] = "'Mint-Y'"
            D[B + "list"] = D[B + "list"][:-1] + ", 'user-x']"
            A.restore()
            assert G["org.cinnamon.desktop.interface gtk-theme"] == "'Mint-Y'"
            assert G["org.cinnamon.theme name"] == "'Mint-Y-Dark'"
            assert G["org.cinnamon.desktop.background picture-uri"] == "'file:///orig.png'"
            assert D[B + "list"] == "['orig', 'user-x']", D
            assert B + "default" not in D
        """)
        self.child("""
            A.apply("librekai", ["terminal"])
            A.restore()
            assert B + "list" not in D and B + "default" not in D, D  # implicit single profile: reset
        """)

    def test_18_retire_after_pending_restore(self):
        self.child("""
            A.apply("librekai")
            RUNNING.add("geany")
            A.restore()
            assert A.SNAPSHOT.exists()
            assert A.load_state()["pending"] == {"geany": "restore"}, A.load_state()
            assert "color_scheme=geany-librekai.conf" in A.GEANY_CONF.read_text()
            assert rd(BRAVE)["browser"]["theme"] == ORIG_BRAVE
            assert rd(BRAVE)["extensions"]["theme"]["id"] == ORIG_BRAVE_EXTENSION_ID
            assert (GTK4 / "assets/a.png").read_text() == "orig"
            RUNNING.clear()
            A.run_pending()
            assert "color_scheme=mine.conf" in A.GEANY_CONF.read_text()
            assert A.load_state()["pending"] == {}
            assert not A.SNAPSHOT.exists() and not (A.STATE / "files").exists()
            assert len(list(A.STATE.glob("snapshot.*.json"))) == 1 and len(list(A.STATE.glob("files.*"))) == 1
            A.apply("librekai")
            assert A.SNAPSHOT.exists() and (A.STATE / "files/gtk4-assets/a.png").exists()
        """)

    def test_18b_apply_after_restore_keeps_snapshot(self):
        self.child("""
            A.apply("librekai")
            RUNNING.add("brave")
            A.restore()
            assert A.load_state()["pending"] == {"brave": "restore"}
            A.apply("librekai", ["gtk", "terminal"])
            assert A.load_state()["pending"] == {"brave": "restore"}  # not dropped
            RUNNING.clear()
            A.run_pending()
            assert rd(BRAVE)["browser"]["theme"] == ORIG_BRAVE  # the queued restore ran
            assert rd(BRAVE)["extensions"]["theme"]["id"] == ORIG_BRAVE_EXTENSION_ID
            assert A.SNAPSHOT.exists() and not list(A.STATE.glob("snapshot.*.json"))
            A.restore()  # still recoverable
            assert G["org.cinnamon.desktop.interface gtk-theme"] == "'Mint-Y'"
            assert not A.SNAPSHOT.exists() and len(list(A.STATE.glob("snapshot.*.json"))) == 1
        """)

    def test_18c_partial_apply_after_restore_keeps_snapshot(self):
        self.child("""
            A.apply("librekai")
            RUNNING.add("geany")
            A.restore()
            assert A.load_state()["pending"] == {"geany": "restore"}
            A.apply("librekai", ["firefox"])
            st = A.load_state()
            assert st.get("applied") and not st.get("current"), st
            RUNNING.clear()
            A.run_pending()
            assert "color_scheme=mine.conf" in A.GEANY_CONF.read_text()
            assert A.SNAPSHOT.exists() and not list(A.STATE.glob("snapshot.*.json"))
        """)

    def test_19_themed_without_snapshot_applies_without_snapshotting(self):
        out = self.child("""
            A.STATE.mkdir(parents=True)
            A.STATE_FILE.write_text(json.dumps({"current": "librekai", "pending": {}}))
            A.apply("librekai")
            assert not A.SNAPSHOT.exists()
            A.apply("librekai")
            assert not A.SNAPSHOT.exists()
            before = dict(G), dict(D)
            try:
                A.restore()
                raise AssertionError("restore should exit")
            except SystemExit as e:
                assert "nothing to restore" in str(e)
            assert (dict(G), dict(D)) == before
        """)
        self.assertEqual(out.count("desktop already themed and no snapshot"), 2)
        shutil.rmtree(self.h)
        self.h.mkdir()
        out = self.child("""
            G["org.cinnamon.desktop.interface gtk-theme"] = "'Rain-Librekai-Dark'"
            A.apply("librekai", ["firefox"])
            assert not A.SNAPSHOT.exists()
        """)
        self.assertIn("desktop already themed and no snapshot", out)
        shutil.rmtree(self.h)
        self.h.mkdir()
        self.child("""
            A.apply("librekai", ["firefox"])  # partial apply: current stays None
            assert A.SNAPSHOT.exists() and A.load_state().get("current") is None
            A.SNAPSHOT.unlink()
            A.apply("librekai", ["vesktop"])
            assert not A.SNAPSHOT.exists()
        """)

    def test_19b_backfill_skips_rain_values(self):
        self.child("""
            A.apply("librekai", ["gtk"])
            snap = rd(A.SNAPSHOT)
            del snap["brave_fields"], snap["geany_color_scheme"]
            A.write(A.SNAPSHOT, json.dumps(snap))
            A.apply_brave("librekai", A.ROOT / "librekai/desktop")
            A.apply("librekai", ["gtk"])
            snap = rd(A.SNAPSHOT)
            assert "brave_fields" not in snap and snap["geany_color_scheme"] == "mine.conf", snap
        """)

    def test_19c_brave_restores_only_unchanged_owned_fields(self):
        self.child("""
            A.apply("librekai", ["brave"])
            prefs = rd(BRAVE)
            prefs["browser"]["theme"]["color_scheme2"] = 7
            prefs["browser"]["theme"]["user_customized"] = True
            A.write(BRAVE, json.dumps(prefs))
            A.restore()
            prefs = rd(BRAVE)
            assert prefs["browser"]["theme"]["user_color2"] == ORIG_BRAVE["user_color2"], prefs
            assert prefs["browser"]["theme"]["color_scheme2"] == 7, prefs
            assert prefs["browser"]["theme"]["user_customized"] is True, prefs
            assert prefs["extensions"]["theme"]["id"] == ORIG_BRAVE_EXTENSION_ID, prefs
        """)

    def test_19d_brave_restore_handles_originally_absent_fields(self):
        self.child("""
            prefs = rd(BRAVE)
            prefs["browser"]["theme"].pop("color_scheme2")
            prefs["extensions"]["theme"].pop("id")
            A.write(BRAVE, json.dumps(prefs))
            A.apply("librekai", ["brave"])
            A.restore()
            prefs = rd(BRAVE)
            assert "color_scheme2" not in prefs["browser"]["theme"], prefs
            assert "id" not in prefs["extensions"]["theme"], prefs
        """)

    def test_19e_brave_legacy_snapshot_does_not_guess_extension_id(self):
        self.child("""
            A.apply("librekai", ["brave"])
            snap = rd(A.SNAPSHOT)
            snap["brave_theme"] = ORIG_BRAVE
            del snap["brave_fields"]
            A.write(A.SNAPSHOT, json.dumps(snap))
            A.restore()
            prefs = rd(BRAVE)
            assert prefs["browser"]["theme"] == ORIG_BRAVE, prefs
            assert prefs["extensions"]["theme"]["id"] == "user_color_theme_id", prefs
        """)

    def test_19f_firefox_explicit_profile_applies_and_restores(self):
        self.child("""
            other = H / ".mozilla/firefox/p.other"
            other.mkdir()
            (other / "prefs.js").write_text("// profile marker\\n")
            (other / "user.js").write_text('user_pref("other", true);\\n')
            A.apply("librekai", ["firefox"], profiles={"firefox": str(other)})
            assert A.USERJS_LINE in (other / "user.js").read_text()
            assert (other / "chrome/userChrome.css").exists()
            assert not (FF / "chrome/userChrome.css").exists()
            A.restore()
            assert (other / "user.js").read_text() == 'user_pref("other", true);\\n'
            assert not (other / "chrome/userChrome.css").exists()
        """)

    def test_19g_refuses_to_retarget_browser_profile_under_active_snapshot(self):
        self.child("""
            A.apply("librekai", ["firefox"])
            other = H / ".mozilla/firefox/p.other"
            other.mkdir()
            (other / "prefs.js").write_text("// profile marker\\n")
            try:
                A.apply("dracula", ["firefox"], profiles={"firefox": str(other)})
                raise AssertionError("expected profile retarget to be refused")
            except SystemExit as e:
                assert "restore before applying to another profile" in str(e), e
            assert not (other / "chrome/userChrome.css").exists()
        """)

    def test_19h_brave_explicit_profile_applies_and_restores(self):
        self.child("""
            other = H / ".config/BraveSoftware/Brave-Origin/Other/Preferences"
            other.parent.mkdir(parents=True)
            original = {"browser": {"theme": {"user_color2": 17, "color_scheme2": 0}},
                        "extensions": {"theme": {"id": "other-theme"}}}
            A.write(other, json.dumps(original))
            A.apply("librekai", ["brave"], profiles={"brave": str(other)})
            assert rd(other)["browser"]["theme"]["user_color2"] != 17
            assert rd(BRAVE)["browser"]["theme"] == ORIG_BRAVE
            A.restore()
            assert rd(other) == original, rd(other)
        """)

    def test_19i_brave_pending_apply_remembers_explicit_profile(self):
        self.child("""
            other = H / ".config/BraveSoftware/Brave-Origin/Other/Preferences"
            other.parent.mkdir(parents=True)
            A.write(other, json.dumps({"browser": {"theme": {"user_color2": 17}}}))
            RUNNING.add("brave")
            A.apply("librekai", ["brave"], profiles={"brave": str(other)})
            assert A.load_state()["pending"]["brave"]["preferences"] == str(other)
            RUNNING.clear()
            A.run_pending()
            assert rd(other)["browser"]["theme"]["user_color2"] != 17
            A.restore()
            assert rd(other)["browser"]["theme"] == {"user_color2": 17}, rd(other)
        """)

    def test_19j_refuses_to_retarget_brave_profile_under_active_snapshot(self):
        self.child("""
            A.apply("librekai", ["brave"])
            other = H / ".config/BraveSoftware/Brave-Origin/Other/Preferences"
            other.parent.mkdir(parents=True)
            A.write(other, json.dumps({"browser": {"theme": {"user_color2": 17}}}))
            try:
                A.apply("dracula", ["brave"], profiles={"brave": str(other)})
                raise AssertionError("expected profile retarget to be refused")
            except SystemExit as e:
                assert "restore before applying to another profile" in str(e), e
            assert rd(other)["browser"]["theme"]["user_color2"] == 17
        """)

    def test_19k_profile_option_requires_target_selection(self):
        self.child("""
            other = H / ".mozilla/firefox/p.other"
            other.mkdir()
            (other / "prefs.js").write_text("// profile marker\\n")
            try:
                A.apply("librekai", ["gtk"], profiles={"firefox": str(other)})
                raise AssertionError("expected unused profile selection to be refused")
            except SystemExit as e:
                assert "requires its target in --only" in str(e), e
            assert not A.SNAPSHOT.exists()
        """)

    def test_21_atomic_writes(self):
        self.child("""
            A.set_brave_theme({"x": 1})
            assert (BRAVE.stat().st_mode & 0o777) == 0o600
            real = H / "real-geany.conf"
            os.replace(A.GEANY_CONF, real)
            A.GEANY_CONF.symlink_to(real)
            A.set_geany("x.conf")
            assert A.GEANY_CONF.is_symlink() and "color_scheme=x.conf" in real.read_text()
            p = H / "f.txt"
            p.write_text("old")
            def boom(*a):
                raise OSError("boom")
            A.os.replace = boom
            try:
                A.atomic_write(p, "new")
                raise AssertionError("no error")
            except OSError:
                pass
            assert p.read_text() == "old" and sorted(x.name for x in H.iterdir() if x.name.startswith(".f.txt")) == []
        """)


# ---------- phone: per-device snapshots (item 4) ----------
PHONE_PRELUDE = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, TOOLS)
import phone_theme as Ph
S = Ph.STATE_DIR
PH, EMU = "adb-XYZ._adb-tls-connect._tcp", "emulator-5554"


def on(transport=None):
    os.environ.pop("ANDROID_SERIAL", None)
    if transport:
        os.environ["ANDROID_SERIAL"] = transport


def setting(t):
    return json.load(open(os.environ["FAKE_ADB"]))["devices"][t]["setting"]
'''


class PhoneTests(unittest.TestCase):
    def setUp(self):
        self.s = Path(tempfile.mkdtemp(prefix="rain-test-phone-"))
        self.h = self.s / "h"
        self.h.mkdir()
        self.bin = bins(self.s / "bin", {"adb": FAKE_ADB, **{n: LOUD for n in ("gsettings", "dconf", "pgrep")}})
        self.db = self.s / "adb.json"

    def tearDown(self):
        shutil.rmtree(self.s, ignore_errors=True)

    def devices(self, **devs):
        self.db.write_text(json.dumps({"devices": devs}))

    def child(self, code, ok=True):
        src = f"TOOLS = {str(TOOLS)!r}\n" + PHONE_PRELUDE + textwrap.dedent(code)
        r = subprocess.run([sys.executable, "-c", src], env=env_for(self.h, self.bin, FAKE_ADB=str(self.db)),
                           capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    orig_phone = '{"android.theme.customization.theme_style":"SPRITZ"}'
    orig_emu = '{"android.theme.customization.theme_style":"VIBRANT"}'

    def test_20a_two_devices_separate_snapshots(self):
        self.devices(**{"emulator-5554": {"serial": "EMU1", "setting": self.orig_emu},
                        "adb-XYZ._adb-tls-connect._tcp": {"serial": "PHONE1", "setting": self.orig_phone}})
        self.child("""
            on(); Ph.apply("librekai", "TONAL_SPOT", False, False)
            on(EMU); Ph.apply("dracula", "VIBRANT", False, False)
            assert json.load(open(S / "phone-snapshot.PHONE1.json")) == {"android.theme.customization.theme_style": "SPRITZ"}
            assert json.load(open(S / "phone-snapshot.EMU1.json")) == {"android.theme.customization.theme_style": "VIBRANT"}
            st = Ph.load_state()
            assert st["PHONE1"]["current"] == "librekai" and st["EMU1"]["current"] == "dracula", st
            assert Ph.summary() == ({"librekai", "dracula"}, "VIBRANT"), Ph.summary()
            on(EMU); Ph.restore(False)
            assert "EMU1" not in Ph.load_state() and "PHONE1" in Ph.load_state()
            assert "VIBRANT" in setting(EMU) and "SPRITZ" not in setting(PH)
        """)

    def legacy(self):
        st = self.h / ".local/state/rain-themes"
        st.mkdir(parents=True)
        (st / "phone-snapshot.json").write_text('{"android.theme.customization.theme_style": "SPRITZ"}\n')
        (st / "phone-state.json").write_text('{"current": "librekai", "style": "TONAL_SPOT"}\n')
        return st

    def test_20b_legacy_not_migrated_to_emulator(self):
        st = self.legacy()
        self.devices(**{"emulator-5554": {"serial": "EMU1", "setting": self.orig_emu}})
        r = self.child("""on(); Ph.apply("dracula", "VIBRANT", False, False)""", ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("predates per-device snapshots", r.stderr)
        self.assertEqual(sorted(p.name for p in st.iterdir()), ["phone-snapshot.json", "phone-state.json"])
        self.assertIn("VIBRANT", json.loads(self.db.read_text())["devices"]["emulator-5554"]["setting"])

    def test_20c_legacy_migrated_to_phone_then_emulator_not_blocked(self):
        st = self.legacy()
        lib = '{"android.theme.customization.system_palette":"F93B7F"}'
        self.devices(**{"emulator-5554": {"serial": "EMU1", "setting": self.orig_emu},
                        "adb-XYZ._adb-tls-connect._tcp": {"serial": "PHONE1", "setting": lib}})
        self.child("""
            on(); Ph.apply("librekai", "TONAL_SPOT", False, False)
            assert not (S / "phone-snapshot.json").exists()
            assert json.load(open(S / "phone-snapshot.PHONE1.json")) == {"android.theme.customization.theme_style": "SPRITZ"}
            assert Ph.load_state() == {"PHONE1": {"current": "librekai", "style": "TONAL_SPOT"}}
            on(EMU); Ph.apply("librekai", "TONAL_SPOT", False, False)
            assert json.load(open(S / "phone-snapshot.EMU1.json")) == {"android.theme.customization.theme_style": "VIBRANT"}
        """)

    def test_20d_phone_already_themed_is_not_snapshotted(self):
        lib = '{"android.theme.customization.system_palette":"f93b7f"}'
        self.devices(**{"adb-XYZ._adb-tls-connect._tcp": {"serial": "PHONE1", "setting": lib}})
        r = self.child("""
            on(); Ph.apply("dracula", "TONAL_SPOT", False, False)
            assert not (S / "phone-snapshot.PHONE1.json").exists()
        """)
        self.assertIn("phone already themed and no snapshot", r.stdout)


# ---------- item 22: check passes, dry-run apply output unchanged ----------
class DryRunTests(unittest.TestCase):
    def test_22a_rain_check(self):
        r = subprocess.run([str(TOOLS / "rain"), "check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(shutil.which("dbus-run-session"), "needs dbus-run-session")
    def test_22b_dry_run_apply_output_only_gains_lines(self):
        s = Path(tempfile.mkdtemp(prefix="rain-test-dry-"))
        try:
            base = subprocess.run(["git", "-C", str(ROOT), "merge-base", "HEAD", "origin/main"],
                                  capture_output=True, text=True, check=True).stdout.strip()
            (s / "tools").mkdir()
            (s / "librekai").symlink_to(ROOT / "librekai")
            h = s / "h"
            h.mkdir()
            make_home(h)
            b = bins(s / "bin", {"pgrep": "#!/bin/sh\nexit 1\n", "adb": LOUD})
            outs = []
            for src in (subprocess.run(["git", "-C", str(ROOT), "show", f"{base}:tools/apply_theme.py"],
                                       capture_output=True, text=True, check=True).stdout,
                        (TOOLS / "apply_theme.py").read_text()):
                (s / "tools/apply_theme.py").write_text(src)
                shutil.rmtree(h / ".local/state", ignore_errors=True)  # the old dry-run mkdirs files/
                r = subprocess.run(["dbus-run-session", "--", sys.executable, str(s / "tools/apply_theme.py"),
                                    "librekai", "--dry-run"], env=env_for(h, b), capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                outs.append(r.stdout.splitlines())
            old, new = outs
            it = iter(new)
            missing = [ln for ln in old if not any(ln == n for n in it)]
            self.assertEqual(missing, [], "\n".join(new))
            self.assertFalse((h / ".local/state").exists())
        finally:
            shutil.rmtree(s, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
