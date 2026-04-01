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

## 📦 Simulation Compressor Distribution

The `simulation_compressor` CLI tool is packaged as a standalone Python package that can be installed and integrated into other applications.

### For End Users

Download the wheel (`.whl`) file from the [GitHub Releases](../../releases) page:

```bash
pip install aerocfd-1.0b0.post1-py3-none-any.whl
```

Then run:

```bash
aerocfd /path/to/simulation/folder -o output.liufs
```

### For Developers

Include in your project's `requirements.txt`:

```
aerocfd @ git+https://github.com/LiU-Formula-Student/LiUFS-AeroCFD.git#subdirectory=simulation_compressor
```

Or in `pyproject.toml`:

```toml
dependencies = [
    "aerocfd @ git+https://github.com/LiU-Formula-Student/LiUFS-AeroCFD.git#subdirectory=simulation_compressor",
]
```

Then use in your code:

```python
from simulation_compressor.packager import build_liufs
from simulation_compressor.reporting import RichReporter
from rich.console import Console

console = Console()
reporter = RichReporter(console)

archive_path = build_liufs(
    source_dir="/path/to/simulation",
    output_file="output.liufs",
    reporter=reporter,
)
```

See [simulation_compressor/README.md](simulation_compressor/README.md) for full documentation.

---

## ⚙️ Development

### Requirements

- Python 3.12
- FFmpeg
- pip

Install dependencies:

```
pip install -r requirements.txt
```

Run locally:

```
python app/main.py
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

## ⚠️ Considerations

- Compression is typically **lossy**
- Keyframe interval affects navigation speed
- Keep raw data until validated

---

## 🔮 Future Work

- Side-by-side comparison
- Timeline navigation
- Web-based viewer
- Database indexing
- Thumbnail previews

---

## 👥 Authors

LiU Formula Student – Gustav Johansson
