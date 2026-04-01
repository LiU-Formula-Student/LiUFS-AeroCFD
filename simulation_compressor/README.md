# simulation_compressor

Utilities for packaging CFD simulation folders into a single `.liufs` archive.

This package scans a simulation directory tree, classifies leaf folders, and then:
- Encodes cutplane image sequences (`cfd_images`) into videos using `ffmpeg`
- Converts `3d_views` images into `.webp` for additional compression
- Writes a `manifest.json` describing packaged content
- Produces a ZIP-based `.liufs` archive

## Installation

### As a standalone CLI tool

Install from a wheel file (available in GitHub releases):

```bash
pip install aerocfd-1.0b0.post1-py3-none-any.whl
```

Or from git:

```bash
pip install git+https://github.com/LiU-Formula-Student/LiUFS-AeroCFD.git#subdirectory=simulation_compressor
```

### As a package dependency

Add to your `requirements.txt`:

```
aerocfd @ git+https://github.com/LiU-Formula-Student/LiUFS-AeroCFD.git#subdirectory=simulation_compressor
```

Or in `pyproject.toml`:

```toml
dependencies = [
  "aerocfd @ git+https://github.com/LiU-Formula-Student/LiUFS-AeroCFD.git#subdirectory=simulation_compressor",
]
```

## Requirements

- Python 3.12+
- `ffmpeg` available on `PATH`
- Dependencies automatically installed: `opencv-python`, `rich`

For development, install with optional dev dependencies from the project root:

```bash
pip install -e ".[dev]"
```

## CLI Usage

After installation, use either:

```bash
aerocfd <source_dir> [options]
```

Or from the project root (if not installed using the editable install):

```bash
python -m simulation_compressor <source_dir> [options]
```

### Options

- `-o, --output` Output `.liufs` file path (default: `<source>.liufs`)
- `--fps` FPS for generated CFD videos (default: `12`)
- `--extension` Video extension for CFD videos (default: `mp4`)
- `--webp-quality` WebP quality for `3d_views` conversion, `0-100` (default: `80`)
- `--include-unknown` Copy files from unknown leaf folders into the package

### Example

```bash
aerocfd /path/to/ER26-BL-0001 \
  --output /path/to/ER26-BL-0001.liufs \
  --fps 12 \
  --extension mp4 \
  --webp-quality 75
```

## Python API

```python
from simulation_compressor.packager import build_liufs

archive_path = build_liufs(
    source_dir="/path/to/ER26-BL-0001",
    output_file="/path/to/ER26-BL-0001.liufs",
    fps=12,
    extension="mp4",
    webp_quality=80,
    include_unknown=False,
)
print(archive_path)
```

## Folder Classification

Leaf folders are identified by filename patterns:
- `cfd_images`: files like `X10X.png`, `Y5Y.png`, `Z120Z.png`
- `3d_views`: view images like `top.png`, `front.png`, `iso_left_front_top.png`
- otherwise: `unknown`

## Notes

- If `ffmpeg` is missing, CFD video generation is skipped.
- `webp_quality` trades size for quality: lower values give smaller files.
- Output archive includes `manifest.json` with metadata and packaged file references.
