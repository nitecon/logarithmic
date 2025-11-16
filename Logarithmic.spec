# -*- mode: python ; coding: utf-8 -*-
import os
import sys  
from pathlib import Path

# --- Cross-Platform Setup ---
project_root = Path(SPECPATH)
icon_file = None
signing_args = {}
windows_args = {}

# Centralized version and metadata
# Priority: 1) Environment variable (set by build scripts from git tag)
#           2) Git tag directly (fallback if env var not set)
#           3) Default version (if git not available)
import subprocess

def get_version():
    # First, check if build script set APP_VERSION env var
    env_version = os.environ.get('APP_VERSION')
    if env_version:
        return env_version
    
    # Fallback: Try to get latest git tag directly
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().lstrip('v')  # Remove 'v' prefix if present
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    
    # Final fallback
    return '1.0.0'

APP_VERSION = get_version()
print(f"Building Logarithmic version: {APP_VERSION}")

bundle_id = 'com.logarithmic.app' # Your bundle ID
info_plist_file = 'Info.plist'

if sys.platform == 'darwin':
    icon_file = 'logo.icns'
    # These args are passed to EXE, which passes them to BUNDLE
    signing_args = {
        'codesign_identity': os.environ.get('APP_CERT'),
        'entitlements_file': 'entitlements.plist',
    }
    info_plist_dict = {
        # Bundle Information
        'CFBundleName': 'Logarithmic',
        'CFBundleDisplayName': 'Logarithmic',
        'CFBundleIdentifier': bundle_id,
        
        # This is the FIX: Set BOTH version keys from your git tag
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': '????',
        'CFBundleExecutable': 'Logarithmic',
        'CFBundleIconFile': icon_file,
        
        # Application Information
        'NSHumanReadableCopyright': 'Copyright © 2025 Willem J Hattingh. All rights reserved.',
        'LSMinimumSystemVersion': '12.0',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
        
        # UI Configuration
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
        'LSUIElement': False,

        # Export Compliance
        'ITSAppUsesNonExemptEncryption': False,
        
        # Network (for sandbox)
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True
        },
        
        # Document Types (for sandbox and file association)
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Log File',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': [
                    'public.log',
                    'public.plain-text',
                ],
                'LSHandlerRank': 'Alternate'
            }
        ],
        'UTExportedTypeDeclarations': [
            {
                'UTTypeIdentifier': 'public.log',
                'UTTypeDescription': 'Log File',
                'UTTypeConformsTo': ['public.plain-text'],
                'UTTypeTagSpecification': {
                    'public.filename-extension': ['log']
                }
            }
        ]
    }
elif sys.platform == 'win32':
    icon_file = 'logo.ico'
    # Windows-specific metadata for version info and UAC
    windows_args = {
        'uac_admin': False,  # Set to True if app requires admin privileges
        'version': APP_VERSION,
    }
elif sys.platform.startswith('linux'):
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

# --- EXE (Cross-Platform, Onedir Mode) ---
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
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
    icon=icon_file,        
    **signing_args,         # <-- Unpacks Mac signing args, does nothing on other OSes
    **windows_args,         # <-- Unpacks Windows-specific args (version, UAC), does nothing on other OSes
)

# --- Output: BUNDLE (Mac) or COLLECT (Windows/Linux) ---
if sys.platform == 'darwin':
    # Create macOS .app bundle
    app = BUNDLE(
        exe,
        a.binaries,         # <-- Pass binaries from Analysis
        a.zipfiles,         # <-- Pass zipfiles from Analysis
        a.datas,            # <-- Pass datas from Analysis
        name='Logarithmic.app',
        icon=icon_file,
        bundle_identifier=bundle_id,
        info_plist=info_plist_dict,
        datas_symlinks=False
        # Note: signing_args are in exe and will be used
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