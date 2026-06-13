# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

flask_datas, flask_binaries, flask_hiddenimports = collect_all('flask')

a = Analysis(
    ['plugin/arkshop_web/app.py'],
    pathex=[],
    binaries=[] + flask_binaries,
    datas=[
        ('plugin/arkshop_web/static', 'static'),
        ('plugin/CustomShop/configs/config.json', 'CustomShop/configs'),
        ('version.json', '.'),
    ] + flask_datas,
    hiddenimports=[
        'flask',
        'flask_cors',
        'flask_limiter',
        'flask_limiter.util',
        'limits',
        'limits.storage',
        'limits.storage.memory',
        'sqlalchemy',
        'sqlalchemy.dialects.mysql',
        'sqlalchemy.dialects.mysql.pymysql',
        'pymysql',
        'cryptography',
        'cryptography.fernet',
        'dotenv',
        'werkzeug',
        'jinja2',
    ] + collect_submodules('sqlalchemy') + flask_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas', 'PyQt5', 'PyQt6',
              'customtkinter', 'PIL', 'pystray', 'pytest'],
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
    name='ARKLAND-WebStore',
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
