# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')

a = Analysis(
    ['arkland_updater.py'],
    pathex=[],
    binaries=[] + ctk_binaries,
    datas=[
        ('ig', 'ig'),
    ] + ctk_datas,
    hiddenimports=[
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.core_widget_classes',
        'customtkinter.windows.ctk_tk',
        'tkinter',
        'tkinter.ttk',
    ] + ctk_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas', 'PyQt5', 'PyQt6',
              'PIL', 'pystray', 'requests'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ARKLAND-Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ig\\ArkLandBR.ico'],
    version_file=None,
)
