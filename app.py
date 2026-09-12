from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
from io import BytesIO
from queue import Queue, Empty
from threading import Event
from PIL import Image, ImageTk
from icons import icon_key, tile_image, load_icons
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font as tkfont
from device import Snapshot, capture, load_snapshot, save_snapshot, WRITE_BLOCK_REASON
from editor import Draft, is_folder, title
from sync import backup_directory
from safe_swap import validate_edit, describe_edit, prepare_swap_sync, apply_swap_sync
from drag_ui import DragFeedback
from window_state import WindowState

BG, CARD, TEXT, MUTED, ACCENT = '#101827', '#1c2940', '#edf3ff', '#a6b8d0', '#63d8bc'

class App:
    def __init__(self, root):
        self.root, self.draft, self.selected = root, None, None
        self.drag, self.targets, self.folder_windows = None, {}, []
        self.tile_frames, self.page_links, self.page_cards = {}, {}, {}
        self.drag_feedback = DragFeedback(self)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.icon_data = {}
        self.icon_device = None
        self.icon_stop = Event()
        self.icon_poll = None
        self.blank_icon = ImageTk.PhotoImage(Image.new("RGBA", (64, 64)), master=root)
        self.busy, self.columns = False, 3
        self.task_mode = 'read'
        self.last_result = None
        self.write_problem = False
        self.swap_mode = tk.BooleanVar(value=False)
        root.title('IconTiller - App Layout Editor')
        artwork = Path(__file__).resolve().parent / 'assets'
        with Image.open(artwork / 'icontiller.png') as icon:
            self.application_icons = [ImageTk.PhotoImage(
                icon.resize((size, size), Image.Resampling.LANCZOS), master=root)
                for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
        # Supply actual small/large images; iconbitmap would override these on Windows.
        root.iconphoto(True, *self.application_icons)
        root.geometry('1280x850')
        root.minsize(850, 600)
        root.configure(bg=BG)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=(12, 8), font=('Segoe UI', 10))
        header = tk.Frame(root, bg=BG)
        header.pack(fill='x', padx=28, pady=(22, 12))
        tk.Label(header, text='IconTiller', bg=BG, fg=TEXT, font=('Segoe UI', 26, 'bold')).pack(anchor='w')
        tk.Label(header, text='Arrange your apps. Keep your data local.', bg=BG, fg=MUTED, font=('Segoe UI', 11)).pack(anchor='w')
        bar = tk.Frame(root, bg=BG)
        bar.pack(fill='x', padx=28)
        self.buttons = {}
        for column, (label, command) in enumerate([('Read iPhone', self.read), ('Open layout', self.open), ('Save draft', self.backup), ('Undo', self.undo), ('Redo', self.redo), ('Add page', self.add_page), ('Demo', self.demo)]):
            button = ttk.Button(bar, text=label, command=command)
            button.grid(row=0, column=column, sticky='w', padx=(0, 7))
            self.buttons[label] = button
        syncbar = tk.Frame(bar, bg=BG)
        syncbar.grid(row=1, column=0, columnspan=5, sticky='w', pady=(8, 0))
        for label, command in [('Apply to iPhone…', self.prepare_apply), ('Restore previous layout…', self.restore_previous)]:
            self.buttons[label] = ttk.Button(syncbar, text=label, command=command)
            self.buttons[label].pack(side='left', padx=(0, 7))
        tk.Label(syncbar, text='Review and apply your arrangement', bg=BG, fg='#ffce85').pack(side='left', padx=10)
        self.buttons['Find app'] = ttk.Button(bar, text='Find app…', command=self.find_dialog)
        self.buttons['Find app'].grid(row=1, column=5, sticky='w', pady=(8, 0))
        self.buttons['About'] = ttk.Button(bar, text='About…', command=self.about)
        self.buttons['About'].grid(row=1, column=6, sticky='w', pady=(8, 0))
        self.status = tk.StringVar(value='Open a saved layout or read your connected iPhone to begin.')
        tk.Label(root, textvariable=self.status, bg=BG, fg=ACCENT, anchor='w', wraplength=1150, font=('Segoe UI', 11)).pack(fill='x', padx=28, pady=(14, 5))
        tk.Label(root, text='Drag between icons to insert and shift. Hold over a page number to jump. Esc cancels.', bg=BG, fg=MUTED, anchor='w').pack(fill='x', padx=28, pady=(0, 8))
        self.page_nav = tk.Frame(root, bg=BG)
        self.page_nav.pack(fill='x', padx=28, pady=(0, 8))
        wrap = tk.Frame(root, bg=BG)
        wrap.pack(fill='both', expand=True, padx=20)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, yscrollincrement=12)
        scrollbar = ttk.Scrollbar(wrap, orient='vertical', command=self.canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.pages = tk.Frame(self.canvas, bg=BG)
        self.window = self.canvas.create_window(0, 0, window=self.pages, anchor='nw')
        self.pages.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self.resize)
        root.bind_all('<MouseWheel>', self.scroll)
        root.bind_all('<ButtonRelease-1>', self.drop, add='+')
        root.bind_all('<B1-Motion>', self.drag_feedback.motion, add='+')
        root.bind_all('<Escape>', self.drag_feedback.cancel, add='+')
        root.bind('<Control-z>', lambda e: self.undo())
        root.bind('<Control-y>', lambda e: self.redo())
        root.bind('<Control-s>', lambda e: self.backup())
        root.bind('<Control-f>', lambda e: self.find_dialog())
        bottom = tk.Frame(root, bg=BG)
        bottom.pack(fill='x', padx=28, pady=14)
        self.selection = tk.StringVar(value='Select an app or folder')
        selection_label = tk.Label(bottom, textvariable=self.selection, bg=BG, fg=TEXT,
                                   font=('Segoe UI', 12), width=24, wraplength=240, anchor='w', justify='left')
        selection_label.grid(row=0, column=0, sticky='w', padx=(0, 12))
        actions = tk.Frame(bottom, bg=BG)
        actions.grid(row=0, column=1, sticky='w')
        for column, (label, command) in enumerate([
                ('Move selected…', self.move_dialog), ('Swap selected with…', self.swap_dialog),
                ('Create / rename folder…', self.folder)]):
            button = ttk.Button(actions, text=label, command=command)
            button.grid(row=0, column=column, padx=(0, 8))
            if command == self.folder: self.buttons['Folder'] = button
        ttk.Radiobutton(actions, text='Insert and shift', variable=self.swap_mode, value=False).grid(row=0, column=3, padx=(8, 8))
        ttk.Radiobutton(actions, text='Swap positions', variable=self.swap_mode, value=True).grid(row=0, column=4)
        def align_actions(event):
            narrow = event.width < selection_label.winfo_reqwidth() + actions.winfo_reqwidth() + 12
            actions.grid_configure(row=1 if narrow else 0, column=0 if narrow else 1,
                                   columnspan=2 if narrow else 1, pady=(8, 0) if narrow else 0)
        bottom.bind('<Configure>', align_actions)
        self.update_buttons()
        self.window_state = WindowState(root)

    def about(self):
        existing = getattr(self, 'about_window', None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_set()
            return
        win = self.about_window = tk.Toplevel(self.root)
        win.withdraw()
        win.title('About IconTiller')
        win.configure(bg=BG)
        win.minsize(600, 440)
        body = tk.Frame(win, bg=BG, padx=28, pady=24)
        body.pack(fill='both', expand=True)
        heading = tk.Frame(body, bg=BG)
        heading.pack(fill='x', pady=(0, 18))
        tk.Label(heading, image=self.application_icons[6], bg=BG).pack(side='left', padx=(0, 16))
        tk.Label(heading, text='IconTiller', bg=BG, fg=TEXT,
                 font=('Segoe UI', 24, 'bold')).pack(side='left')
        paragraphs = [
            'Your icons. Your arrangement. Your data stays local.',
            'IconTiller was created for one simple purpose: to help you arrange your iPhone apps and folders without needing an online service or sharing your personal layout data just to move a few icons.',
            'The app reads your layout and app artwork through a local USB connection. Drafts, backups, and cached icons stay on your computer. No account, telemetry, cloud uploads, or external image service is built into the app.',
        ]
        labels = []
        for index, text in enumerate(paragraphs):
            label = tk.Label(body, text=text, bg=BG, fg=ACCENT if index == 0 else TEXT,
                             font=('Segoe UI', 11, 'bold' if index == 0 else 'normal'),
                             wraplength=544, justify='left', anchor='w')
            label.pack(fill='x', pady=(0, 16))
            labels.append(label)
        body.bind('<Configure>', lambda event: [label.configure(wraplength=max(1, event.width - 56)) for label in labels])
        footer = tk.Frame(win, bg=CARD, padx=24, pady=14)
        footer.pack(fill='x')
        close = ttk.Button(footer, text='Close', command=win.destroy)
        close.pack(side='right')
        win.bind('<Escape>', lambda e: win.destroy())
        win.bind('<Return>', lambda e: win.destroy())
        self.show_dialog(win, 620, 450)
        close.focus_set()

    def scroll(self, event):
        if event.widget.winfo_toplevel() == self.root:
            self.canvas.yview_scroll(-3 * int(event.delta / 120), 'units')

    def resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        if self.drag: return
        columns = max(1, event.width // 380)
        if columns != self.columns:
            self.columns = columns
            if self.draft: self.render()

    def discard_ok(self):
        return not self.draft or not self.draft.dirty or messagebox.askyesno('Replace current draft?', 'The layout has edits. Replace it? Save a draft first if you want to keep them.', parent=self.root)

    def update_buttons(self):
        for label in ('Read iPhone', 'Open layout', 'Demo'):
            self.buttons[label].configure(state='disabled' if self.busy else 'normal')
        for label in ('Save draft', 'Add page', 'Find app', 'Folder'):
            self.buttons[label].configure(state='normal' if self.draft and not self.busy else 'disabled')
        can_apply = False
        if self.draft and self.draft.original.device_id and not self.busy and not self.write_problem:
            try:
                validate_edit(self.baseline(), self.draft.layout)
                can_apply = True
            except (ValueError, TypeError, IndexError, KeyError): pass
        self.buttons['Apply to iPhone…'].configure(state='normal' if can_apply else 'disabled')
        self.buttons['Restore previous layout…'].configure(state='disabled')
        self.buttons['Undo'].configure(state='normal' if self.draft and self.draft.past and not self.busy else 'disabled')
        self.buttons['Redo'].configure(state='normal' if self.draft and self.draft.future and not self.busy else 'disabled')

    def read(self):
        if not self.discard_ok(): return
        self.icon_stop.set()
        self.drag_feedback.cancel()
        self.busy = True
        self.task_mode = 'read'
        self.update_buttons()
        self.status.set('Reading over USB… Unlock your phone and accept Trust if requested.')
        self.future = self.pool.submit(capture)
        self.root.after(100, self.poll)

    def poll(self):
        if not self.future.done():
            self.root.after(100, self.poll)
            return
        self.busy = False
        try:
            value = self.future.result()
            if self.task_mode == 'prepare':
                self.review_plan(value)
            elif self.task_mode == 'apply':
                self.last_result = value
                if value.status == 'verified':
                    self.show(value.observed, fetch_icons=True)
                    self.status.set('Applied and verified by a fresh read from your iPhone.')
                else:
                    self.write_problem = True
                    self.status.set('Apply result: ' + value.status.replace('_', ' ') + '. ' + value.detail + ' Read the phone again before continuing.')
                if value.backup:
                    messagebox.showinfo('Apply result', self.status.get() + '\n\nBackup saved at:\n' + str(value.backup), parent=self.root)
            else:
                self.show(value, fetch_icons=True)
        except Exception as error:
            if isinstance(error, ValueError): self.status.set(str(error))
            else: self.status.set(f'Operation could not finish ({type(error).__name__}). Reconnect and read the phone to check its state.')
        self.update_buttons()

    def baseline(self):
        if not self.draft: return None
        original = self.draft.original
        return original.layout if original.baseline is None else original.baseline

    def prepare_apply(self):
        if not self.draft or self.busy or self.write_problem: return
        self.start_prepare(self.draft.snapshot(), self.baseline())

    def start_prepare(self, desired, baseline):
        self.icon_stop.set()
        self.busy, self.task_mode = True, 'prepare'
        self.update_buttons()
        self.status.set('Checking connected phone, current layout, and page limits…')
        self.future = self.pool.submit(prepare_swap_sync, desired, baseline)
        self.root.after(100, self.poll)

    def review_plan(self, plan):
        if self.draft and self.draft.layout == plan.desired.layout:
            self.draft.original.baseline = plan.before.layout
            self.draft.original.device_id = plan.before.device_id
        if not plan.changed_pages:
            self.status.set('The draft already matches the connected iPhone.')
            return
        if not self.confirm_apply(plan): return
        self.busy, self.task_mode = True, 'apply'
        self.update_buttons()
        self.status.set('Saving backup, applying once, then reading the phone to verify…')
        self.future = self.pool.submit(apply_swap_sync, plan)
        self.root.after(100, self.poll)

    def confirm_apply(self, plan):
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title('Review arrangement')
        win.configure(bg=BG)
        win.minsize(680, 540)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(2, weight=1)
        tk.Label(win, text='Review your arrangement', bg=BG, fg=TEXT,
                 font=('Segoe UI', 20, 'bold')).grid(row=0, column=0, sticky='w', padx=24, pady=(22, 4))
        tk.Label(win, text=f'Apply these changes to {plan.before.name}', bg=BG, fg=MUTED,
                 font=('Segoe UI', 11)).grid(row=1, column=0, sticky='w', padx=24, pady=(0, 18))
        changes = tk.Frame(win, bg=CARD, padx=14, pady=12)
        changes.grid(row=2, column=0, sticky='nsew', padx=24)
        tk.Label(changes, text='CHANGES TO REVIEW', bg=CARD, fg=ACCENT,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 8))
        scrollbar = ttk.Scrollbar(changes)
        scrollbar.pack(side='right', fill='y')
        summary = tk.Text(changes, height=10, width=60, wrap='word', bg=CARD, fg=TEXT,
                          font=('Segoe UI', 11), relief='flat', borderwidth=0,
                          highlightthickness=0, spacing1=3, spacing3=5,
                          yscrollcommand=scrollbar.set)
        summary.pack(fill='both', expand=True)
        scrollbar.configure(command=summary.yview)
        summary.insert('1.0', describe_edit(plan.before.layout, plan.desired.layout, limit=None))
        summary.configure(state='disabled')
        details = tk.Frame(win, bg=BG)
        details.grid(row=3, column=0, sticky='ew', padx=24, pady=18)
        tk.Label(details, text='Page sizes and app data stay intact.', bg=BG, fg=TEXT,
                 font=('Segoe UI', 11)).pack(anchor='w')
        tk.Label(details, text='A fresh backup is saved before applying. The phone is read again to verify the result.',
                 bg=BG, fg=MUTED, font=('Segoe UI', 10), wraplength=620,
                 justify='left').pack(anchor='w', pady=(6, 12))
        tk.Label(details, text='Backup folder', bg=BG, fg=MUTED,
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 4))
        backup = ttk.Entry(details, font=('Segoe UI', 10))
        backup.insert(0, str(backup_directory()))
        backup.configure(state='readonly')
        backup.pack(fill='x')
        footer = tk.Frame(win, bg=CARD, padx=24, pady=16)
        footer.grid(row=4, column=0, sticky='ew')
        accepted = False
        def finish(value=False):
            nonlocal accepted
            accepted = value
            win.destroy()
        apply_button = tk.Button(footer, text='Apply to iPhone', command=lambda: finish(True),
                                 bg=ACCENT, fg=BG, activebackground='#85e6cf',
                                 activeforeground=BG, font=('Segoe UI', 11, 'bold'),
                                 relief='flat', padx=18, pady=9)
        apply_button.pack(side='right')
        cancel = ttk.Button(footer, text='Cancel', command=finish)
        cancel.pack(side='right', padx=(0, 12))
        win.protocol('WM_DELETE_WINDOW', finish)
        win.bind('<Escape>', lambda e: finish())
        apply_button.bind('<Return>', lambda e: finish(True))
        cancel.bind('<Return>', lambda e: finish())
        self.show_dialog(win, 760, 620, modal=True)
        cancel.focus_set()
        win.wait_window()
        return accepted

    def restore_previous(self):
        messagebox.showinfo('Phone writes paused', WRITE_BLOCK_REASON, parent=self.root)

    def show(self, snapshot, fetch_icons=False):
        self.icon_stop.set()
        if self.icon_poll is not None:
            self.root.after_cancel(self.icon_poll)
            self.icon_poll = None
        if self.icon_device != snapshot.device_id:
            self.icon_data = {}
            self.icon_device = snapshot.device_id
        self.write_problem = False
        self.draft = Draft(snapshot)
        self.render()
        if len(snapshot.device_id) == 64:
            self.start_icons(snapshot, fetch_icons)

    def artwork(self, item):
        picture = tile_image(item, self.icon_data)
        return ImageTk.PhotoImage(picture, master=self.root) if picture is not None else None

    def paint_icon(self, tile, item):
        icon = tile.winfo_children()[0]
        photo = self.artwork(item)
        name = title(item)
        icon.configure(image=photo or self.blank_icon, width=64, height=64,
                       text='' if photo else ('▦' if is_folder(item) else ''.join(w[0] for w in name.split()[:2]).upper() or '•'))
        icon.artwork = photo  # Tk only keeps the image name, not the Python reference.

    def start_icons(self, snapshot, fetch):
        self.icon_stop.set()
        if self.icon_poll is not None: self.root.after_cancel(self.icon_poll)
        self.icon_stop = Event()
        messages = Queue()
        job = self.pool.submit(load_icons, snapshot, messages, self.icon_stop, fetch)
        def poll_icons():
            self.icon_poll = None
            updated = set()
            for _ in range(10):
                try: key, data = messages.get_nowait()
                except Empty: break
                try:
                    with Image.open(BytesIO(data)) as picture:
                        self.icon_data[key] = picture.convert('RGBA')
                    updated.add(key)
                except (OSError,ValueError): pass
            if updated:
                painted = set()
                for widget, tile in self.tile_frames.items():
                    if tile in painted or not tile.winfo_exists(): continue
                    painted.add(tile)
                    path, slot = self.targets[widget]
                    item = self.draft.container(path)[slot]
                    keys = {icon_key(x) for page in item['iconLists'] for x in page} if is_folder(item) else {icon_key(item)}
                    if keys & updated: self.paint_icon(tile,item)
            if not job.done() or not messages.empty():
                self.icon_poll = self.root.after(50,poll_icons)
        self.icon_poll = self.root.after(50,poll_icons)

    def render(self):
        self.drag_feedback.cancel()
        for win in self.folder_windows:
            if win.winfo_exists(): win.destroy()
        self.folder_windows = []
        self.selected = self.drag = None
        self.selection.set('Select an app or folder')
        self.targets, self.tile_frames, self.page_links, self.page_cards = {}, {}, {}, {}
        for child in self.page_nav.winfo_children(): child.destroy()
        tk.Label(self.page_nav, text='Go to page', bg=BG, fg=MUTED).pack(side='left', padx=(0, 8))
        for index in range(len(self.draft.layout)):
            link = tk.Label(self.page_nav, text='Dock' if index == 0 else str(index),
                            bg=CARD, fg=TEXT, padx=7, pady=5, cursor='hand2')
            link.pack(side='left', padx=2)
            self.page_links[link] = index
            link.bind('<Button-1>', lambda e, p=index: self.jump_page(p))
        for child in self.pages.winfo_children(): child.destroy()
        for col in range(8): self.pages.columnconfigure(col, weight=0)
        for col in range(self.columns): self.pages.columnconfigure(col, weight=1)
        for index, items in enumerate(self.draft.layout):
            card = tk.Frame(self.pages, bg=CARD, padx=10, pady=12)
            card.grid(row=index // self.columns, column=index % self.columns, sticky='nsew', padx=8, pady=8)
            self.page_cards[index] = card
            self.targets[card] = ((index,), None)
            heading = tk.Label(card, text=('Dock' if index == 0 else f'Page {index}') + f'   ·   {len(items)} items', bg=CARD, fg=TEXT, font=('Segoe UI', 12, 'bold'), anchor='w')
            heading.pack(fill='x', pady=(0, 10))
            self.targets[heading] = ((index,), None)
            grid = tk.Frame(card, bg=CARD)
            grid.pack(fill='both', expand=True)
            self.targets[grid] = ((index,), None)
            if isinstance(items, list): self.tiles(grid, (index,), items)
        self.update_draft_status()

    def update_draft_status(self):
        mark = 'Edited draft' if self.draft.dirty else 'Original layout'
        if self.draft.dirty:
            try:
                validate_edit(self.baseline(), self.draft.layout)
                mark += ' • Arrangement ready for review' if self.draft.original.device_id else ' • Local demo/file only'
            except ValueError:
                mark += ' • Unsupported changes; undo folder edits, removals, or page-size changes'
        self.status.set(f'{self.draft.original.name}  •  iOS {self.draft.original.version}  •  {mark}')
        self.update_buttons()

    def tiles(self, parent, path, items):
        for col in range(4): parent.columnconfigure(col, weight=1)
        for index, item in enumerate(items):
            name = title(item)
            color = '#375875' if is_folder(item) else ['#326d80', '#665396', '#95614a', '#426e64', '#526da1'][hashlib.sha256(name.encode()).digest()[0] % 5]
            tile = tk.Frame(parent, bg=CARD, highlightthickness=2, highlightbackground=CARD, padx=2, pady=3)
            tile.grid(row=index // 4, column=index % 4, sticky='nsew', padx=2, pady=4)
            badge = '▦' if is_folder(item) else ''.join(word[0] for word in name.split()[:2]).upper()
            icon = tk.Label(tile, text=badge or '•', bg=color, fg='white', font=('Segoe UI', 18, 'bold'), image=self.blank_icon, compound='center', width=64, height=64)
            icon.pack()
            label = tk.Label(tile, text=name[:36], bg=CARD, fg=TEXT, wraplength=74, height=3, font=('Segoe UI', 9))
            label.pack(fill='x')
            self.paint_icon(tile, item)
            for widget in (tile, icon, label):
                widget.configure(cursor='hand2')
                self.targets[widget] = (path, index)
                self.tile_frames[widget] = tile
                widget.bind('<ButtonPress-1>', lambda e, p=path, i=index, t=tile: self.pick(e, p, i, t))
                widget.bind('<Double-Button-1>', lambda e, p=path, i=index: self.open_folder(p, i))
        end = tk.Label(parent, text='Drop here to place at page end', bg=CARD, fg=MUTED, pady=12, wraplength=280)
        end.grid(row=(len(items) + 3) // 4, column=0, columnspan=4, sticky='ew')
        self.targets[end] = (path, None)

    def pick(self, event, path, index, tile):
        if self.busy: return
        self.drag_feedback.begin()
        self.selected = (path, index)
        self.drag = (path, index, event.x_root, event.y_root)
        self.selection.set(title(self.draft.container(path)[index])[:32])
        for widget in self.targets:
            if isinstance(widget, tk.Frame) and int(widget.cget('highlightthickness')) == 2:
                widget.configure(highlightbackground=CARD)
        tile.configure(highlightbackground=ACCENT)

    def drop(self, event):
        if not self.drag or self.busy: return
        path, index, x, y = self.drag
        widget = self.drag_feedback.target_at(event.x_root, event.y_root)
        valid = self.drag_feedback.valid_target(widget)
        self.drag_feedback.reset()
        self.drag = None
        if abs(event.x_root-x) + abs(event.y_root-y) < 8: return
        if not valid:
            self.status.set('No change made. Choose a Home Screen app boundary to insert, or another app to swap.')
            return
        if widget in self.targets:
            target, position = self.targets[widget]
            if self.swap_mode.get():
                if position is None:
                    self.status.set('Drop onto another app tile to swap positions.')
                    return
                self.swap_in_place(path, index, target, position)
            else:
                self.insert_in_place(path, index, target, self.insertion_position(widget, event.x_root))

    def insertion_position(self, widget, x):
        path, index = self.targets[widget]
        if index is None: return len(self.draft.container(path))
        tile = self.tile_frames[widget]
        return index + (x >= tile.winfo_rootx() + tile.winfo_width()/2)

    def insert_in_place(self, source, index, target, position):
        if not self.draft or self.busy: return
        try:
            self.draft.insert_across_pages(source, index, target, position)
            self.drag_feedback.cancel()
            for win in self.folder_windows:
                if win.winfo_exists(): win.destroy()
            self.folder_windows = []
            self.targets = {w:loc for w,loc in self.targets.items() if len(loc[0]) == 1}
            self.tile_frames = {w:t for w,t in self.tile_frames.items() if w in self.targets}
            painted = set()
            for widget, (path, slot) in self.targets.items():
                tile = self.tile_frames.get(widget)
                if tile is None or tile in painted: continue
                painted.add(tile)
                item = self.draft.container(path)[slot]
                name = title(item)
                color = '#375875' if is_folder(item) else ['#326d80', '#665396', '#95614a', '#426e64', '#526da1'][hashlib.sha256(name.encode()).digest()[0] % 5]
                icon, label = tile.winfo_children()
                icon.configure(text='▦' if is_folder(item) else ''.join(w[0] for w in name.split()[:2]).upper() or '•', bg=color)
                label.configure(text=name[:36])
                self.paint_icon(tile, item)
                tile.configure(highlightbackground=CARD)
            self.selected = None
            self.selection.set('Arrangement ready for review')
            self.update_draft_status()
        except (ValueError, IndexError, KeyError) as error:
            messagebox.showerror('Cannot insert here', str(error), parent=self.root)

    def swap_in_place(self, source, index, target, position):
        if not self.draft or self.busy: return
        try:
            self.draft.swap(source, index, target, position)
            self.drag_feedback.cancel()
            affected = {(source, index), (target, position)}
            painted = set()
            for widget, location in self.targets.items():
                tile = self.tile_frames.get(widget)
                if location not in affected or tile is None or tile in painted: continue
                painted.add(tile)
                path, slot = location
                item = self.draft.container(path)[slot]
                name = title(item)
                color = ['#326d80', '#665396', '#95614a', '#426e64', '#526da1'][hashlib.sha256(name.encode()).digest()[0] % 5]
                icon, label = tile.winfo_children()
                icon.configure(text=''.join(word[0] for word in name.split()[:2]).upper() or '•', bg=color)
                label.configure(text=name[:36])
                self.paint_icon(tile, item)
                tile.configure(highlightbackground=CARD)
            self.selected = None
            self.selection.set('Swap ready • Review and apply')
            self.update_draft_status()
        except (ValueError, IndexError, KeyError) as error:
            messagebox.showerror('Cannot make that change', str(error), parent=self.root)

    def perform(self, action):
        if not self.draft or self.busy: return
        try:
            action()
            self.render()
        except (ValueError, IndexError, KeyError) as error:
            messagebox.showerror('Cannot make that change', str(error), parent=self.root)

    def show_dialog(self, win, width=None, height=None, modal=False):
        """Place a completed dialog over the current app position, then show it."""
        win.transient(self.root)
        self.root.update_idletasks()
        width = max(width or 0, win.winfo_reqwidth())
        height = max(height or 0, win.winfo_reqheight())
        # Geometry positions include the window frame, unlike winfo_rootx/y.
        x = self.root.winfo_x() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - height) // 2
        # '+-N' is an absolute negative coordinate, for monitors left of/above primary.
        win.geometry(f'{width}x{height}+{x}+{y}')
        win.deiconify()
        if modal:
            win.grab_set()

    def open_folder(self, path, index):
        self.drag_feedback.cancel()
        self.drag = None
        if self.busy: return
        item = self.draft.container(path)[index]
        if not is_folder(item) or len(path) != 1: return
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title(title(item))
        win.configure(bg=CARD)
        self.folder_windows.append(win)
        tabs = ttk.Notebook(win)
        tabs.pack(fill='both', expand=True, padx=12, pady=12)
        for page, entries in enumerate(item['iconLists']):
            frame = tk.Frame(tabs, bg=CARD, padx=8, pady=8)
            tabs.add(frame, text=f'Folder page {page+1}')
            target = (path[0], index, page)
            self.targets[frame] = (target, None)
            self.tiles(frame, target, entries)
        tk.Label(win, text='Use Move selected to move an app to another page or folder.', bg=CARD, fg=TEXT).pack(padx=12, pady=12)
        def closed():
            self.drag_feedback.cancel()
            self.targets = {w: v for w, v in self.targets.items() if w.winfo_toplevel() != win}
            self.tile_frames = {w: v for w, v in self.tile_frames.items() if w.winfo_toplevel() != win}
            self.selected = self.drag = None
            self.selection.set('Select an app or folder')
            win.destroy()
        win.protocol('WM_DELETE_WINDOW', closed)
        self.show_dialog(win)

    def jump_page(self, page):
        card = self.page_cards.get(page)
        if not card: return
        self.root.update_idletasks()
        height = max(1, self.pages.winfo_height())
        self.canvas.yview_moveto(max(0, card.winfo_y()-8) / height)
        for link, index in self.page_links.items():
            link.configure(bg=ACCENT if index == page else CARD, fg=BG if index == page else TEXT)

    def move_dialog(self):
        if not self.selected or self.busy: return
        self.drag_feedback.cancel()
        source, index = self.selected
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title('Move selected item')
        choices = []
        for p, page in enumerate(self.draft.layout):
            choices.append(('Dock' if p == 0 else f'Page {p}', (p,)))
            for i, item in enumerate(page):
                if is_folder(item):
                    for f in range(len(item['iconLists'])):
                        choices.append((f'Page {p} / {title(item)} / Folder page {f+1}', (p, i, f)))
        ttk.Label(win, text='Move to the end of:').pack(padx=20, pady=12)
        combo = ttk.Combobox(win, values=[name for name, _ in choices], state='readonly', width=60)
        combo.pack(padx=20, pady=8)
        combo.current(0)
        def apply():
            target = choices[combo.current()][1]
            win.destroy()
            self.perform(lambda: self.draft.move(source, index, target))
        ttk.Button(win, text='Move', command=apply).pack(pady=14)
        win.bind('<Escape>', lambda e: win.destroy())
        self.show_dialog(win, modal=True)

    def swap_dialog(self):
        if not self.draft or not self.selected or self.busy: return
        self.drag_feedback.cancel()
        source, index = self.selected
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title('Swap with another app')
        query = tk.StringVar()
        ttk.Label(win, text='Choose an app to exchange positions with the selected app.').pack(padx=16, pady=12)
        entry = ttk.Entry(win, textvariable=query)
        entry.pack(fill='x', padx=16)
        listing = tk.Listbox(win, font=('Segoe UI', 10), exportselection=False)
        listing.pack(fill='both', expand=True, padx=16, pady=12)
        results = []
        def refresh(*_):
            results[:] = [r for r in self.draft.find(query.get())
                          if r[2][0] != 0 and (r[2], r[3]) != (source, index)
                          and not is_folder(self.draft.container(r[2])[r[3]])
                          and self.draft.container(r[2])[r[3]].get('bundleIdentifier')]
            listing.delete(0, 'end')
            for name, location, _, _ in results: listing.insert('end', f'{name} — {location}')
            if results: listing.selection_set(0)
        def choose(*_):
            selected = listing.curselection()
            if not selected: return
            _, _, target, position = results[selected[0]]
            win.destroy()
            self.swap_in_place(source, index, target, position)
        ttk.Button(win, text='Swap in draft', command=choose).pack(pady=(0, 12))
        listing.bind('<Double-Button-1>', choose)
        win.bind('<Return>', choose)
        win.bind('<Escape>', lambda e: win.destroy())
        query.trace_add('write', refresh)
        refresh()
        self.show_dialog(win, 700, 460, modal=True)
        entry.focus_set()

    def find_dialog(self):
        if not self.draft or self.busy: return
        self.drag_feedback.cancel()
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title('Find an app or folder')
        query = tk.StringVar()
        ttk.Label(win, text='Search by app name or identifier, including inside folders.').pack(anchor='w', padx=16, pady=(16, 8))
        entry = ttk.Entry(win, textvariable=query)
        entry.pack(fill='x', padx=16)
        style = ttk.Style(win)
        style.configure('SearchResults.Treeview', font=('Segoe UI', 10),
                        rowheight=32, padding=(8, 8))
        result_frame = ttk.Frame(win)
        result_frame.pack(fill='both', expand=True, padx=16, pady=12)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_font = tkfont.Font(root=win, family='Segoe UI', size=10)
        listing = ttk.Treeview(result_frame, columns=('name', 'separator', 'location'),
                               show='', selectmode='browse', style='SearchResults.Treeview', height=8)
        listing.column('name', anchor='w', stretch=False)
        listing.column('separator', anchor='w', stretch=False,
                       width=result_font.measure('—  ') + 4, minwidth=0)
        listing.column('location', anchor='w', stretch=True)
        scrollbar = ttk.Scrollbar(result_frame, orient='vertical', command=listing.yview)
        listing.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(result_frame, orient='horizontal', command=listing.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        listing.configure(xscrollcommand=horizontal.set)
        listing.grid(row=0, column=0, sticky='nsew')
        results = []
        def refresh(*_):
            results[:] = self.draft.find(query.get())
            listing.delete(*listing.get_children())
            name_width = max((result_font.measure(row[0]) for row in results), default=0)
            listing.column('name', width=name_width + result_font.measure('  ') + 4, minwidth=0)
            location_width = max((result_font.measure(row[1]) for row in results), default=0) + 12
            listing.column('location', width=location_width, minwidth=location_width)
            for index, (name, location, _, _) in enumerate(results):
                listing.insert('', 'end', iid=str(index), values=(name, '—', location))
            if results:
                listing.selection_set('0')
                listing.focus('0')
            move.configure(state='normal' if results else 'disabled')
        def move_result(*_):
            selected = listing.selection()
            if not selected: return
            name, _, path, index = results[int(selected[0])]
            self.selected = (path, index)
            self.selection.set(name[:32])
            win.destroy()
            self.move_dialog()
        move = ttk.Button(win, text='Move selected result…', command=move_result)
        move.pack(pady=(0, 16))
        def swap_result():
            selected = listing.selection()
            if not selected: return
            name, _, path, index = results[int(selected[0])]
            self.selected = (path, index)
            self.selection.set(name[:32])
            win.destroy()
            self.swap_dialog()
        ttk.Button(win, text='Swap selected result…', command=swap_result).pack(pady=(0, 12))
        listing.bind('<Double-Button-1>', move_result)
        win.bind('<Return>', move_result)
        win.bind('<Escape>', lambda e: win.destroy())
        query.trace_add('write', refresh)
        refresh()
        self.show_dialog(win, 700, 460, modal=True)
        entry.focus_set()

    def folder(self):
        if not self.draft or self.busy: return
        self.drag_feedback.cancel()
        choices = [(name, location, path, index) for name, location, path, index in self.draft.find('')
                   if len(path) == 1 and isinstance(self.draft.container(path)[index], dict)]
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title('Create / rename folder')
        win.minsize(540, 300)
        body = ttk.Frame(win, padding=24)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='Choose an app to create a folder, or a folder to rename.',
                  font=('Segoe UI', 11), wraplength=490).pack(anchor='w')
        target = ttk.Combobox(body, state='readonly', font=('Segoe UI', 11),
                              values=[f'{name} — {location}' for name, location, _, _ in choices])
        target.pack(fill='x', pady=(10, 16))
        ttk.Label(body, text='Folder name:', font=('Segoe UI', 11)).pack(anchor='w')
        entry = ttk.Entry(body, font=('Segoe UI', 12))
        entry.pack(fill='x', pady=(8, 20))
        buttons = ttk.Frame(body)
        buttons.pack(side='bottom', anchor='e')
        def apply(*_):
            if target.current() < 0: return
            if not entry.get().strip():
                entry.focus_set()
                return
            _, _, path, index = choices[target.current()]
            name = entry.get()
            win.destroy()
            self.perform(lambda: self.draft.folder(path, index, name))
        ok = ttk.Button(buttons, text='OK', command=apply, state='disabled')
        ok.pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Cancel', command=win.destroy).pack(side='left')
        def choose(*_):
            _, _, path, index = choices[target.current()]
            item = self.draft.container(path)[index]
            entry.delete(0, 'end')
            entry.insert(0, title(item) if is_folder(item) else '')
            entry.selection_range(0, 'end')
            ok.configure(state='normal')
            entry.focus_set()
        target.bind('<<ComboboxSelected>>', choose)
        for position, (_, _, path, index) in enumerate(choices):
            if (path, index) == self.selected:
                target.current(position)
                choose()
                break
        win.bind('<Return>', apply)
        win.bind('<Escape>', lambda e: win.destroy())
        self.show_dialog(win, 540, 300, modal=True)
        if target.current() < 0: target.focus_set()
        else: entry.focus_set()

    def undo(self): self.perform(lambda: self.draft.undo())
    def redo(self): self.perform(lambda: self.draft.redo())
    def add_page(self): self.perform(lambda: self.draft.add_page())

    def backup(self):
        if not self.draft or self.busy: return
        self.drag_feedback.cancel()
        path = filedialog.asksaveasfilename(parent=self.root, title='Save a new local draft', defaultextension='.plist', filetypes=[('Layout draft', '*.plist')])
        if path:
            try:
                save_snapshot(self.draft.saved_snapshot(), Path(path))
                self.status.set('Draft saved locally. Your original file and iPhone are unchanged.')
            except FileExistsError: messagebox.showerror('Choose a new filename', 'Existing files are never overwritten.', parent=self.root)
            except Exception: messagebox.showerror('Could not save', 'Check folder permissions and try again.', parent=self.root)

    def open(self):
        if self.busy or not self.discard_ok(): return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[('Layout backup / draft', '*.plist')])
        if path:
            try: self.show(load_snapshot(Path(path)))
            except Exception: messagebox.showerror('Could not open', 'This is not a readable supported layout file.', parent=self.root)

    def demo(self):
        if self.busy or not self.discard_ok(): return
        def app(name): return {'displayName': name, 'bundleIdentifier': 'demo.' + name.lower()}
        self.show(Snapshot('Demo — not your phone', 'sample', [
            [app(n) for n in ('Phone', 'Safari', 'Messages', 'Music')],
            [app(n) for n in ('Calendar', 'Photos', 'Camera', 'Weather', 'Maps', 'Notes', 'Reminders', 'Settings')]
            + [{'displayName': 'Work', 'listType': 'folder', 'iconLists': [[app('Mail'), app('Files')]]}],
            [app(n) for n in ('Books', 'Podcasts', 'Fitness', 'Clock')]]))

    def close(self):
        if self.busy:
            messagebox.showinfo('Operation in progress', 'Wait for the USB operation and verification to finish before closing.', parent=self.root)
            return
        if not self.discard_ok(): return
        self.drag_feedback.cancel()
        self.icon_stop.set()
        if self.icon_poll is not None: self.root.after_cancel(self.icon_poll)
        self.window_state.save()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Local iPhone Home Screen editor')
    parser.add_argument('--self-test', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        from smoke_check import run
        run(args.self_test)
        raise SystemExit(0)
    import os
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('IconTiller.Desktop')
    root = tk.Tk()
    app = App(root)
    root.mainloop()
