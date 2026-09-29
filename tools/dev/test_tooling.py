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
           if not k.startswith(("GIT_", "ANDROID_", "XDG_", "DBUS_")) and k not in ("DISPLAY", "WAYLAND_DISPLAY")}
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
        cls.git(tpl, "add", "-A", "tools")
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
     "org.cinnamon.desktop.background picture-uri": "'file:///orig.png'"}
D = {B + ":orig/visible-name": "'Default'"}
RUNNING = set()


def run(*cmd, check=True):
    op = cmd[1]
    if cmd[0] == "gsettings":
        k = f"{cmd[2]} {cmd[3]}"
        if op == "get":
            return G[k]
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
BRAVE = A.BRAVE_PREFS
ORIG_BRAVE = {"user_color2": -14244198, "color_scheme2": 1}


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
    brave.write_text(json.dumps({"browser": {"theme": {"user_color2": -14244198, "color_scheme2": 1}}}))
    brave.chmod(0o600)
    (h / ".config/vesktop/settings").mkdir(parents=True)
    (h / ".config/vesktop/themes").mkdir()
    (h / ".config/vesktop/settings/settings.json").write_text('{"enabledThemes": []}')
    if gtk4_assets:
        (h / ".config/gtk-4.0/assets").mkdir(parents=True)
        (h / ".config/gtk-4.0/assets/a.png").write_text("orig")


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.s = Path(tempfile.mkdtemp(prefix="rain-test-desk-"))
        self.h = self.s / "h"
        self.h.mkdir()
        self.bin = bins(self.s / "bin", {n: LOUD for n in ("gsettings", "dconf", "pgrep", "adb")})

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
            del snap["brave_theme"], snap["geany_color_scheme"]
            A.write(A.SNAPSHOT, json.dumps(snap))
            A.apply_brave("librekai", A.ROOT / "librekai/desktop")
            A.apply("librekai", ["gtk"])
            snap = rd(A.SNAPSHOT)
            assert "brave_theme" not in snap and snap["geany_color_scheme"] == "mine.conf", snap
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
