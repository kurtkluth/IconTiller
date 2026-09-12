from io import BytesIO
from pathlib import Path
from queue import Queue
from threading import Event
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from device import Snapshot
from icons import apps_in, cache_path, icon_key, load_icons, tile_image, validate_png


class IconTests(unittest.TestCase):
    def png(self):
        buffer=BytesIO();Image.new('RGBA',(204,204),'red').save(buffer,format='PNG')
        return buffer.getvalue()

    def test_nested_apps_dedup_and_device_version_scoped_paths(self):
        app={'bundleIdentifier':'example','bundleVersion':'2','iconLists':[],'iconType':'app'}
        folder={'displayName':'Folder','iconLists':[[app]]}
        self.assertEqual(apps_in([[app,folder]]),[('example','2')])
        self.assertNotEqual(cache_path('a',icon_key(app)),cache_path('b',icon_key(app)))
        self.assertNotEqual(cache_path('a',('example','2')),cache_path('a',('example','3')))
        self.assertIsNone(icon_key({'webClipURL':'https://example.com'}))

    def test_cache_only_load_validates_images_and_never_connects(self):
        snapshot=Snapshot('Test','27',[[{'bundleIdentifier':'example'}]],'device')
        with tempfile.TemporaryDirectory() as directory:
            path=cache_path(snapshot.device_id,('example',''),directory)
            path.parent.mkdir(parents=True);path.write_bytes(self.png())
            output=Queue()
            with patch('icons.usb_connection',side_effect=AssertionError('unexpected USB')):
                load_icons(snapshot,output,Event(),False,directory)
                self.assertEqual(output.get_nowait()[0],('example',''))
                path.write_bytes(b'bad image')
                load_icons(snapshot,output,Event(),False,directory)
                self.assertTrue(output.empty())

    def test_mosaic_fallback_and_cancel(self):
        app={'bundleIdentifier':'a'}; folder={'iconLists':[[app,{'bundleIdentifier':'missing'}]]}
        self.assertIsNone(tile_image(folder,{}))
        images={('a',''):Image.new('RGBA',(204,204),'red')}
        self.assertEqual(tile_image(app,images).size,(64,64))
        self.assertEqual(tile_image(folder,images).getpixel((6,6)),(255,0,0,255))
        stop=Event();stop.set();output=Queue()
        with patch('icons.usb_connection',side_effect=AssertionError('unexpected USB')):
            load_icons(Snapshot('Test','27',[[app]],'id'),output,stop,True)
        self.assertTrue(output.empty())
        with self.assertRaises(ValueError):validate_png(b'not png')

    def test_gui_keeps_artwork_attached_when_icons_swap(self):
        import tkinter as tk
        from app import App
        root=tk.Tk();root.withdraw();ui=App(root)
        try:
            first={'bundleIdentifier':'a','displayName':'A'}
            second={'bundleIdentifier':'b','displayName':'B'}
            ui.show(Snapshot('Demo','27',[[],[first,second]],''))
            ui.icon_data={('a',''):Image.new('RGBA',(64,64),'red'),('b',''):Image.new('RGBA',(64,64),'blue')}
            ui.render()
            tile=next(w for w,pos in ui.targets.items() if pos==((1,),0))
            label=tile.winfo_children()[0]
            self.assertEqual(root.tk.call(str(label.cget('image')),'get',20,20),(255,0,0))
            ui.swap_in_place((1,),0,(1,),1)
            self.assertEqual(root.tk.call(str(label.cget('image')),'get',20,20),(0,0,255))
            self.assertEqual(label.cget('text'),'')
        finally:
            ui.drag_feedback.cancel();ui.icon_stop.set();ui.pool.shutdown(wait=True);root.destroy()
