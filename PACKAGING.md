# simulation_compressor Distribution & Packaging

This document describes how `simulation_compressor` is packaged and distributed as a standalone Python package.

## Overview

`simulation_compressor` is built as a distributable Python package that can be:
1. **Installed as a CLI tool** - for end-users who want to use the packager independently
2. **Installed as a library** - for developers building applications that need CFD packaging functionality

## Package Structure

```
AeroCFD/
├── pyproject.toml              # Package metadata and build config
├── MANIFEST.in                 # Distribution file inclusion rules
├── dist/                       # Built distributions
│   ├── aerocfd-1.0b0.post4-py3-none-any.whl
│   └── simulation_compressor-0.1.0.tar.gz
└── simulation_compressor/      # Package source
    ├── __init__.py
    ├── __main__.py
    ├── encoder.py
    ├── packager.py
    ├── reporting.py
    ├── scanner.py
    └── README.md
```

## Building

### Building the Wheel and Source Distribution

From the project root:

```bash
# Install build tools
pip install build

# Build both wheel (.whl) and source distribution (.tar.gz)
python -m build
```

Artifacts are created in the `dist/` directory.

### Manual Testing of the Built Wheel

```bash
# Install from local wheel
pip install dist/aerocfd-1.0b0.post4-py3-none-any.whl

# Test the CLI command
liufs-compressor --help

# Use the Python API
python -c "from simulation_compressor.packager import build_liufs; print(build_liufs.__doc__)"
```

## Distribution Methods

### 1. **GitHub Releases (Recommended)**

The CI/CD pipeline automatically builds and attaches wheels to GitHub releases:

1. Create a GitHub release (this triggers the workflow)
2. The CI automatically:
   - Builds desktop application distributions
   - Builds the `simulation_compressor` wheel and source distribution
   - Attaches all artifacts to the release
3. Users download from the release page

### 2. **Direct Installation from Repository**

Users can install directly from the repository:

```bash
# Install from git (requires git to be installed)
pip install git+https://github.com/LiUFS/AeroCFD.git

# Or install editable for development
pip install -e git+https://github.com/LiUFS/AeroCFD.git#egg=simulation_compressor
```

### 3. **Local Installation**

For testing locally:

```bash
# From project root
pip install -e .

# This allows modifications to be reflected without reinstalling
```

## Usage After Installation

### As a CLI Tool

```bash
liufs-compressor /path/to/simulation -o output.liufs --fps 12
```

### As a Library

```python
from simulation_compressor.packager import build_liufs
from simulation_compressor.reporting import RichReporter
from rich.console import Console

console = Console()
reporter = RichReporter(console)

archive = build_liufs(
    source_dir="/path/to/simulation",
    output_file="output.liufs",
    fps=12,
    extension="mp4",
    webp_quality=80,
    reporter=reporter
)
print(f"Created: {archive}")
```

## Package Metadata

**Name:** `aerocfd`
**Version:** `0.1.0`
**Python:** `>=3.12`
**License:** MIT
**Dependencies:**
  - `opencv-python>=4.8.0`
  - `rich>=13.0.0`

### CLI Entry Point

The package provides a console script entry point:

```
[console_scripts]
aerocfd = simulation_compressor.__main__:main
```

This is automatically available after installation via pip.

## CI/CD Integration

### Release Workflow (`.github/workflows/release.yml`)

On release publication:
1. Builds desktop applications (Windows, macOS, Linux)
2. Builds `simulation_compressor` wheel and source distribution
3. Attaches all artifacts to the GitHub release

### CI Workflow (`.github/workflows/ci.yml`)

On push/PR to `develop`:
1. Runs component tests
2. Builds the `simulation_compressor` package
3. Verifies wheel contents

## Development

### Installing in Development Mode

```bash
# From project root, install with dev dependencies
pip install -e ".[dev]"
```

This installs:
- The package in editable mode (changes to source reflect immediately)
- Optional dependencies: `pytest`, `pytest-cov`, `black`, `ruff`

### Building the Documentation

To view the entry point details:

```bash
python -c "import simulation_compressor.__main__; help(simulation_compressor.__main__.main)"
```

## Troubleshooting

### "liufs-compressor command not found"

Ensure the package is installed:
```bash
pip list | grep simulation
```

If not installed, install from wheel or git:
```bash
pip install /path/to/aerocfd-1.0b0.post4-py3-none-any.whl
```

### Import Errors After Installation

If you get `ModuleNotFoundError: No module named 'simulation_compressor'`:

1. Verify installation: `pip show simulation-compressor`
2. Reinstall: `pip reinstall -r requirements` or `pip install -e .`
3. Check Python version: must be Python 3.12+

### Wheel Build Fails

Ensure build tools are installed:
```bash
pip install --upgrade build setuptools wheel
```

Then rebuild:
```bash
python -m build
```

## Next Steps

1. **Publish to PyPI** (optional)
   - Create PyPI account
   - Build and upload: `python -m twine upload dist/*`
   - Then users can: `pip install simulation-compressor`

2. **Documentation**
   - Full API documentation (docstrings)
   - Usage examples in `simulation_compressor/README.md`
   - Integration guide for other projects

3. **Testing**
   - Add unit tests in `tests/` directory
   - Add integration tests for build end-to-end
