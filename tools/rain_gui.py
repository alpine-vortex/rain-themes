"""Small GTK3 window for rain-themes: pick a palette, apply, preview, restore.

Started by `tools/rain gui` (or the "Rain Themes" menu entry from `rain install`).
All work is done by running `tools/rain ...` as a subprocess, so the GUI adds no
logic of its own; its output is shown in the collapsible Activity pane.
"""
import json
import math
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
from gi.repository import GdkPixbuf, Gio, Gtk, Pango  # noqa: E402

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
RAIN = str(TOOLS / "rain")
sys.path.insert(0, str(TOOLS))
from apply_theme import SNAPSHOT, load_state  # noqa: E402
from phone_theme import STYLES, summary as phone_summary  # noqa: E402

CSS = b"""
list row.palette-row {
  padding: 7px;
  border-radius: 8px;
}
list row.palette-row:selected {
  background: @theme_selected_bg_color;
  color: @theme_selected_fg_color;
}
.badge { font-size: smaller; font-weight: bold; color: @theme_selected_bg_color; }
.dim { opacity: 0.6; }
.log { font-family: monospace; font-size: smaller; }
.detail { padding: 20px; }
.wallpaper-preview { background: @theme_base_color; border-radius: 10px; }
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
    notes = (ROOT / slug / f"{slug}-notes.md").read_text().splitlines()
    contrast = [line.strip("| ") for line in notes if "| FAIL |" in line]
    return {"slug": slug, "name": name, "swatches": swatches, "wallpaper": d / "wallpaper-desktop.png",
            "contrast": contrast}


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


class WallpaperPreview(Gtk.DrawingArea):
    """Paint the selected wallpaper into the space the current window gives us."""

    def __init__(self):
        super().__init__()
        self.pixbuf = None
        self.set_size_request(240, 150)
        self.set_hexpand(True)
        self.get_style_context().add_class("wallpaper-preview")
        self.connect("draw", self.on_draw)

    def do_get_preferred_height_for_width(self, width):
        return 150, max(150, min(420, int(width / 1.6)))

    def set_pixbuf(self, pixbuf):
        self.pixbuf = pixbuf
        self.queue_draw()

    def on_draw(self, _widget, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        if width <= 0 or height <= 0:
            return False
        self.get_style_context().render_background(cr, 0, 0, width, height)
        if self.pixbuf is None:
            return False
        scale = min(width / self.pixbuf.get_width(), height / self.pixbuf.get_height())
        draw_width = self.pixbuf.get_width() * scale
        draw_height = self.pixbuf.get_height() * scale
        x = (width - draw_width) / 2
        y = (height - draw_height) / 2
        cr.save()
        radius = min(10, width / 2, height / 2)
        cr.new_path()
        cr.move_to(radius, 0)
        cr.line_to(width - radius, 0)
        cr.arc(width - radius, radius, radius, -math.pi / 2, 0)
        cr.line_to(width, height - radius)
        cr.arc(width - radius, height - radius, radius, 0, math.pi / 2)
        cr.line_to(radius, height)
        cr.arc(radius, height - radius, radius, math.pi / 2, math.pi)
        cr.line_to(0, radius)
        cr.arc(radius, radius, radius, math.pi, math.pi * 1.5)
        cr.close_path()
        cr.clip()
        cr.translate(x, y)
        cr.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
        cr.paint()
        cr.restore()
        return False


class App(Gtk.Window):
    def __init__(self):
        super().__init__(title="Rain Themes")
        self.set_default_size(1000, 700)
        self.set_size_request(620, 480)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("key-press-event", self.on_key_press)
        self.busy = False
        self.buttons = []
        self.selected_slug = None

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        header = Gtk.HeaderBar(title="Rain Themes", show_close_button=True)
        self.set_titlebar(header)
        self.pending_btn = Gtk.Button()
        self.pending_btn.set_no_show_all(True)
        self.pending_btn.connect("clicked", lambda _b: self.run(["pending"]))
        header.pack_start(self.pending_btn)
        self.buttons.append(self.pending_btn)
        menu = Gtk.MenuButton()
        menu.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        menu.set_tooltip_text("More actions")
        menu_items = Gtk.Menu()
        self.restore_btn = Gtk.MenuItem(label="Restore original desktop…")
        self.restore_btn.get_accessible().set_name("Restore the original desktop settings")
        self.restore_btn.connect("activate", self.on_restore)
        menu_items.append(self.restore_btn)
        menu_items.show_all()
        menu.set_popup(menu_items)
        header.pack_end(menu)
        self.log_toggle = Gtk.ToggleButton(label="Activity")
        self.log_toggle.set_tooltip_text("Show action output")
        self.log_toggle.connect("toggled", self.on_log_toggled)
        header.pack_end(self.log_toggle)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                                  margin_start=16, margin_end=16, margin_top=6, margin_bottom=6)
        self.status_box.set_no_show_all(True)
        self.status_spinner = Gtk.Spinner()
        self.status_box.pack_start(self.status_spinner, False, False, 0)
        self.status_icon = Gtk.Image()
        self.status_box.pack_start(self.status_icon, False, False, 0)
        self.result_label = Gtk.Label(xalign=0, wrap=True)
        self.status_box.pack_start(self.result_label, True, True, 0)
        root.pack_start(self.status_box, False, False, 0)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True, vexpand=True)
        self.main_paned = paned
        self.compact_layout = None
        paned.connect("size-allocate", self.on_main_size_allocate)
        root.pack_start(paned, True, True, 0)
        browser = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
        self.browser = browser
        browser.set_size_request(240, -1)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search palettes")
        self.search.set_tooltip_text("Ctrl+F to focus, Escape to clear")
        self.search.get_accessible().set_name("Search palettes by name")
        self.search.connect("search-changed", self.on_search_changed)
        browser.pack_start(self.search, False, False, 0)
        self.palette_count = Gtk.Label(xalign=0)
        self.palette_count.get_style_context().add_class("dim")
        browser.pack_start(self.palette_count, False, False, 0)
        self.palette_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.palette_list.set_filter_func(self.filter_card)
        self.palette_list.connect("row-selected", self.on_palette_selected)
        palette_scroll = Gtk.ScrolledWindow(vexpand=True, min_content_width=220)
        palette_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        palette_scroll.add(self.palette_list)
        browser.pack_start(palette_scroll, True, True, 0)
        self.rain_only = Gtk.Label(xalign=0, wrap=True)
        self.rain_only.get_style_context().add_class("dim")
        browser.pack_start(self.rain_only, False, False, 0)
        paned.pack1(browser, False, False)

        detail_scroll = Gtk.ScrolledWindow()
        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=22)
        self.detail = detail
        detail.get_style_context().add_class("detail")
        detail_scroll.add(detail)
        paned.pack2(detail_scroll, True, False)
        self.preview_image = WallpaperPreview()
        self.preview_image.get_accessible().set_name("Selected palette wallpaper preview")
        self.preview_cache = {}
        detail.pack_start(self.preview_image, False, True, 0)
        self.swatches = Swatches(["#333333", "#bbbbbb"])
        self.swatches.set_size_request(160, 20)
        self.swatches.set_hexpand(True)
        detail.pack_start(self.swatches, False, True, 0)
        self.detail_title = Gtk.Label(xalign=0)
        self.detail_title.set_use_markup(True)
        self.detail_title.set_line_wrap(True)
        self.detail_title.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        detail.pack_start(self.detail_title, False, False, 0)
        self.detail_status = Gtk.Label(xalign=0, wrap=True)
        self.detail_status.get_style_context().add_class("dim")
        detail.pack_start(self.detail_status, False, False, 0)
        self.contrast_label = Gtk.Label(xalign=0, wrap=True)
        self.contrast_label.get_style_context().add_class("dim")
        detail.pack_start(self.contrast_label, False, False, 0)
        actions = Gtk.Box(spacing=8)
        self.apply_btn = Gtk.Button(label="Apply to desktop")
        self.apply_btn.get_style_context().add_class("suggested-action")
        self.apply_btn.connect("clicked", lambda _b: self.confirm_apply(self.selected_slug))
        self.preview_btn = Gtk.Button(label="Preview")
        self.preview_btn.set_tooltip_text("Open screenshots in temporary windows; this changes nothing")
        self.preview_btn.connect("clicked", lambda _b: self.run(["preview", self.selected_slug])
                                 if self.selected_slug else None)
        actions.pack_start(self.apply_btn, False, False, 0)
        actions.pack_start(self.preview_btn, False, False, 0)
        detail.pack_start(actions, False, False, 0)
        self.buttons += [self.apply_btn, self.preview_btn]

        phone = Gtk.Expander(label="Phone")
        phone_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=10)
        phone.add(phone_box)
        phone_box.pack_start(Gtk.Label(label="Set the phone's Material You colours and copy theme files over ADB.",
                                       xalign=0, wrap=True), False, False, 0)
        phone_row = Gtk.Box(spacing=8)
        phone_row.pack_start(Gtk.Label(label="Colour style", xalign=0), False, False, 0)
        self.style = Gtk.ComboBoxText()
        for style in STYLES:
            self.style.append(style, style.replace("_", " ").title())
        self.style.set_active_id(phone_summary()[1] or "TONAL_SPOT")
        self.style.set_tooltip_text("Material You style used for phone colours")
        self.style.get_accessible().set_name("Phone Material You colour style")
        phone_row.pack_start(self.style, False, False, 0)
        phone_box.pack_start(phone_row, False, False, 0)
        phone_actions = Gtk.Box(spacing=8)
        self.phone_apply_btn = Gtk.Button(label="Apply to phone")
        self.phone_apply_btn.connect("clicked", lambda _b: self.confirm_phone(self.selected_slug))
        phone_actions.pack_start(self.phone_apply_btn, False, False, 0)
        self.phone_restore_btn = Gtk.Button(label="Restore phone")
        self.phone_restore_btn.connect("clicked", self.on_phone_restore)
        phone_actions.pack_start(self.phone_restore_btn, False, False, 0)
        phone_box.pack_start(phone_actions, False, False, 0)
        detail.pack_start(phone, False, False, 0)
        self.buttons += [self.style, self.phone_apply_btn, self.phone_restore_btn]

        self.log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True,
                                wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=8, top_margin=6)
        self.log.get_style_context().add_class("log")
        log_scroll = Gtk.ScrolledWindow(min_content_height=130)
        log_scroll.add(self.log)
        self.log_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
                                         transition_duration=120)
        self.log_revealer.add(log_scroll)
        root.pack_end(self.log_revealer, False, True, 0)

        self.populate()
        self.refresh()
        self.say("Desktop changes apply immediately. Apps that are open may need Finish pending or a restart.\n")

    def populate(self):
        slugs = sorted(p.parent.parent.name for p in ROOT.glob("*/desktop/colloid.json"))
        self.cards = {}
        for slug in slugs:
            info = palette_info(slug)
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("palette-row")
            row._rain_slug = slug
            row._rain_name = info["name"]
            row.set_activatable(True)
            row.get_accessible().set_name(info["name"])
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            title = Gtk.Label(xalign=0)
            title.set_markup(f"<b>{GLib.markup_escape_text(info['name'])}</b>")
            title.set_ellipsize(Pango.EllipsizeMode.END)
            content.pack_start(title, False, False, 0)
            swatch = Swatches(info["swatches"])
            swatch.set_size_request(170, 12)
            swatch.get_accessible().set_name(f"{info['name']} color swatches")
            content.pack_start(swatch, False, False, 0)
            card.pack_start(content, True, True, 0)
            applied = Gtk.Label(label="●")
            applied.get_style_context().add_class("badge")
            applied.set_tooltip_text("Applied to desktop")
            on_phone = Gtk.Label(label="●")
            on_phone.get_style_context().add_class("dim")
            on_phone.set_tooltip_text("Saved on phone")
            card.pack_end(on_phone, False, False, 0)
            card.pack_end(applied, False, False, 0)
            row.add(card)
            self.cards[slug] = (row, applied, on_phone, info)
            self.palette_list.add(row)
        others = sorted(p.parent.name for p in ROOT.glob("*/theme.spec.json")
                        if not (p.parent / "desktop").exists())
        self.rain_only.set_text("Rain only: " + ", ".join(others) if others else "")
        self.palette_count.set_text(f"{len(slugs)} palettes")
        self.show_all()
        current = load_state().get("current")
        children = self.palette_list.get_children()
        selected = next((row for row in children if row._rain_slug == current), None)
        if selected is None and children:
            selected = children[0]
        if selected:
            self.palette_list.select_row(selected)

    def refresh(self):
        state = load_state()
        current = state.get("current")
        phone = phone_summary()[0]
        for slug, (_row, applied, on_phone, _info) in self.cards.items():
            applied.set_visible(slug == current)
            on_phone.set_visible(slug in phone)
        pending = state.get("pending", {})
        self.pending_btn.set_label(f"Finish pending ({len(pending)})")
        self.pending_btn.set_visible(bool(pending))
        self.pending_btn.set_tooltip_text("\n".join(f"{k}: {v}" for k, v in pending.items())
                                          or "No apps are waiting for a change")
        self.pending_btn.set_sensitive(bool(pending) and not self.busy)
        self.restore_btn.set_sensitive(SNAPSHOT.exists() and not self.busy)
        self.update_palette_count()
        if self.selected_slug:
            self.show_selection(self.selected_slug)

    def filter_card(self, child, _data=None):
        query = self.search.get_text().strip().casefold()
        return not query or query in child._rain_name.casefold() or query in child._rain_slug.casefold()

    def on_search_changed(self, _entry):
        self.palette_list.invalidate_filter()
        self.update_palette_count()
        visible = [row for row in self.palette_list.get_children() if row.get_child_visible()]
        selected = self.palette_list.get_selected_row()
        if not selected or selected not in visible:
            self.palette_list.unselect_all()
            if visible:
                self.palette_list.select_row(visible[0])
            else:
                self.show_empty_detail()

    def update_palette_count(self):
        query = self.search.get_text().strip()
        if not query:
            self.palette_count.set_text(f"{len(self.cards)} palettes")
            return
        visible_count = sum(row.get_child_visible() for row in self.palette_list.get_children())
        self.palette_count.set_text(f"{visible_count} of {len(self.cards)} palettes")

    def on_main_size_allocate(self, paned, allocation):
        if allocation.width <= 1:
            return
        compact = allocation.width < 760
        if compact == self.compact_layout:
            return
        self.compact_layout = compact
        if compact:
            paned.set_orientation(Gtk.Orientation.VERTICAL)
            self.browser.set_size_request(-1, 185)
            GLib.idle_add(self.set_main_position, 190)
        else:
            paned.set_orientation(Gtk.Orientation.HORIZONTAL)
            self.browser.set_size_request(240, -1)
            GLib.idle_add(self.set_main_position, 260)

    def set_main_position(self, position):
        self.main_paned.set_position(position)
        return GLib.SOURCE_REMOVE

    def on_key_press(self, _window, event):
        control = event.state & Gdk.ModifierType.CONTROL_MASK
        if control and event.keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.search.grab_focus()
            return True
        if event.keyval == Gdk.KEY_Escape and self.search.get_text():
            self.search.set_text("")
            self.search.grab_focus()
            return True
        return False

    def on_palette_selected(self, _listbox, row):
        if row:
            self.show_selection(row._rain_slug)

    def show_selection(self, slug):
        if slug not in self.cards:
            return
        self.selected_slug = slug
        _row, applied, on_phone, info = self.cards[slug]
        self.swatches.set_visible(True)
        try:
            pixbuf = self.preview_cache.get(slug)
            if pixbuf is None:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(info["wallpaper"]), 1200, 750, True)
                self.preview_cache[slug] = pixbuf
                if len(self.preview_cache) > 3:
                    self.preview_cache.pop(next(iter(self.preview_cache)))
            self.preview_image.set_pixbuf(pixbuf)
        except GLib.Error:
            self.preview_image.set_pixbuf(None)
        self.swatches.colours = info["swatches"]
        self.swatches.get_accessible().set_name(f"{info['name']} color palette")
        self.swatches.queue_draw()
        self.detail_title.set_markup(f"<span size='xx-large' weight='bold'>{GLib.markup_escape_text(info['name'])}</span>")
        self.detail_status.set_text(f"{'Applied to desktop' if applied.get_visible() else 'Not currently applied'}  ·  "
                                    f"{'Saved on phone' if on_phone.get_visible() else 'Not recorded on phone'}")
        self.apply_btn.set_label("Re-apply to desktop" if applied.get_visible() else "Apply to desktop")
        self.contrast_label.set_text(f"{len(info['contrast'])} contrast pairs below target" if info["contrast"] else "")
        self.contrast_label.set_tooltip_text("\n".join(info["contrast"]))
        for button in (self.apply_btn, self.preview_btn, self.phone_apply_btn):
            button.set_sensitive(not self.busy)

    def show_empty_detail(self):
        self.selected_slug = None
        self.preview_image.set_pixbuf(None)
        self.swatches.set_visible(False)
        self.detail_title.set_markup("<span size='xx-large' weight='bold'>No matching palettes</span>")
        self.detail_status.set_text("Try another name or clear the search to browse all palettes.")
        self.contrast_label.set_text("")
        self.contrast_label.set_tooltip_text(None)
        for button in (self.apply_btn, self.preview_btn, self.phone_apply_btn):
            button.set_sensitive(False)

    def on_log_toggled(self, button):
        self.log_revealer.set_reveal_child(button.get_active())

    def confirm(self, title, detail):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL, text=title)
        dialog.format_secondary_text(detail)
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        return accepted

    def confirm_apply(self, slug):
        if not slug:
            return
        detail = ("Rain will apply this palette to the desktop targets available on this computer. "
                  "Some changes may wait until an app is restarted or pending work is finished.")
        if self.confirm(f"Apply {self.cards[slug][3]['name']} to the desktop?", detail):
            self.run(["apply", slug])

    def confirm_phone(self, slug):
        if not slug:
            return
        detail = ("This changes the phone's system color seed and copies theme files to Downloads. "
                  "Wallpaper and app imports remain manual. The selected Material You style will be used.")
        if self.confirm(f"Apply {self.cards[slug][3]['name']} to the phone?", detail):
            self.run(["phone", slug, "--style", self.style.get_active_id()])

    def say(self, text):
        buffer = self.log.get_buffer()
        buffer.insert(buffer.get_end_iter(), text)
        self.log.scroll_to_iter(buffer.get_end_iter(), 0, False, 0, 0)

    def on_restore(self, _item):
        detail = ("Rain will restore the desktop targets it changed to their previous values. "
                  "Changes made since applying Rain are left alone where possible.")
        if self.confirm("Restore the original desktop?", detail):
            self.run(["restore"])

    def on_phone_restore(self, _button):
        detail = ("The connected phone goes back to the colour setting it had before Rain first themed it. "
                  "Wallpaper and app themes are left as they are.")
        if self.confirm("Restore the phone's system colours?", detail):
            self.run(["phone", "--restore"])

    def set_busy(self, busy):
        self.busy = busy
        for button in self.buttons:
            button.set_sensitive(not busy)
        self.restore_btn.set_sensitive(SNAPSHOT.exists() and not busy)
        if busy:
            self.log_toggle.set_active(True)
        else:
            self.refresh()

    def run(self, args):
        if self.busy:
            return
        self.set_busy(True)
        self.active_action = self.describe_action(args)
        self.result_label.set_text(self.active_action + "…")
        self.result_label.show()
        self.status_icon.clear()
        self.status_icon.hide()
        self.status_spinner.show()
        self.status_spinner.start()
        self.status_box.set_visible(True)
        self.say(f"\n$ rain {' '.join(args)}\n")
        process = Gio.Subprocess.new([RAIN] + args, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        stream = Gio.DataInputStream.new(process.get_stdout_pipe())

        def on_line(source, result):
            line, _length = source.read_line_finish_utf8(result)
            if line is None:
                process.wait_async(None, on_exit)
                return
            self.say(line + "\n")
            source.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line)

        def on_exit(proc, result):
            proc.wait_finish(result)
            ok = proc.get_successful()
            self.say("done\n" if ok else f"failed (exit {proc.get_exit_status()})\n")
            self.status_spinner.stop()
            self.status_spinner.hide()
            self.status_icon.set_from_icon_name("emblem-ok-symbolic" if ok else "dialog-error-symbolic",
                                                Gtk.IconSize.MENU)
            self.status_icon.show()
            self.result_label.set_text(f"{self.active_action} complete. Review Activity for skipped targets." if ok
                                       else f"{self.active_action} failed (exit {proc.get_exit_status()}). "
                                            "Review Activity for details.")
            self.set_busy(False)

        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, on_line)

    def describe_action(self, args):
        command = args[0]
        if command == "apply" and len(args) > 1:
            return f"Applying {self.cards[args[1]][3]['name']} to the desktop"
        if command == "preview" and len(args) > 1:
            return f"Preparing the {self.cards[args[1]][3]['name']} preview"
        if command == "phone" and len(args) > 1 and args[1] != "--restore":
            return f"Applying {self.cards[args[1]][3]['name']} to the phone"
        if command == "phone":
            return "Restoring the phone's system colours"
        if command == "restore":
            return "Restoring the original desktop settings"
        if command == "pending":
            return "Finishing pending app changes"
        return f"Running rain {command}"


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
