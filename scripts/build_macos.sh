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
ditto -c -k --sequesterRsrc --keepParent dist/liufs-viewer dist/liufs-viewer-macos.zip

echo "Built artifact: dist/liufs-viewer-macos.zip"
