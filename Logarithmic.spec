# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# Get the project root directory
project_root = Path(SPECPATH)

# Include font files
font_dir = project_root / 'fonts'
font_datas = []
if font_dir.exists():
    for font_file in font_dir.glob('**/*.ttf'):
        font_datas.append((str(font_file), 'fonts'))

a = Analysis(
    ['src/logarithmic/__main__.py'],
    pathex=[],
    binaries=[],
    datas=font_datas,
    hiddenimports=['PySide6.QtCore', 'PySide6.QtWidgets', 'PySide6.QtGui', 'watchdog.observers', 'watchdog.events'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Logarithmic',
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
    icon=None,
)

# Create macOS app bundle
app = BUNDLE(
    exe,
    name='Logarithmic.app',
    icon=None,
    bundle_identifier='com.logarithmic.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'LSBackgroundOnly': 'False',
    },
)
