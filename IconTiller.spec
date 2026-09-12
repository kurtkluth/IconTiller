from PyInstaller.utils.hooks import copy_metadata

a = Analysis(['app.py'], pathex=[], binaries=[],
             datas=copy_metadata('pymobiledevice3') + [('assets/icontiller.png', 'assets'), ('assets/icontiller.ico', 'assets')], hiddenimports=[],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='IconTiller', icon='assets/icontiller.ico', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='IconTiller')
