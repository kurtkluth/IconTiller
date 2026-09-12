"""Pointer feedback and navigation for local draft dragging; no phone access."""
import tkinter as tk
import time
from editor import is_folder, title


def edge_step(x, y, left, top, width, height):
    if width <= 0 or height < 100 or not left <= x <= left + width: return 0
    if top - 24 <= y < top + 48: return -1 if y > top + 24 else -2
    if top + height - 48 < y <= top + height + 24: return 1 if y < top + height - 24 else 2
    return 0


class DragFeedback:
    def __init__(self, app):
        self.app = app
        self.ghost = self.label = self.highlight = None
        self.timer = None
        self.active = False
        self.nav_hover = None
        self.nav_since = 0
        self.nav_jumped = False
        self.saved_status = ''
        self.insert_line = None

    def begin(self):
        self.reset()
        self.saved_status = self.app.status.get()

    def motion(self, event):
        app = self.app
        if not app.drag or app.busy: return
        path, index, x, y = app.drag
        if not self.active and abs(event.x_root-x) + abs(event.y_root-y) < 8: return
        if not self.active:
            self.active = True
            self.ghost = tk.Toplevel(app.root)
            self.ghost.overrideredirect(True)
            self.ghost.attributes('-topmost', True)
            self.ghost.attributes('-alpha', 0.92)
            self.ghost.configure(bg='#63d8bc', takefocus=False)
            name = title(app.draft.container(path)[index])
            photo = app.artwork(app.draft.container(path)[index])
            self.label = tk.Label(self.ghost, text=f'{name}\nDrag onto an app • Esc cancels',
                                  bg='#1c2940', fg='#edf3ff', padx=14, pady=10,
                                  font=('Segoe UI', 10, 'bold'), wraplength=210,
                                  image=photo or '', compound='top')
            self.label.artwork = photo
            self.label.pack(padx=2, pady=2)
            app.root.configure(cursor='hand2')
        self.update_pointer(event.x_root, event.y_root)
        if self.timer is None: self.timer = app.root.after(35, self.tick)

    def target_at(self, x, y):
        widget = self.app.root.winfo_containing(x, y)
        while widget and widget not in self.app.targets and widget not in self.app.page_links:
            widget = widget.master
        return widget

    def valid_target(self, widget):
        app = self.app
        if not app.drag or widget not in app.targets: return False
        source, index, _, _ = app.drag
        target, position = app.targets[widget]
        if app.swap_mode.get():
            if position is None or source[0] == 0 or target[0] == 0: return False
            if source == target and index == position: return False
            for path, slot in ((source, index), (target, position)):
                item = app.draft.container(path)[slot]
                if not isinstance(item, dict) or is_folder(item) or not item.get('bundleIdentifier'): return False
            return True
        if len(source) != 1 or len(target) != 1 or source[0] == 0 or target[0] == 0: return False
        item = app.draft.container(source)[index]
        return isinstance(item,dict) and not is_folder(item) and bool(item.get('bundleIdentifier'))

    def update_pointer(self, x, y):
        if self.ghost:
            self.ghost.geometry(f'+{max(0, x+18)}+{max(0, y+18)}')
        widget = self.target_at(x, y)
        page = self.app.page_links.get(widget)
        if widget in self.app.page_links:
            if self.nav_hover != page:
                self.nav_hover, self.nav_since, self.nav_jumped = page, time.monotonic(), False
            self.app.status.set(f'Hold here to show {"Dock" if page == 0 else f"page {page}"} without releasing the app.')
        else:
            self.nav_hover, self.nav_jumped = None, False
        highlight = self.app.tile_frames.get(widget) if self.valid_target(widget) else None
        if highlight != self.highlight:
            self.clear_highlight()
            if highlight:
                highlight.configure(highlightbackground='#ffd27d', highlightthickness=2)
                self.highlight = highlight
        if highlight:
            path, index = self.app.targets[widget]
            after = False if self.app.swap_mode.get() else self.app.insertion_position(widget,x) > index
            action = 'Swap with' if self.app.swap_mode.get() else ('Insert after' if after else 'Insert before')
            if not self.app.swap_mode.get():
                if self.insert_line is None: self.insert_line = tk.Frame(highlight, bg='#ffd27d', width=4)
                self.insert_line.place(relx=1 if after else 0, rely=0, relheight=1, anchor='ne' if after else 'nw')
            self.app.status.set(f'{action} {title(self.app.draft.container(path)[index])} • Release to edit the draft • Esc cancels')
        elif widget not in self.app.page_links:
            self.app.status.set('Keep holding: drag to a page number to jump, or the top/bottom edge to scroll. Esc cancels.')

    def tick(self):
        self.timer = None
        if not self.active or not self.app.drag: return
        x, y = self.app.root.winfo_pointerxy()
        self.update_pointer(x, y)
        if self.nav_hover is not None and not self.nav_jumped and time.monotonic() - self.nav_since >= 0.5:
            self.app.jump_page(self.nav_hover)
            self.nav_jumped = True
        canvas = self.app.canvas
        step = edge_step(x, y, canvas.winfo_rootx(), canvas.winfo_rooty(), canvas.winfo_width(), canvas.winfo_height())
        if step and self.nav_hover is None:
            canvas.yview_scroll(step, 'units')
        self.timer = self.app.root.after(35, self.tick)

    def clear_highlight(self):
        if self.insert_line is not None:
            self.insert_line.destroy()
            self.insert_line = None
        if self.highlight and self.highlight.winfo_exists():
            self.highlight.configure(highlightbackground='#1c2940')
        self.highlight = None

    def reset(self):
        if self.timer is not None:
            self.app.root.after_cancel(self.timer)
            self.timer = None
        self.clear_highlight()
        if self.ghost:
            self.ghost.destroy()
            self.ghost = self.label = None
        self.active = False
        self.nav_hover, self.nav_jumped = None, False
        self.app.root.configure(cursor='')

    def cancel(self, event=None):
        was_dragging = self.app.drag is not None
        self.app.drag = None
        self.reset()
        if was_dragging: self.app.status.set(self.saved_status or 'Drag cancelled. No changes made.')
