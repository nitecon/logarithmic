#!/bin/bash
set -e
# Personal build script - not committed to repo

# --- 1. Get the APP Certificate ---
export APP_CERT=$(security find-identity -v -p codesigning | grep "Apple Distribution" | head -n 1 | awk -F'"' '{print $2}')
if [ -z "$APP_CERT" ]; then
  echo "Error: Could not find 'Apple Distribution' certificate."
  echo "This is for signing the .app bundle."
  exit 1
fi
echo "== Using App Cert: $APP_CERT =="

# --- 2. Get the INSTALLER Certificate ---
# Note: Apple's older name for this was "3rd Party Mac Developer Installer"
# This command checks for both the new and old names.
export INSTALLER_CERT=$(security find-identity -v -p macappstore |grep -E "3rd Party" | awk -F'"' '{print $2}')
if [ -z "$INSTALLER_CERT" ]; then
  echo "Error: Could not find 'Mac Installer Distribution' certificate."
  echo "Please create one in the Apple Developer Portal."
  echo "This is for signing the .pkg installer."
  exit 1
fi
echo "== Using Installer Cert: $INSTALLER_CERT =="


# Clean and build
echo "== Cleaning and building... =="
rm -rf build dist

# PyInstaller will run and use $APP_CERT to sign the .app
pyinstaller Logarithmic.spec

# Create package
echo "== Creating installer package... =="
# productbuild will now use $INSTALLER_CERT to sign the .pkg
productbuild --component dist/Logarithmic.app /Applications \
    --sign "$INSTALLER_CERT" \
    dist/Logarithmic.pkg

# Verify signatures
echo "Verifying app signature..."
codesign --verify --deep --strict --verbose=2 dist/Logarithmic.app

echo "Verifying package signature..."
pkgutil --check-signature dist/Logarithmic.pkg

echo ""
echo "== Build complete! =="
echo "App bundle: dist/Logarithmic.app"
echo "Installer package: dist/Logarithmic.pkg"
