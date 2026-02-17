# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for building elod.exe

import os
from PyInstaller.utils.hooks import collect_data_files

# openpyxl ships template files that must be bundled
openpyxl_datas = collect_data_files('openpyxl')

# Absolute path to the project root so PyInstaller finds local modules
project_root = os.path.abspath('.')

a = Analysis(
    ['regenerate_all.py'],
    pathex=[project_root],
    binaries=[],
    datas=openpyxl_datas,
    hiddenimports=[
        'generate_progressive',
        'elod',
        'elo_math',
        'player',
        'tournament',
        'mdb_reader',
        'html_reader',
        'image_reader',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'test_elod',
        'pytesseract',
        'PIL',
        'Pillow',
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
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
    name='elod',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
