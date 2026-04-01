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

$exePath = 'dist/liufs-viewer/liufs-viewer.exe'

if ($env:WINDOWS_SIGN_CERT_BASE64 -and $env:WINDOWS_SIGN_CERT_PASSWORD) {
	if (-not (Get-Command signtool -ErrorAction SilentlyContinue)) {
		throw 'signtool was not found on PATH; cannot sign Windows build.'
	}

	$certPath = Join-Path $env:TEMP 'liufs-signing-cert.pfx'
	[IO.File]::WriteAllBytes($certPath, [Convert]::FromBase64String($env:WINDOWS_SIGN_CERT_BASE64))

	& signtool sign /fd SHA256 /f $certPath /p $env:WINDOWS_SIGN_CERT_PASSWORD /tr http://timestamp.digicert.com /td SHA256 $exePath
	if ($LASTEXITCODE -ne 0) {
		Remove-Item -Force $certPath -ErrorAction SilentlyContinue
		throw 'Windows code signing failed.'
	}

	Remove-Item -Force $certPath -ErrorAction SilentlyContinue
	Write-Host 'Windows executable signed successfully.'
} else {
	Write-Host 'Windows signing secrets not provided; building unsigned artifact.'
}

if (-not (Test-Path 'dist')) {
	New-Item -ItemType Directory -Path 'dist' | Out-Null
}

Compress-Archive -Path 'dist/liufs-viewer/*' -DestinationPath 'dist/liufs-viewer-windows.zip' -Force

Write-Host 'Built artifact: dist/liufs-viewer-windows.zip'
