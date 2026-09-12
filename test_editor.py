from copy import deepcopy
import unittest
from device import Snapshot
from editor import Draft, is_folder

def app(name): return {'displayName': name, 'bundleIdentifier': name, 'unknown': b'\x01\xff'}

class EditorTests(unittest.TestCase):
    def setUp(self):
        self.source = Snapshot('Test', '27', [[app('dock')], [app('a'), app('b'), {'displayName': 'Work', 'listType': 'folder', 'iconLists': [[app('c')]], 'metadata': {'future': 42}}], []])
        self.draft = Draft(self.source)

    def test_cross_page_move_and_history_preserve_original(self):
        original = deepcopy(self.source)
        self.draft.move((1,), 0, (2,))
        self.assertEqual(self.draft.layout[2][0], app('a'))
        self.assertEqual(self.source, original)
        self.draft.undo()
        self.assertEqual(self.draft.snapshot(), original)
        self.draft.redo()
        self.assertEqual(self.draft.layout[2][0], app('a'))

    def test_move_to_folder_after_source_index_shifts(self):
        self.draft.move((1,), 0, (1, 2, 0))
        folder = self.draft.layout[1][1]
        self.assertEqual([x['displayName'] for x in folder['iconLists'][0]], ['c', 'a'])
        self.assertEqual(folder['metadata'], {'future': 42})

    def test_move_out_of_folder(self):
        self.draft.move((1, 2, 0), 0, (2,))
        self.assertEqual(self.draft.layout[2], [app('c')])
        self.assertEqual(self.draft.layout[1][2]['iconLists'], [[]])

    def test_reorder_forward_and_backward(self):
        self.draft.move((1,), 0, (1,), 2)
        self.assertEqual(self.draft.layout[1][:2], [app('b'), app('a')])
        self.draft.move((1,), 1, (1,), 0)
        self.assertEqual(self.draft.snapshot(), self.source)

    def test_no_nested_folder_or_full_dock(self):
        with self.assertRaises(ValueError): self.draft.move((1,), 2, (1, 2, 0))
        self.draft.layout[0] = [app(str(i)) for i in range(4)]
        with self.assertRaises(ValueError): self.draft.move((1,), 0, (0,))
        self.assertEqual(len(self.draft.past), 0)

    def test_special_app_is_not_folder(self):
        self.assertFalse(is_folder({'iconType': 'app', 'bundleIdentifier': 'special', 'iconLists': []}))
        self.assertTrue(is_folder(self.draft.layout[1][2]))

    def test_search_returns_current_folder_locations_without_editing(self):
        self.draft.layout[1][2]['iconLists'][0][0]['displayName'] = 'Nested Mail'
        before = self.draft.snapshot()
        self.assertEqual(self.draft.find(' MAIL '), [('Nested Mail', 'Page 1 / Work / Folder page 1', (1, 2, 0), 0)])
        self.assertEqual(self.draft.find('WORK')[0][2:], ((1,), 2))
        self.assertEqual(self.draft.find('missing'), [])
        self.assertEqual(self.draft.snapshot(), before)
        self.assertEqual(self.draft.past, [])
        self.draft.move((1, 2, 0), 0, (2,))
        self.assertEqual(self.draft.find('mail')[0][2:], ((2,), 0))

    def test_folder_create_rename_undo_and_redo_branch(self):
        self.draft.folder((1,), 0, 'Personal')
        self.assertEqual(self.draft.layout[1][0]['iconLists'], [[app('a')]])
        self.draft.folder((1,), 0, 'Favorites')
        self.draft.undo()
        self.assertEqual(self.draft.layout[1][0]['displayName'], 'Personal')
        self.draft.add_page()
        self.assertEqual(self.draft.future, [])

if __name__ == '__main__': unittest.main()
