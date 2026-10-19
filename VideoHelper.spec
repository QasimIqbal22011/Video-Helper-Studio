# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None
BASE_DIR = os.path.abspath(SPECPATH)

# Data files to bundle inside the executable
datas = [
    (os.path.join(BASE_DIR, 'src', 'gui', 'web'), os.path.join('src', 'gui', 'web')),
    (os.path.join(BASE_DIR, 'resources', 'ffmpeg', 'ffmpeg.exe'), os.path.join('resources', 'ffmpeg')),
]

hiddenimports = [
    'clr_loader',
    'pythonnet',
    'webview',
    'webview.platforms.winforms',
    'bottle',
    'wsgiref.simple_server',
]

a = Analysis(
    [os.path.join(BASE_DIR, 'src', 'main.py')],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VideoHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI mode - no command prompt popup window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoHelper',
)
