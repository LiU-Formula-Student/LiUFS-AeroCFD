#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
	PYTHON_BIN="$ROOT_DIR/venv/bin/python"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
	PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
	PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
	PYTHON_BIN="python3"
else
	echo "Error: neither python nor python3 was found in PATH." >&2
	exit 1
fi

if [[ ! -s "viewer.spec" ]]; then
	echo "Error: viewer.spec is missing or empty." >&2
	exit 1
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" -m pip install pyinstaller

rm -rf build dist
"$PYTHON_BIN" -m PyInstaller viewer.spec

mkdir -p dist

APP_PATH="dist/liufs-viewer.app"
if [[ ! -d "$APP_PATH" ]]; then
	APP_PATH="dist/liufs-viewer"
fi

if [[ -n "${APPLE_CERT_BASE64:-}" && -n "${APPLE_CERT_PASSWORD:-}" && -n "${APPLE_SIGN_IDENTITY:-}" ]]; then
	KEYCHAIN_NAME="liufs-build.keychain"
	KEYCHAIN_PASSWORD="${APPLE_KEYCHAIN_PASSWORD:-liufs-build-keychain-password}"
	CERT_PATH="$(mktemp -t liufs-signing-cert).p12"

	echo "$APPLE_CERT_BASE64" | base64 --decode > "$CERT_PATH"

	security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"
	security set-keychain-settings -lut 21600 "$KEYCHAIN_NAME"
	security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"
	security list-keychains -d user -s "$KEYCHAIN_NAME" $(security list-keychains -d user | sed 's/[\"]//g')
	security import "$CERT_PATH" -k "$KEYCHAIN_NAME" -P "$APPLE_CERT_PASSWORD" -T /usr/bin/codesign -T /usr/bin/security
	security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"

	codesign --force --deep --options runtime --sign "$APPLE_SIGN_IDENTITY" "$APP_PATH"

	rm -f "$CERT_PATH"
	security delete-keychain "$KEYCHAIN_NAME"

	echo "macOS app signed successfully."
else
	echo "macOS signing secrets not provided; building unsigned artifact."
fi

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" dist/liufs-viewer-macos.zip

if [[ -n "${APPLE_ID:-}" && -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" && -n "${APPLE_TEAM_ID:-}" ]]; then
	xcrun notarytool submit dist/liufs-viewer-macos.zip \
		--apple-id "$APPLE_ID" \
		--password "$APPLE_APP_SPECIFIC_PASSWORD" \
		--team-id "$APPLE_TEAM_ID" \
		--wait

	if [[ -d "$APP_PATH" && "$APP_PATH" == *.app ]]; then
		xcrun stapler staple "$APP_PATH"
		ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" dist/liufs-viewer-macos.zip
	fi

	echo "macOS notarization completed."
else
	echo "macOS notarization secrets not provided; skipping notarization."
fi

echo "Built artifact: dist/liufs-viewer-macos.zip"
