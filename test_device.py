import tempfile
import unittest
from pathlib import Path
from device import Snapshot, load_snapshot, save_snapshot


class BackupTests(unittest.TestCase):
    def test_identity_and_baseline_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'draft.plist'
            draft = Snapshot('Phone', '27', [[{'bundleIdentifier': 'a'}]], 'hash', [[{'bundleIdentifier': 'b'}]])
            save_snapshot(draft, path)
            self.assertEqual(load_snapshot(path), draft)

    def test_preserves_unknown_fields_and_binary_data(self):
        layout = [[{"displayName": "App", "futureWidgetField": {"bytes": b"\x00\xff"}}], [], [False]]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "layout.plist"
            original = Snapshot("Test phone", "27", layout)
            save_snapshot(original, path)
            self.assertEqual(load_snapshot(path), original)
            with self.assertRaises(FileExistsError):
                save_snapshot(Snapshot("Other", "26", [[]]), path)
            self.assertEqual(load_snapshot(path), original)

    def test_rejects_foreign_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.plist"
            path.write_bytes(b"not a plist")
            with self.assertRaises(Exception):
                load_snapshot(path)


if __name__ == "__main__":
    unittest.main()
