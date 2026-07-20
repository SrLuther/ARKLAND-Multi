# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# Coleta completa dos pacotes que carregam dados em runtime
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')
pil_datas,  pil_binaries,  pil_hiddenimports  = collect_all('PIL')
tray_datas, tray_binaries, tray_hiddenimports = collect_all('pystray')

# Coleta todos os submódulos do pacote src automaticamente
src_hiddenimports = collect_submodules('src')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[] + ctk_binaries + pil_binaries + tray_binaries,
    datas=[
        ('ig', 'ig'),
        ('setup_db.sql', '.'),
        ('plugin/CustomShop/bin/CustomShop.dll',      'plugins'),
        ('plugin/CustomShop/bin/libmariadb.dll',       'plugins'),
        ('plugin/CustomShop/bin/z.dll',                'plugins'),
        ('plugin/CustomShop/bin/PluginInfo.json',      'plugins/customshop'),
        ('plugin/CustomDinoDeliver/bin/CustomDinoDeliver.dll', 'plugins'),
        ('plugin/CustomDinoDeliver/bin/PluginInfo.json', 'plugins/customdino'),
        ('plugin/ArkPlayer/bin/ArkPlayer.dll',         'plugins'),
        ('plugin/ArkPlayer/bin/PluginInfo.json',       'plugins/arkplayer'),
        ('plugin/ArkPlayer/configs/config.json',       'plugins/arkplayer'),
        ('plugin/Permissions/configs/config.json',   'Permissions/configs'),
        ('config/mapas_cross_chat_ids.json',         'config'),
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
        # bandeja
        'pystray',
        'pystray._win32',
        # monitoramento de desempenho
        'psutil',
        'psutil._pswindows',
        'psutil._common',
    ] + ctk_hiddenimports + pil_hiddenimports + tray_hiddenimports + src_hiddenimports,
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
    uac_admin=True,
)
