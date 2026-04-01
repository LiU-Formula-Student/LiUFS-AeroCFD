#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -s "viewer.spec" ]]; then
	echo "Error: viewer.spec is missing or empty." >&2
	exit 1
fi

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

rm -rf build dist
pyinstaller viewer.spec

mkdir -p dist
ditto -c -k --sequesterRsrc --keepParent dist/liufs-viewer.app dist/liufs-viewer-macos.zip

echo "Built artifact: dist/liufs-viewer-macos.zip"
