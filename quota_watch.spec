# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for QuotaWatch. Build: pyinstaller quota_watch.spec"""

a = Analysis(
    ['monitor/__main__.py'],
    pathex=['G:/Gitrepo/quota-watch'],
    binaries=[],
    datas=[
        ('monitor/html/popup.html', 'monitor/html'),
        ('monitor/html/popup.css',  'monitor/html'),
        ('monitor/html/popup.js',   'monitor/html'),
    ],
    hiddenimports=[
        'pystray._win32',
        'pystray._util',
        'pystray._util.win32',
        'webview',
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'bottle',
        'clr_loader',
        'winreg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter',
        'PIL._avif', 'PIL._webp',
        'PIL._imagingcms', 'PIL._imagingmath', 'PIL._imagingtk', 'PIL._imagingmorph',
        'setuptools', '_distutils_hack',
        'multiprocessing',
        'sqlite3',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='QuotaWatch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon='soc_monitor.ico',
)
