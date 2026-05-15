# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Coleta completa dos pacotes que carregam dados em runtime
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')
pil_datas,  pil_binaries,  pil_hiddenimports  = collect_all('PIL')
tray_datas, tray_binaries, tray_hiddenimports = collect_all('pystray')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[] + ctk_binaries + pil_binaries + tray_binaries,
    datas=[
        ('ig', 'ig'),
    ] + ctk_datas + pil_datas + tray_datas,
    hiddenimports=[
        # customtkinter
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.core_widget_classes',
        'customtkinter.windows.ctk_tk',
        'customtkinter.windows.ctk_toplevel',
        # PIL / Pillow
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.PngImagePlugin',
        'PIL.IcoImagePlugin',
        # stdlib / tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        # projeto
        'src.app',
        'src.server_config',
        'src.server_manager',
        'src.mod_manager',
        'src.ark_ini',
        'src.rcon_client',
        'src.config_manager',
        'src.updater',
        'src.version',
        'src.mod_auto_updater',
        # bandeja
        'pystray',
        'pystray._win32',
        # monitoramento de desempenho
        'psutil',
        'psutil._pswindows',
        'psutil._common',
    ] + ctk_hiddenimports + pil_hiddenimports + tray_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas', 'PyQt5', 'PyQt6'],
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
    name='ARKLAND-ServerManager',
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
