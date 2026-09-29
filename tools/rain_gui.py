"""Small GTK3 window for rain-themes: pick a palette, apply, preview, restore.

Started by `tools/rain gui` (or the "Rain Themes" menu entry from `rain install`).
All work is done by running `tools/rain ...` as a subprocess, so the GUI adds no
logic of its own; its output is shown in the log pane.
"""
import json
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GLib  # noqa: E402

# WM_CLASS must be rain-themes (= StartupWMClass in rain-themes.desktop) or Cinnamon can't
# pin the window; GTK fixes the class when it initialises, so set it before importing Gtk.
GLib.set_prgname("rain-themes")
GLib.set_application_name("Rain Themes")
from gi.repository import Gdk  # noqa: E402

Gdk.set_program_class("rain-themes")
from gi.repository import GdkPixbuf, Gio, Gtk  # noqa: E402

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
RAIN = str(TOOLS / "rain")
sys.path.insert(0, str(TOOLS))
from apply_theme import load_state  # noqa: E402
from phone_theme import STYLES, summary as phone_summary  # noqa: E402

CSS = b"""
.card { padding: 10px; border-radius: 10px; }
.card-current { box-shadow: inset 0 0 0 2px @theme_selected_bg_color; }
.badge { font-size: smaller; font-weight: bold; color: @theme_selected_bg_color; }
.dim { opacity: 0.6; }
.log { font-family: monospace; font-size: smaller; }
"""


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def palette_info(slug):
    d = ROOT / slug / "desktop"
    term = json.loads((d / "gnome-terminal.json").read_text())
    seed = json.loads((d / "brave.json").read_text())["seed"]
    name = json.loads((d / "colloid.json").read_text())["name"]
    p = term["palette"]
    swatches = [term["background-color"], term["foreground-color"], seed] + p[9:15]
    return {"slug": slug, "name": name, "swatches": swatches, "wallpaper": d / "wallpaper-desktop.png"}


class Swatches(Gtk.DrawingArea):
    def __init__(self, colours):
        super().__init__()
        self.colours = colours
        self.set_size_request(240, 18)
        self.connect("draw", self.on_draw)

    def on_draw(self, _w, cr):
        w = self.get_allocated_width() / len(self.colours)
        h = self.get_allocated_height()
        for i, c in enumerate(self.colours):
            cr.set_source_rgb(*hex_rgb(c))
            cr.rectangle(i * w, 0, w + 0.5, h)
            cr.fill()


class App(Gtk.Window):
    def __init__(self):
        super().__init__(title="Rain Themes")
        self.set_default_size(820, 640)
        self.busy = False
        self.buttons = []

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        hb = Gtk.HeaderBar(title="Rain Themes", show_close_button=True)
        self.set_titlebar(hb)
        self.restore_btn = Gtk.Button(label="Restore original")
        self.restore_btn.set_tooltip_text("Put back what the last apply changed, as it was before Rain themed it")
        self.restore_btn.connect("clicked", self.on_restore)
        hb.pack_start(self.restore_btn)
        self.pending_btn = Gtk.Button()
        self.pending_btn.connect("clicked", lambda _b: self.run(["pending"]))
        hb.pack_end(self.pending_btn)
        self.buttons += [self.restore_btn, self.pending_btn]

        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.add(paned)

        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.add(top)
        paned.pack1(scroll, True, False)

        # phone row: style for the cards' Phone buttons, and phone restore
        prow = Gtk.Box(spacing=8)
        plabel = Gtk.Label(label="Phone (adb):", xalign=0)
        plabel.get_style_context().add_class("dim")
        prow.pack_start(plabel, False, False, 0)
        self.style = Gtk.ComboBoxText()
        for st in STYLES:
            self.style.append(st, st.replace("_", " ").title())
        self.style.set_active_id(phone_summary()[1] or "TONAL_SPOT")
        self.style.set_tooltip_text("Material You style used by the Phone buttons. Vibrant stays closest "
                                    "to the accent")
        prow.pack_start(self.style, False, False, 0)
        self.phone_restore_btn = Gtk.Button(label="Restore phone")
        self.phone_restore_btn.set_tooltip_text("Put the phone's system colours back as they were")
        self.phone_restore_btn.connect("clicked", self.on_phone_restore)
        prow.pack_start(self.phone_restore_btn, False, False, 0)
        top.pack_start(prow, False, False, 0)
        self.buttons += [self.style, self.phone_restore_btn]

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=12, row_spacing=12,
                                homogeneous=True, min_children_per_line=2, max_children_per_line=4)
        top.pack_start(self.flow, False, False, 0)
        self.rain_only = Gtk.Label(xalign=0, wrap=True)
        self.rain_only.get_style_context().add_class("dim")
        top.pack_start(self.rain_only, False, False, 0)

        self.log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=8, top_margin=6)
        self.log.get_style_context().add_class("log")
        ls = Gtk.ScrolledWindow(min_content_height=150)
        ls.add(self.log)
        paned.pack2(ls, False, True)

        self.populate()
        self.refresh()
        self.say("Apply switches the desktop immediately. Geany and Brave are queued while open and "
                 "finished by “Finish pending” or at the next login.\n")

    # ----- content -----
    def populate(self):
        slugs = sorted(p.parent.parent.name for p in ROOT.glob("*/desktop/colloid.json"))
        self.cards = {}
        for slug in slugs:
            info = palette_info(slug)
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.get_style_context().add_class("card")
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(info["wallpaper"]), 240, 150, False)
                card.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
            except GLib.Error:
                pass
            card.pack_start(Swatches(info["swatches"]), False, False, 0)
            row = Gtk.Box(spacing=6)
            title = Gtk.Label(xalign=0)
            title.set_markup(f"<b>{GLib.markup_escape_text(info['name'])}</b>")
            row.pack_start(title, True, True, 0)
            badge = Gtk.Label(label="applied")
            badge.get_style_context().add_class("badge")
            row.pack_end(badge, False, False, 0)
            pbadge = Gtk.Label(label="phone")
            pbadge.get_style_context().add_class("badge")
            row.pack_end(pbadge, False, False, 0)
            card.pack_start(row, False, False, 0)
            btns = Gtk.Box(spacing=6)
            ap = Gtk.Button(label="Apply")
            ap.get_style_context().add_class("suggested-action")
            ap.connect("clicked", lambda _b, s=slug: self.run(["apply", s]))
            pv = Gtk.Button(label="Preview")
            pv.set_tooltip_text("Screenshots in throwaway windows; changes nothing")
            pv.connect("clicked", lambda _b, s=slug: self.run(["preview", s]))
            ph = Gtk.Button(label="Phone")
            ph.set_tooltip_text("Android over adb: system colours from this accent, plus wallpaper, "
                                "Sync and redeye files in Download/rain-themes")
            ph.connect("clicked", lambda _b, s=slug: self.run(["phone", s, "--style", self.style.get_active_id()]))
            btns.pack_start(ap, True, True, 0)
            btns.pack_start(pv, True, True, 0)
            btns.pack_start(ph, True, True, 0)
            card.pack_start(btns, False, False, 0)
            self.buttons += [ap, pv, ph]
            self.cards[slug] = (card, badge, ap, pbadge)
            self.flow.add(card)
        others = sorted(p.parent.name for p in ROOT.glob("*/theme.spec.json")
                        if not (p.parent / "desktop").exists())
        self.rain_only.set_text("Rain only for now (no desktop exports yet): " + ", ".join(others) if others else "")
        self.show_all()

    def refresh(self):
        st = load_state()
        cur = st.get("current")
        phone = phone_summary()[0]
        for slug, (card, badge, ap, pbadge) in self.cards.items():
            ap.set_label("Re-apply" if slug == cur else "Apply")
            ctx = card.get_style_context()
            (ctx.add_class if slug == cur else ctx.remove_class)("card-current")
            badge.set_visible(slug == cur)
            pbadge.set_visible(slug in phone)
        pending = st.get("pending", {})
        self.pending_btn.set_label(f"Finish pending ({len(pending)})" if pending else "Nothing pending")
        self.pending_btn.set_tooltip_text(
            "\n".join(f"{k}: {v}" for k, v in pending.items()) or "No apps are waiting for a change")
        self.pending_btn.set_sensitive(bool(pending) and not self.busy)

    # ----- actions -----
    def say(self, text):
        buf = self.log.get_buffer()
        buf.insert(buf.get_end_iter(), text)
        self.log.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)

    def on_restore(self, _b):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.OK_CANCEL,
                              text="Restore the original desktop?")
        d.format_secondary_text("Themes, wallpaper, terminal profile, Firefox, Geany, Brave and Vesktop go back "
                                "to how they were before Rain themed them. Anything you changed "
                                "since is left alone.")
        if d.run() == Gtk.ResponseType.OK:
            self.run(["restore"])
        d.destroy()

    def on_phone_restore(self, _b):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.OK_CANCEL,
                              text="Restore the phone's system colours?")
        d.format_secondary_text("The connected phone goes back to the colour setting it had before Rain "
                                "first themed it. Wallpaper and app themes are left as they are.")
        if d.run() == Gtk.ResponseType.OK:
            self.run(["phone", "--restore"])
        d.destroy()

    def set_busy(self, busy):
        self.busy = busy
        for b in self.buttons:
            b.set_sensitive(not busy)
        if not busy:
            self.refresh()

    def run(self, args):
        if self.busy:
            return
        self.set_busy(True)
        self.say(f"\n$ rain {' '.join(args)}\n")
        proc = Gio.Subprocess.new([RAIN] + args, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        stream = Gio.DataInputStream.new(proc.get_stdout_pipe())

        def on_line(s, res):
            line, _ = s.read_line_finish_utf8(res)
            if line is None:
                proc.wait_async(None, on_exit)
                return
            self.say(line + "\n")
            s.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line)

        def on_exit(p, res):
            p.wait_finish(res)
            ok = p.get_successful()
            self.say("done\n" if ok else f"failed (exit {p.get_exit_status()})\n")
            self.set_busy(False)

        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line)


def set_app_icon():
    """Window/Alt-Tab icon straight from assets/icon, so it works before `rain install`."""
    pbs = []
    for png in sorted((ROOT / "assets/icon").glob("rain-themes-[0-9]*.png")):
        try:
            pbs.append(GdkPixbuf.Pixbuf.new_from_file(str(png)))
        except GLib.Error:
            pass
    if pbs:
        Gtk.Window.set_default_icon_list(pbs)
    else:
        Gtk.Window.set_default_icon_name("rain-themes")


def main():
    set_app_icon()
    win = App()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    win.refresh()
    Gtk.main()


if __name__ == "__main__":
    main()
