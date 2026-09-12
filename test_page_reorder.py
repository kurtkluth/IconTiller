import unittest
from copy import deepcopy
from device import Snapshot
from editor import Draft
from safe_swap import validate_edit


class PageInsertionTests(unittest.TestCase):
    def setUp(self):
        app = lambda name: {'bundleIdentifier': name, 'extra': b'preserve'}
        self.source = Snapshot('Test','27',[[app('dock')],[app('a'),app('b'),app('c')],
            [{'displayName':'Folder','iconLists':[[app('child')]],'metadata':{'x':1}},app('d'),app('e')],
            [app('f'),app('g'),app('h')]],'id')

    def test_forward_cascade_and_undo_preserve_full_folders(self):
        draft=Draft(self.source)
        original=deepcopy(self.source)
        draft.insert_across_pages((1,),1,(3,),1)
        self.assertEqual([len(p) for p in draft.layout],[1,3,3,3])
        self.assertEqual(draft.layout[1],[self.source.layout[1][0],self.source.layout[1][2],self.source.layout[2][0]])
        self.assertEqual(draft.layout[3],[self.source.layout[1][1],self.source.layout[3][1],self.source.layout[3][2]])
        self.assertEqual(validate_edit(self.source.layout,draft.layout),'reorder')
        self.assertEqual(self.source,original)
        draft.undo();self.assertEqual(draft.snapshot(),original)
        draft.redo();self.assertTrue(draft.dirty)

    def test_backward_move_shifts_entries_to_later_pages(self):
        draft=Draft(self.source)
        draft.insert_across_pages((3,),2,(1,),0)
        self.assertEqual(draft.layout[1][0],self.source.layout[3][2])
        self.assertEqual(draft.layout[2][0],self.source.layout[1][2])
        self.assertEqual(draft.layout[3][0],self.source.layout[2][2])
        validate_edit(self.source.layout,draft.layout)

    def test_metadata_removal_and_dock_changes_are_rejected(self):
        draft=Draft(self.source)
        draft.insert_across_pages((1,),0,(2,),2)
        for kind in ('metadata','removed','dock'):
            bad=deepcopy(draft.layout)
            if kind=='metadata':
                next(x for p in bad for x in p if 'metadata' in x)['metadata']['x']=2
            elif kind=='removed': bad[1].pop()
            else: bad[0][0]['extra']=b'changed'
            with self.assertRaises(ValueError):validate_edit(self.source.layout,bad)
        with self.assertRaises(ValueError):draft.insert_across_pages((0,),0,(1,),0)

    def test_drop_at_end_of_earlier_full_page_stays_on_that_page(self):
        draft=Draft(self.source)
        draft.insert_across_pages((3,),2,(1,),3)
        self.assertEqual(draft.layout[1][-1],self.source.layout[3][-1])
        self.assertEqual(draft.layout[2][0],self.source.layout[1][-1])
