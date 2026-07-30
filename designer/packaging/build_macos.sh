#!/usr/bin/env bash
# Build, sign, notarize and package FigSpec Designer (arm64).
# Usage: ./build_macos.sh [--skip-sign] [--release]
# Env (required unless --skip-sign):
#   FIGSPEC_SIGN_IDENTITY   e.g. "Developer ID Application: NAME (TEAMID)"
#   FIGSPEC_NOTARY_PROFILE  notarytool keychain profile name
set -euo pipefail
cd "$(dirname "$0")"

SKIP_SIGN=0; RELEASE=0
for arg in "$@"; do
  case "$arg" in
    --skip-sign) SKIP_SIGN=1 ;;
    --release) RELEASE=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' ../figspec_designer/__init__.py)
APP="dist/FigSpec Designer.app"
DMG="FigSpec-Designer-${VERSION}-arm64.dmg"

if [ "$SKIP_SIGN" -eq 0 ]; then
  : "${FIGSPEC_SIGN_IDENTITY:?set FIGSPEC_SIGN_IDENTITY or use --skip-sign}"
  : "${FIGSPEC_NOTARY_PROFILE:?set FIGSPEC_NOTARY_PROFILE or use --skip-sign}"
fi

echo "==> build venv (uv, python 3.11)"
uv venv --python 3.11 build-env --clear
source build-env/bin/activate
uv pip install --quiet ../../ ../ pyinstaller Pillow
# iCloud-synced checkouts (e.g. under ~/Desktop) get UF_HIDDEN reapplied to
# files on write, which makes Qt's plugin scanner treat plugin dylibs as
# invisible (breaks the venv). Clear the flag recursively after installing.
chflags -R nohidden build-env/ 2>/dev/null || true

echo "==> icon"
python make_icon.py

echo "==> pyinstaller"
rm -rf build dist
pyinstaller --noconfirm figspec-designer.spec
# shutil.copy2/copystat preserves BSD flags, so the .app bundle can inherit
# UF_HIDDEN from site-packages under iCloud sync; clear it here too.
chflags -R nohidden dist/ 2>/dev/null || true

echo "==> smoke test"
"./dist/FigSpec Designer/FigSpec Designer" --smoke

if [ "$SKIP_SIGN" -eq 0 ]; then
  echo "==> codesign"
  codesign --deep --force --options runtime --timestamp \
    --sign "$FIGSPEC_SIGN_IDENTITY" "$APP"
  codesign --verify --deep --strict "$APP"

  echo "==> notarize"
  ditto -c -k --keepParent "$APP" "dist/notarize.zip"
  xcrun notarytool submit "dist/notarize.zip" \
    --keychain-profile "$FIGSPEC_NOTARY_PROFILE" --wait
  xcrun stapler staple "$APP"
fi

echo "==> dmg"
rm -f "$DMG"
create-dmg --volname "FigSpec Designer" --window-size 500 320 \
  --icon-size 100 --app-drop-link 350 130 "$DMG" "$APP" \
  || { echo "create-dmg failed (brew install create-dmg)"; exit 1; }

if [ "$RELEASE" -eq 1 ]; then
  gh release create "designer-v${VERSION}" --draft \
    --title "FigSpec Designer ${VERSION}" "$DMG"
fi
echo "done: $DMG"
