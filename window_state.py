"""Local window preferences and monitor-aware placement (no device data)."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tkinter as tk


def settings_path():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'iPhoneScreenManager' / 'window.json'


def monitors(root):
    if os.name == 'nt':
        class Info(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                        ('work', wintypes.RECT), ('flags', wintypes.DWORD),
                        ('device', wintypes.WCHAR * 32)]
        found = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                           ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        user32 = ctypes.windll.user32
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        def visit(handle, dc, rect, data):
            info = Info()
            info.size = ctypes.sizeof(info)
            if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                r = info.work
                found.append({'id': info.device, 'work': (r.left, r.top, r.right, r.bottom),
                              'primary': bool(info.flags & 1)})
            return True
        callback = callback_type(visit)
        user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), callback_type, wintypes.LPARAM]
        user32.EnumDisplayMonitors.restype = wintypes.BOOL
        if user32.EnumDisplayMonitors(None, None, callback, 0) and found:
            return found
    return [{'id': 'primary', 'work': (0, 0, root.winfo_screenwidth(), root.winfo_screenheight()), 'primary': True}]


def placement(saved, screens):
    """Return safe normal geometry and maximized state, or None for bad settings."""
    if not isinstance(saved, dict): return None
    if any(type(saved.get(k)) is not int for k in ('x', 'y', 'width', 'height')): return None
    if not (0 < saved['width'] <= 50000 and 0 < saved['height'] <= 50000): return None
    screen = next((m for m in screens if m['id'] == saved.get('monitor')), None)
    x, y = saved['x'], saved['y']
    missing = screen is None
    if screen is not None:
        left, top, right, bottom = screen['work']
        missing = not (left <= x < right - 32 and top <= y < bottom - 32)
    if missing:
        screen = next((m for m in screens if m['primary']), screens[0])
        x = y = 0
    left, top, right, bottom = screen['work']
    width = min(max(850, saved['width']), max(1, right - left - 16))
    height = min(max(600, saved['height']), max(1, bottom - top - 40))
    if not missing:
        x = min(x, right - width - 16)
        y = min(y, bottom - height - 40)
    return {'x': x, 'y': y, 'width': width, 'height': height,
            'maximized': saved.get('maximized') is True}


class WindowState:
    def __init__(self, root, path=None):
        self.root = root
        self.path = Path(path) if path is not None else settings_path()
        self.normal = None
        self.maximized = False
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            restored = placement(saved, monitors(root))
            if restored:
                self.normal = restored
                root.geometry('{width}x{height}+{x}+{y}'.format(**restored))
                if restored['maximized']:
                    root.state('zoomed')
                    self.maximized = True
        except (OSError, ValueError, tk.TclError):
            pass  # Missing or damaged preferences must never prevent startup.
        root.bind('<Configure>', self.remember, add='+')

    def remember(self, event=None):
        if event is not None and event.widget != self.root: return
        state = self.root.state()
        if state not in ('normal', 'zoomed'): return
        self.maximized = state == 'zoomed'
        if not self.maximized:
            self.normal = {'x': self.root.winfo_x(), 'y': self.root.winfo_y(),
                           'width': self.root.winfo_width(), 'height': self.root.winfo_height()}

    def save(self):
        self.remember()
        if not self.normal: return
        saved = dict(self.normal, maximized=self.maximized)
        screens = monitors(self.root)
        def overlap(screen):
            left, top, right, bottom = screen['work']
            return max(0, min(saved['x'] + saved['width'], right) - max(saved['x'], left)) * max(0, min(saved['y'] + saved['height'], bottom) - max(saved['y'], top))
        saved['monitor'] = max(screens, key=overlap)['id']
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(saved), encoding='utf-8')
            temporary.replace(self.path)
        except OSError:
            pass  # Preference storage is best-effort; closing must still work.
