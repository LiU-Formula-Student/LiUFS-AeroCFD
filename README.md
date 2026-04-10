# LiU FS Simulation Viewer (`.liufs`)

A cross-platform desktop application and file format for efficiently storing, sharing, and visualizing CFD simulation results within LiU Formula Student.

## 🚀 Motivation

CFD simulations in LiU FS generate **large volumes of images**, especially cutplane sequences. This leads to:

- Massive storage usage (TB scale)
- Hitting Google Drive **500k item limits**
- Difficult navigation between simulation results
- Inefficient sharing and comparison between runs

This project solves that by:

- Compressing image sequences into **video-based representations**
- Packaging simulations into a **single file format (`.liufs`)**
- Providing a **lightweight viewer application** for fast navigation

---

## 📦 Key Features

### Storage & Compression
- Convert cutplane image sequences → **video (inter-frame compression)**
- Reduce storage by up to **~100x** (depending on data)
- Collapse thousands of files into **one `.liufs` file**

### Simulation Packaging
- Each simulation stored as a **single portable archive**
- Supports:
  - Multiple **versions / conditions**
  - Multiple **image densities** (`images_5`, `images_10`, etc.)
  - Structured categories:
    - `CpPlotFW`, `CpPlotRW`
    - `cutplanes` (`cp`, `cptot`, `hel`, `lic`)
    - `iso`, `surf`

### Viewer Application
- Cross-platform (Windows, macOS, Linux)
- No installation required (portable builds)
- Fast navigation:
  - Arrow keys for plane stepping
  - Sequence playback
- Organized browsing of:
  - runs
  - categories
  - image groups

---

## 🧠 Concept

Instead of storing:

286 images → 286 files

We store:

286 images → 1 video (with delta compression)

This leverages the same principle as video codecs:

- First frame = full image (keyframe)
- Subsequent frames = differences (delta frames)

---

## 📁 `.liufs` File Format

A `.liufs` file is a **compressed container (ZIP-based)** containing:

```
simulation.liufs
├── manifest.json
├── preview.png
├── versions/
│   ├── run_01/
│   │   ├── metadata.json
│   │   ├── CpPlotFW/
│   │   ├── CpPlotRW/
│   │   ├── sequences/
│   │   │   ├── cutplanes_cp.mp4
│   │   │   ├── cutplanes_cptot.mp4
│   │   │   ├── cutplanes_hel.mp4
│   │   │   └── cutplanes_lic.mp4
│   │   ├── iso/
│   │   └── surf/
│   └── run_02/
```

---

## 🖥️ Viewer Application

### Tech Stack
- Python
- PySide6 (Qt)
- PyInstaller (packaging)

### Capabilities
- Open `.liufs` files
- Browse:
  - versions
  - categories
  - image groups
- View:
  - videos (cutplanes)
  - static images (graphs, iso, surf)
- Navigate with keyboard:
  - ← / → : change plane
  - ↑ / ↓ : change dataset/category

---

## 📥 Installation / Usage

### No installation required

Download the appropriate build for your OS:

- Windows → `.zip`
- macOS → `.zip` (`.app`)
- Linux → `.tar.gz` or AppImage

Then:

```
# Example (Linux/macOS)
tar -xzf liufs-viewer-linux.tar.gz
./liufs-viewer
```

or on Windows:

Extract ZIP → Run .exe

---

## 📦 Python Package Installation (`aerocfd`)

The project is distributed as one package (`aerocfd`) with optional extras:

- `aerocfd[cli]` → CLI dependencies
- `aerocfd[app]` → desktop app dependencies
- `aerocfd[full]` → CLI + desktop app dependencies

### For End Users

Install from package index:

PyPI project page: https://pypi.org/project/aerocfd/

```bash
pip install "aerocfd[cli]"
pip install "aerocfd[app]"
pip install "aerocfd[full]"
```

Or install from a release artifact:

```bash
pip install "aerocfd-1.0.1-py3-none-any.whl[full]"
```

Then run:

```bash
aerocfd /path/to/simulation/folder -o output.liufs
```

### For Developers

Install editable with full runtime + development dependencies:

```bash
pip install -e ".[full,dev]"
```

Then use in your code:

```python
from aerocfd_cli.packager import build_liufs
from aerocfd_cli.reporting import RichReporter
from rich.console import Console

console = Console()
reporter = RichReporter(console)

archive_path = build_liufs(
    source_dir="/path/to/simulation",
    output_file="output.liufs",
    reporter=reporter,
)
```

See [aerocfd_cli/README.md](aerocfd_cli/README.md) for full documentation.

---

## ✅ Supported Platforms

| Platform  | Python | Status      |
|-----------|--------|------------|
| Windows 10/11 | 3.12+  | ✅ Tested  |
| macOS 12+     | 3.12+  | ✅ Tested  |
| Linux (Ubuntu 22.04+) | 3.12+  | ✅ Tested  |

**Minimum Requirements:**
- Python 3.12+
- FFmpeg 4.4+ (for encoding)
- 4 GB RAM recommended
- Modern GPU optional (video playback)

---

## 🧪 Post-Install Smoke Tests

After installing, verify the installation with:

```bash
# CLI smoke test
aerocfd --help

# Desktop app smoke test (requires display/X11)
python -m aerocfd_app
```

Expected output:
- `aerocfd --help` → shows CLI options for packaging simulations
- `python -m aerocfd_app` → launches GUI viewer window

If you encounter import errors after install, reinstall with:
```bash
pip install --force-reinstall "aerocfd[full]"
```

---

## ⚙️ Development

### Requirements

- Python 3.12
- FFmpeg
- pip

Install dependencies:

```
pip install -e ".[full,dev]"
```

Run locally:

```
python -m aerocfd_app
```

---

## 🏗️ Build

Using PyInstaller:

```
pyinstaller viewer.spec
```

---

## 🔄 CI/CD

GitHub Actions pipeline:

- Builds for:
  - Windows
  - macOS
  - Linux
- Triggered on:
  - tag (`v*`) or merge to `main`
- Outputs:
  - downloadable artifacts
  - GitHub Release with binaries

---

## 📊 Storage Impact

Observed example:

- 275 GB images → 2.0 GB compressed
- ~140x reduction

---

## 👥 Authors

LiU Formula Student – Gustav Johansson
