from copy import deepcopy
import unittest
from device import Snapshot
from live_move_test import swap_target


class LiveMovePlanTests(unittest.TestCase):
    def test_cross_page_swap_preserves_sizes_and_rejects_bad_destination(self):
        source = Snapshot('Test', '27', [[], [{'bundleIdentifier': 'a', 'extra': b'1'}],
            [{'bundleIdentifier': 'b'}, {'bundleIdentifier': 'c'}]], 'id')
        before = deepcopy(source)
        target = swap_target(source, 1, 0, 1, 2)
        self.assertEqual(source, before)
        self.assertEqual([len(p) for p in target.layout], [0, 1, 2])
        self.assertEqual(target.layout, [[], [source.layout[2][1]], [source.layout[2][0], source.layout[1][0]]])
        self.assertEqual(swap_target(target, 1, 0, 1, 2), source)
        for destination, slot in [(0, 0), (3, 0), (2, 2)]:
            with self.assertRaises(ValueError): swap_target(source, 1, 0, slot, destination)

    def test_only_selected_entries_change_and_metadata_survives(self):
        source = Snapshot('Test', '27', [[], [
            {'bundleIdentifier': 'a', 'unknown': b'abc'},
            {'bundleIdentifier': 'b', 'iconLists': []},
            {'displayName': 'Folder', 'iconLists': [[]], 'listMetadata': {'x': 1}}
        ]], 'test-identity')
        before = deepcopy(source)
        target = swap_target(source, 1, 0, 1)
        self.assertEqual(source, before)
        self.assertEqual(target.layout[1], [source.layout[1][1], source.layout[1][0], source.layout[1][2]])
        self.assertEqual(swap_target(target, 1, 0, 1), source)
        for page, first, second in [(0, 0, 1), (1, 0, 0), (1, 0, 2), (1, 0, 3), (1, -1, 0)]:
            with self.assertRaises(ValueError): swap_target(source, page, first, second)


if __name__ == '__main__': unittest.main()
