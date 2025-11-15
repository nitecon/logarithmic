# -*- mode: python ; coding: utf-8 -*-
import os
import sys  # <-- Import sys to check the OS
from pathlib import Path

# --- Cross-Platform Setup ---
project_root = Path(SPECPATH)
icon_file = None
signing_args = {}
bundle_id = 'com.logarithmic.app' # Your bundle ID
info_plist_file = 'Info.plist'

if sys.platform == 'darwin':
    icon_file = 'logo.icns'
    # These args are passed to EXE, which passes them to BUNDLE
    signing_args = {
        'codesign_identity': os.environ.get('APP_CERT'),
        'entitlements_file': 'entitlements.plist',
    }
elif sys.platform == 'win32':
    icon_file = 'logo.ico'
elif sys.platform.startswith('linux'):
    # Linux uses .png for icons, but not in the PyInstaller build itself.
    # This is handled by your .desktop file or package (e.g., .deb)
    icon_file = None

# --- Your Font Logic (This is great, no changes needed) ---
font_dir = project_root / 'fonts'
font_datas = []
if font_dir.exists():
    for font_file in font_dir.glob('**/*.ttf'):
        relative_path = font_file.relative_to(project_root)
        dest_dir = str(relative_path.parent)
        font_datas.append((str(font_file), dest_dir))

# --- Analysis (No changes needed) ---
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

# --- EXE (Now Cross-Platform) ---
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
    console=False,          # <-- Correct for a GUI app on all platforms
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=icon_file,         # <-- Uses our conditional icon
    **signing_args,         # <-- Unpacks Mac signing args, does nothing on other OSes
)

# --- Output: BUNDLE (Mac) or COLLECT (Windows/Linux) ---
if sys.platform == 'darwin':
    # Create macOS .app bundle
    app = BUNDLE(
        exe,
        name='Logarithmic.app',
        icon=icon_file,
        bundle_identifier=bundle_id,
        version='1.0.0',
        info_plist=info_plist_file,
        # Note: codesign_identity and entitlements_file are passed
        # from the EXE block automatically.
    )
else:
    # Create a standard output folder for Windows and Linux
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Logarithmic'  # <-- This will create the 'dist/Logarithmic' folder
    )
