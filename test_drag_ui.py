import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import App
from drag_ui import edge_step


class DragTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.ui = App(self.root)
        self.ui.swap_mode.set(True)
        self.ui.demo()

    def tearDown(self):
        self.ui.drag_feedback.cancel()
        self.ui.pool.shutdown(wait=True, cancel_futures=True)
        self.root.destroy()

    def pick_first(self):
        tile = next(w for w, target in self.ui.targets.items() if target == ((1,), 0))
        self.ui.pick(SimpleNamespace(x_root=100, y_root=100), (1,), 0, tile)
        return tile

    def test_threshold_preview_highlight_and_escape_leave_draft_unchanged(self):
        original = self.ui.draft.snapshot()
        self.pick_first()
        self.ui.drag_feedback.motion(SimpleNamespace(x_root=102, y_root=102))
        self.assertIsNone(self.ui.drag_feedback.ghost)
        target = next(w for w, pos in self.ui.targets.items() if pos == ((2,), 0))
        with patch.object(self.root, 'winfo_containing', return_value=target):
            self.ui.drag_feedback.motion(SimpleNamespace(x_root=140, y_root=140))
        self.assertTrue(self.ui.drag_feedback.active)
        self.assertIsNotNone(self.ui.drag_feedback.ghost)
        self.assertEqual(self.ui.drag_feedback.highlight, self.ui.tile_frames[target])
        self.assertIn('Books', self.ui.status.get())
        self.ui.drag_feedback.cancel()
        self.assertIsNone(self.ui.drag)
        self.assertIsNone(self.ui.drag_feedback.timer)
        self.assertIsNone(self.ui.drag_feedback.ghost)
        self.assertEqual(self.ui.draft.snapshot(), original)

    def test_release_outside_or_on_folder_does_not_edit(self):
        original = self.ui.draft.snapshot()
        for target in (None, next(w for w, pos in self.ui.targets.items() if pos == ((1,), 8))):
            self.pick_first()
            with patch.object(self.root, 'winfo_containing', return_value=target):
                self.ui.drop(SimpleNamespace(x_root=200, y_root=200))
            self.assertEqual(self.ui.draft.snapshot(), original)

    def test_page_hover_jumps_without_releasing_and_drop_swaps(self):
        self.pick_first()
        link = next(w for w, page in self.ui.page_links.items() if page == 2)
        with patch.object(self.root, 'winfo_containing', return_value=link), \
                patch.object(self.root, 'winfo_pointerxy', return_value=(200, 200)), \
                patch('drag_ui.time.monotonic', return_value=1):
            self.ui.drag_feedback.motion(SimpleNamespace(x_root=200, y_root=200))
        feedback = self.ui.drag_feedback
        self.root.after_cancel(feedback.timer)
        feedback.timer = None
        with patch.object(self.root, 'winfo_containing', return_value=link), \
                patch.object(self.root, 'winfo_pointerxy', return_value=(200, 200)), \
                patch('drag_ui.time.monotonic', return_value=2), patch.object(self.ui, 'jump_page') as jump:
            feedback.tick()
            jump.assert_called_once_with(2)
        self.assertIsNotNone(self.ui.drag)
        target = next(w for w, pos in self.ui.targets.items() if pos == ((2,), 0))
        with patch.object(self.root, 'winfo_containing', return_value=target):
            self.ui.drop(SimpleNamespace(x_root=300, y_root=300))
        self.assertEqual(self.ui.draft.layout[1][0]['displayName'], 'Books')
        self.assertEqual(self.ui.draft.layout[2][0]['displayName'], 'Calendar')
        self.assertIsNone(feedback.timer)
        self.assertIsNone(feedback.ghost)

    def test_scroll_edges_and_resize_do_not_destroy_active_drag(self):
        self.assertEqual(edge_step(50, 110, 0, 100, 500, 400), -2)
        self.assertEqual(edge_step(50, 490, 0, 100, 500, 400), 2)
        self.assertEqual(edge_step(50, 300, 0, 100, 500, 400), 0)
        self.assertEqual(edge_step(600, 490, 0, 100, 500, 400), 0)
        self.pick_first()
        with patch.object(self.ui, 'render') as render:
            self.ui.resize(SimpleNamespace(width=600))
            render.assert_not_called()
        self.assertIsNotNone(self.ui.drag)

    def test_swap_repaints_only_existing_tiles_and_keeps_folder_open(self):
        self.ui.open_folder((1,), 8)
        folder = self.ui.folder_windows[0]
        source_tile = next(w for w, pos in self.ui.targets.items() if pos == ((2,), 0))
        destination_tile = next(w for w, pos in self.ui.targets.items() if pos == ((1, 8, 0), 0))
        with patch.object(self.ui, 'render') as render:
            self.ui.swap_in_place((2,), 0, (1, 8, 0), 0)
            render.assert_not_called()
        self.assertTrue(folder.winfo_exists())
        self.assertEqual(source_tile.winfo_children()[1].cget('text'), 'Mail')
        self.assertEqual(destination_tile.winfo_children()[1].cget('text'), 'Books')
        self.assertTrue(self.ui.draft.dirty)

    def test_insert_mode_marks_boundary_and_shifts_without_rebuilding(self):
        self.ui.swap_mode.set(False)
        before = self.ui.draft.snapshot()
        self.pick_first()
        target = next(w for w,pos in self.ui.targets.items() if pos == ((2,),1))
        with patch.object(self.root,'winfo_containing',return_value=target):
            self.ui.drag_feedback.motion(SimpleNamespace(x_root=300,y_root=300))
            self.assertIsNotNone(self.ui.drag_feedback.insert_line)
            with patch.object(self.ui,'render') as render:
                self.ui.drop(SimpleNamespace(x_root=300,y_root=300))
                render.assert_not_called()
        self.assertIsNone(self.ui.drag_feedback.insert_line)
        self.assertEqual([len(p) for p in self.ui.draft.layout],[len(p) for p in before.layout])
        self.assertTrue(self.ui.draft.dirty)

    def test_folder_dialog_without_selection_can_create_and_prefill_rename(self):
        from tkinter import ttk
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        self.ui.selected = None
        self.ui.folder()
        win = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        widgets = list(descendants(win))
        target = next(w for w in widgets if isinstance(w, ttk.Combobox))
        entry = next(w for w in widgets if isinstance(w, ttk.Entry) and not isinstance(w, ttk.Combobox))
        ok = next(w for w in widgets if isinstance(w, ttk.Button) and w.cget('text') == 'OK')
        self.assertEqual(target.current(), -1)
        self.assertIn('disabled', ok.state())
        target.current(4)  # Calendar, the first Home Screen app in the demo.
        target.event_generate('<<ComboboxSelected>>')
        entry.insert(0, 'Personal')
        ok.invoke()
        self.assertEqual(self.ui.draft.layout[1][0]['displayName'], 'Personal')
        self.ui.selected = ((1,), 0)
        self.ui.folder()
        win = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        entry = next(w for w in descendants(win) if isinstance(w, ttk.Entry) and not isinstance(w, ttk.Combobox))
        self.assertEqual(entry.get(), 'Personal')
        win.destroy()

    def test_toolbar_alignment_at_normal_and_minimum_width(self):
        self.root.deiconify()
        for width in (1280, 850):
            self.root.geometry(f'{width}x850')
            self.root.update()
            self.assertEqual(self.ui.buttons['Find app'].winfo_rootx(),
                             self.ui.buttons['Add page'].winfo_rootx())
            actions = self.ui.buttons['Folder'].master
            self.assertLessEqual(actions.winfo_rootx() + actions.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())
            self.assertEqual(int(actions.grid_info()['row']), 0 if width == 1280 else 1)
