# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

_project_root = Path(SPEC).parent.resolve()

flask_datas, flask_binaries, flask_hiddenimports = collect_all('flask')
cors_datas, cors_binaries, cors_hiddenimports = collect_all('flask_cors')
limiter_datas, limiter_binaries, limiter_hiddenimports = collect_all('flask_limiter')
dotenv_datas, dotenv_binaries, dotenv_hiddenimports = collect_all('dotenv')
crypto_datas, crypto_binaries, crypto_hiddenimports = collect_all('cryptography')

a = Analysis(
    ['plugin/arkshop_web/app.py'],
    pathex=[str(_project_root)],
    binaries=[] + flask_binaries + cors_binaries + limiter_binaries + dotenv_binaries + crypto_binaries,
    datas=[
        ('plugin/arkshop_web/static', 'static'),
        ('plugin/arkshop_web/data', 'data'),
        ('plugin/CustomShop/configs/config.json', 'CustomShop/configs'),
        ('version.json', '.'),
    ] + flask_datas + cors_datas + limiter_datas + dotenv_datas + crypto_datas,
    hiddenimports=[
        'flask',
        'flask_cors',
        'flask_limiter',
        'flask_limiter.util',
        'limits',
        'limits.storage',
        'limits.storage.memory',
        'ordered_set',
        'sqlalchemy',
        'sqlalchemy.dialects.mysql',
        'sqlalchemy.dialects.mysql.pymysql',
        'pymysql',
        'rcon_bridge',
        'src.rcon_client',
        'src.rcon_util',
        'cryptography',
        'cryptography.fernet',
        'dotenv',
        'werkzeug',
        'jinja2',
    ] + collect_submodules('sqlalchemy')
      + flask_hiddenimports + cors_hiddenimports + limiter_hiddenimports
      + dotenv_hiddenimports + crypto_hiddenimports,
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
