from copy import deepcopy
import unittest
from device import Snapshot
from live_folder_test import folder_move_target, parse_path


class FolderMovePlanTests(unittest.TestCase):
    def test_swap_with_folder_preserves_counts_metadata_and_is_reversible(self):
        source = Snapshot('Test', '27', [[], [{'bundleIdentifier': 'a', 'extra': b'bytes'}], [
            {'displayName': 'AI', 'iconLists': [[{'bundleIdentifier': 'b'}, {'bundleIdentifier': 'c'}]],
             'listMetadata': {'future': 17}}]], 'id')
        original = deepcopy(source)
        swapped = folder_move_target(source, (1,), 0, (2, 0, 0), 1, exchange=True)
        self.assertEqual(source, original)
        self.assertEqual([len(p) for p in swapped.layout], [0, 1, 1])
        self.assertEqual(swapped.layout[1][0], source.layout[2][0]['iconLists'][0][1])
        self.assertEqual(swapped.layout[2][0]['iconLists'][0], [{'bundleIdentifier': 'b'}, source.layout[1][0]])
        self.assertEqual(swapped.layout[2][0]['listMetadata'], {'future': 17})
        self.assertEqual(folder_move_target(swapped, (2, 0, 0), 1, (1,), 0, exchange=True), source)
        for position in (None, -1, 2):
            with self.assertRaises(ValueError):
                folder_move_target(source, (1,), 0, (2, 0, 0), position, exchange=True)

    def test_in_and_out_preserve_metadata_even_when_folder_index_shifts(self):
        source = Snapshot('Test', '27', [[], [
            {'bundleIdentifier': 'a', 'extra': b'bytes'},
            {'displayName': 'Folder', 'iconLists': [[{'bundleIdentifier': 'b'}]], 'listMetadata': {'x': 1}}
        ]], 'id')
        before = deepcopy(source)
        inside = folder_move_target(source, (1,), 0, (1, 1, 0))
        self.assertEqual(source, before)
        self.assertEqual(inside.layout[1][0]['listMetadata'], {'x': 1})
        self.assertEqual(len(inside.layout[1][0]['iconLists'][0]), 2)
        outside = folder_move_target(inside, (1, 0, 0), 1, (1,), 0)
        self.assertEqual(outside, source)
        with self.assertRaises(ValueError): folder_move_target(source, (1,), 1, (1, 1, 0))
        with self.assertRaises(ValueError): folder_move_target(source, (1,), -1, (1, 1, 0))
        self.assertEqual(parse_path('2,1,1'), (2, 0, 0))
