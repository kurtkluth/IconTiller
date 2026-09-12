"""Exercise the packaged GUI and imports without connecting to a phone."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk


def run(report):
    result = {'passed': False}
    root = None
    ui = None
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.springboard import SpringBoardServicesService
        from app import App
        from device import load_snapshot, save_snapshot
        root = tk.Tk()
        root.withdraw()
        ui = App(root)
        ui.demo()
        root.update()
        matches = ui.draft.find('mail')
        assert len(matches) == 1 and len(matches[0][2]) == 3
        _, _, path, index = matches[0]
        original = ui.draft.snapshot()
        ui.perform(lambda: ui.draft.move(path, index, (2,)))
        assert ui.draft.find('mail')[0][2] == (2,)
        ui.undo()
        assert ui.draft.snapshot() == original
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'draft.plist'
            save_snapshot(ui.draft.saved_snapshot(), target)
            assert load_snapshot(target) == ui.draft.saved_snapshot()
        assert str(ui.buttons['Apply to iPhone…']['state']) == 'disabled'
        assert str(ui.buttons['Restore previous layout…']['state']) == 'disabled'
        ui.find_dialog()
        root.update()
        result = {'passed': True, 'checks': ['GUI', 'folder search', 'move and undo', 'save and reopen', 'USB dependency imports', 'write controls disabled'], 'device_accessed': False}
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        if ui: ui.pool.shutdown(wait=False, cancel_futures=True)
        if root: root.destroy()
        Path(report).write_text(json.dumps(result, indent=2), encoding='utf-8')
