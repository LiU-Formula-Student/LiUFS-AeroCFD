# Development and Release Workflow

This document describes the team workflow for developing, validating, and releasing the LiU FS Viewer.

## Branch Strategy

- **feature branches**: day-to-day development work (`feature/<name>`)
- **develop**: integration branch for automated checks
- **main**: stable branch for manual validation and release preparation

Typical flow:
1. Create a feature branch from `develop`
2. Open a PR into `develop`
3. Let CI run automatically
4. Merge feature PR after checks pass
5. When ready to deliver, merge `develop` into `main`
6. Validate manually from `main`
7. Create and publish a GitHub Release with a new version tag (for example `v1.2.0`)

## CI on `develop`

Workflow file: `.github/workflows/ci.yml`

Triggers:
- Push to `develop`
- Pull request targeting `develop`

What it does:
- Sets up Python 3.12
- Installs dependencies from `requirements.txt`
- Runs component checks via `python test_components.py`

Goal:
- Catch integration issues early before code reaches `main`

## Release Build Pipeline

Workflow file: `.github/workflows/release.yml`

Trigger:
- GitHub Release event: `published`

Important:
- The release should have a semantic version tag, such as `v1.0.0`
- Publishing the Release starts cross-platform builds automatically

### Build targets

- **Windows** (`windows-latest`) → `dist/liufs-viewer-windows.zip`
- **macOS** (`macos-latest`) → `dist/liufs-viewer-macos.zip`
- **Linux** (`ubuntu-latest`) → `dist/liufs-viewer-linux.tar.gz`

Build scripts used:
- `scripts/build_windows.ps1`
- `scripts/build_macos.sh`
- `scripts/build_linux.sh`

### Packaging and upload

The release workflow:
1. Builds artifacts in parallel (matrix job)
2. Uploads artifacts from each OS job
3. Downloads all artifacts in a publish job
4. Attaches the files to the GitHub Release automatically

## Local Build Commands

Run from repository root.

Linux:
```bash
./scripts/build_linux.sh
```

macOS:
```bash
./scripts/build_macos.sh
```

Windows (PowerShell):
```powershell
./scripts/build_windows.ps1
```

## PyInstaller Configuration

- File: `viewer.spec`
- Defines the desktop app build using `app/main.py`
- Produces onedir output named `liufs-viewer`

## Notes

- `ffmpeg` is required for compressor-related functionality and should be available on build/runtime environments where needed.
- If builds fail, first check workflow logs for dependency or platform-specific packaging errors.

## Code Signing (optional, recommended)

You can configure signing secrets in GitHub so release artifacts are signed automatically.

### Windows signing secrets

- `WINDOWS_SIGN_CERT_BASE64` (base64-encoded `.pfx` certificate)
- `WINDOWS_SIGN_CERT_PASSWORD`

Behavior:
- If both secrets are present, `scripts/build_windows.ps1` signs `liufs-viewer.exe` with `signtool`.
- If not present, the build still succeeds but produces an unsigned artifact.

### macOS signing and notarization secrets

- `APPLE_CERT_BASE64` (base64-encoded Developer ID `.p12` certificate)
- `APPLE_CERT_PASSWORD`
- `APPLE_SIGN_IDENTITY` (for example `Developer ID Application: Your Name (TEAMID)`)
- `APPLE_TEAM_ID`
- `APPLE_ID` (Apple account email used for notarization)
- `APPLE_APP_SPECIFIC_PASSWORD`

Behavior:
- If signing secrets are present, `scripts/build_macos.sh` signs the `.app` bundle.
- If notarization secrets are also present, the workflow submits the ZIP for notarization and staples the app.
- If missing, the build still succeeds but artifact is unsigned/unnotarized.
