$ErrorActionPreference = 'Stop'

$rootDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $rootDir

if (-not (Test-Path 'viewer.spec') -or ((Get-Item 'viewer.spec').Length -eq 0)) {
	throw 'viewer.spec is missing or empty.'
}

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' }

pyinstaller viewer.spec

if (-not (Test-Path 'dist')) {
	New-Item -ItemType Directory -Path 'dist' | Out-Null
}

Compress-Archive -Path 'dist/liufs-viewer/*' -DestinationPath 'dist/liufs-viewer-windows.zip' -Force

Write-Host 'Built artifact: dist/liufs-viewer-windows.zip'
