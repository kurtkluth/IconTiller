import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app import App
from device import Snapshot
from safe_swap import validate_swap, describe_swap, prepare_swap, apply_swap
from test_sync import Phone


class SwapBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_transaction_verifies_one_swap_and_rejects_tampered_plan(self):
        phone = Phone()
        before = deepcopy(phone.layout)
        desired = Snapshot(phone.name, phone.version, [before[0], list(reversed(before[1]))], phone.device_id)
        plan = await prepare_swap(desired, before, phone.connection)
        with tempfile.TemporaryDirectory() as directory:
            result = await apply_swap(plan, directory, phone.connection)
            self.assertEqual(result.status, 'verified')
            self.assertTrue(result.backup.exists())
            self.assertEqual(phone.writes, 1)
            plan.desired.layout[1].pop()
            with self.assertRaises(ValueError): await apply_swap(plan, directory, phone.connection)
            self.assertEqual(phone.writes, 1)

    async def test_stale_and_unidentified_drafts_rejected(self):
        phone = Phone()
        baseline = deepcopy(phone.layout)
        desired = Snapshot(phone.name, phone.version, [baseline[0], list(reversed(baseline[1]))], '')
        with self.assertRaises(ValueError): await prepare_swap(desired, baseline, phone.connection)
        desired.device_id = phone.device_id
        phone.layout[1][0]['extra'] = 1
        with self.assertRaises(ValueError): await prepare_swap(desired, baseline, phone.connection)
        self.assertEqual(phone.writes, 0)

    def test_structure_and_metadata_boundary(self):
        a, b = {'bundleIdentifier':'a'}, {'bundleIdentifier':'b'}
        before = [[{'bundleIdentifier':'dock'}], [a, {'displayName':'AI', 'iconLists':[[b]], 'extra':b'bytes'}]]
        after = deepcopy(before)
        after[1][0], after[1][1]['iconLists'][0][0] = after[1][1]['iconLists'][0][0], after[1][0]
        self.assertEqual(len(validate_swap(before, after)), 2)
        self.assertIn('AI', describe_swap(before, after))
        for change in ('metadata', 'size', 'dock', 'appmetadata'):
            bad = deepcopy(after)
            if change == 'metadata': bad[1][1]['extra'] = b'lost'
            if change == 'size': bad[1].append({'bundleIdentifier':'new'})
            if change == 'dock': bad[0][0]['extra'] = 1
            if change == 'appmetadata': bad[1][0]['extra'] = 1
            with self.assertRaises(ValueError): validate_swap(before, bad)
        with self.assertRaises(ValueError): validate_swap(before, before)
        many = [[], [{'bundleIdentifier':str(i)} for i in range(4)]]
        with self.assertRaises(ValueError): validate_swap(many, [[], list(reversed(many[1]))])


class SwapUITests(unittest.TestCase):
    def test_drag_swaps_apps_and_insert_stays_unappliable(self):
        root = tk.Tk()
        root.withdraw()
        ui = App(root)
        ui.swap_mode.set(True)
        try:
            phone = Phone()
            ui.show(Snapshot(phone.name, phone.version, deepcopy(phone.layout), phone.device_id))
            widget = next(w for w, pos in ui.targets.items() if pos == ((1,), 1))
            ui.drag = ((1,), 0, 0, 0)
            with patch.object(root, 'winfo_containing', return_value=widget):
                ui.drop(SimpleNamespace(x_root=100, y_root=100))
            self.assertEqual(ui.draft.layout[1][0]['bundleIdentifier'], 'b')
            self.assertEqual(str(ui.buttons['Apply to iPhone…']['state']), 'normal')
            ui.undo()
            ui.perform(lambda: ui.draft.add_page())
            ui.perform(lambda: ui.draft.move((1,), 0, (2,)))
            self.assertEqual(str(ui.buttons['Apply to iPhone…']['state']), 'disabled')
        finally:
            ui.pool.shutdown(wait=True, cancel_futures=True)
            root.destroy()

    def test_mismatch_disables_further_apply_until_fresh_read(self):
        from concurrent.futures import Future
        from sync import Result
        root = tk.Tk()
        root.withdraw()
        ui = App(root)
        ui.swap_mode.set(True)
        try:
            phone = Phone()
            ui.show(Snapshot(phone.name, phone.version, deepcopy(phone.layout), phone.device_id))
            ui.perform(lambda: ui.draft.swap((1,), 0, (1,), 1))
            ui.task_mode = 'apply'
            ui.busy = True
            ui.future = Future()
            ui.future.set_result(Result('mismatch', None, None, 'Unexpected result'))
            ui.poll()
            self.assertTrue(ui.write_problem)
            self.assertEqual(str(ui.buttons['Apply to iPhone…']['state']), 'disabled')
            self.assertIn('Read the phone again', ui.status.get())
        finally:
            ui.pool.shutdown(wait=True, cancel_futures=True)
            root.destroy()

    def test_review_dialog_requires_explicit_apply_and_shows_all_changes(self):
        from types import SimpleNamespace
        root = tk.Tk()
        root.withdraw()
        ui = App(root)
        before = [[], [{'displayName': f'App {i}', 'bundleIdentifier': f'test.{i}'} for i in range(14)]]
        desired = [[], before[1][1:] + before[1][:1]]
        plan = SimpleNamespace(before=Snapshot('Test phone', 'sample', before),
                               desired=Snapshot('Test phone', 'sample', desired))
        observations = []
        def visit(widget):
            for child in widget.winfo_children():
                yield child
                yield from visit(child)
        def respond(accept):
            win = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            widgets = list(visit(win))
            text = next(w for w in widgets if isinstance(w, tk.Text)).get('1.0', 'end')
            observations.append(text)
            if accept:
                next(w for w in widgets if isinstance(w, tk.Button) and w.cget('text') == 'Apply to iPhone').invoke()
            else:
                win.destroy()  # Closing the review must also count as Cancel.
        try:
            for accept in (False, True):
                root.after(50, lambda accept=accept: respond(accept))
                self.assertEqual(ui.confirm_apply(plan), accept)
            self.assertTrue(all('Page 1, slot 14:' in text for text in observations))
            self.assertTrue(all('additional positions' not in text for text in observations))
        finally:
            ui.pool.shutdown(wait=True, cancel_futures=True)
            root.destroy()

    def test_review_apply_and_verified_refresh_with_fake_phone(self):
        phone = Phone()
        root = tk.Tk()
        root.withdraw()
        ui = App(root)
        ui.swap_mode.set(True)
        try:
            ui.show(Snapshot(phone.name, phone.version, deepcopy(phone.layout), phone.device_id))
            ui.perform(lambda: ui.draft.swap((1,), 0, (1,), 1))
            self.assertEqual(str(ui.buttons['Apply to iPhone…']['state']), 'normal')
            self.assertEqual(str(ui.buttons['Restore previous layout…']['state']), 'disabled')
            with tempfile.TemporaryDirectory() as directory:
                def prep(desired, baseline): return asyncio.run(prepare_swap(desired, baseline, phone.connection))
                def send(plan): return asyncio.run(apply_swap(plan, directory, phone.connection))
                with patch('app.prepare_swap_sync', prep), patch('app.apply_swap_sync', send), \
                        patch.object(ui, 'confirm_apply', return_value=True) as review, patch('app.messagebox.showinfo'):
                    ui.prepare_apply()
                    deadline = time.monotonic() + 10
                    while ui.busy and time.monotonic() < deadline:
                        root.update()
                        time.sleep(0.02)
                    self.assertFalse(ui.busy)
                    self.assertEqual(phone.writes, 1)
                    self.assertTrue(review.called)
                    self.assertEqual(ui.draft.layout, phone.layout)
                    self.assertFalse(ui.draft.dirty)
                    self.assertEqual(str(ui.buttons['Apply to iPhone…']['state']), 'disabled')
                    self.assertIn('verified', ui.status.get())
        finally:
            ui.pool.shutdown(wait=True, cancel_futures=True)
            root.destroy()
