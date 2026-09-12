import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from window_state import WindowState, placement


class WindowStateTests(unittest.TestCase):
    screens = [
        {'id': 'main', 'work': (0, 0, 1920, 1040), 'primary': True},
        {'id': 'left', 'work': (-1600, 0, 0, 900), 'primary': False},
    ]

    def saved(self, **changes):
        return dict(dict(x=-1500, y=50, width=1100, height=700,
                         monitor='left', maximized=False), **changes)

    def test_connected_negative_monitor_keeps_position(self):
        result = placement(self.saved(), self.screens)
        self.assertEqual((result['x'], result['y'], result['width'], result['height']), (-1500, 50, 1100, 700))

    def test_removed_or_repositioned_monitor_returns_to_origin(self):
        for screens in (self.screens[:1], [self.screens[0], dict(self.screens[1], work=(1920, 0, 3520, 900))]):
            result = placement(self.saved(maximized=True), screens)
            self.assertEqual((result['x'], result['y']), (0, 0))
            self.assertTrue(result['maximized'])

    def test_oversized_window_fits_and_malformed_preferences_are_ignored(self):
        result = placement(self.saved(width=3000, height=2000), self.screens)
        self.assertLessEqual(result['x'] + result['width'], 0)
        self.assertLessEqual(result['y'] + result['height'], 900)
        for saved in (None, [], {}, self.saved(width='huge'), self.saved(height=-2)):
            self.assertIsNone(placement(saved, self.screens))

    def test_save_and_restore_maximized_keeps_normal_bounds(self):
        root = Mock()
        root.state.return_value = 'normal'
        root.winfo_x.return_value = -1500
        root.winfo_y.return_value = 50
        root.winfo_width.return_value = 1100
        root.winfo_height.return_value = 700
        with tempfile.TemporaryDirectory() as directory, patch('window_state.monitors', return_value=self.screens):
            path = Path(directory) / 'window.json'
            state = WindowState(root, path)
            state.remember()
            root.state.return_value = 'zoomed'
            state.remember()
            root.state.return_value = 'iconic'
            state.save()
            saved = json.loads(path.read_text())
            self.assertTrue(saved['maximized'])
            self.assertEqual(saved['width'], 1100)
            self.assertEqual(saved['monitor'], 'left')
            restored = Mock()
            WindowState(restored, path)
            restored.geometry.assert_called_once_with('1100x700+-1500+50')
            restored.state.assert_called_once_with('zoomed')

    def test_corrupt_or_unwritable_file_does_not_block_app(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'window.json'
            path.write_text('broken json')
            root = Mock()
            root.state.return_value = 'iconic'
            state = WindowState(root, path)
            root.geometry.assert_not_called()
            state.normal = dict(x=10, y=10, width=1000, height=700)
            state.path = Path(directory) / 'blocked'
            state.path.mkdir()  # A directory cannot be replaced by a file.
            with patch('window_state.monitors', return_value=self.screens):
                state.save()
