# aerocfd Distribution & Packaging

This document describes how `aerocfd` is packaged as one distribution with optional extras.

## Overview

`aerocfd` is built as one distributable package that can be installed in different modes:
1. **CLI mode** - `pip install "aerocfd[cli]"`
2. **App mode** - `pip install "aerocfd[app]"`
3. **Full mode** - `pip install "aerocfd[full]"`

## Package Structure

```
AeroCFD/
├── pyproject.toml              # Package metadata and build config
├── MANIFEST.in                 # Distribution file inclusion rules
├── dist/                       # Built distributions
│   ├── aerocfd-1.0.0-py3-none-any.whl
│   └── aerocfd-1.0b0.post7.tar.gz
├── aerocfd_cli/                # CLI package source
│   ├── __init__.py
│   ├── __main__.py
│   ├── encoder.py
│   ├── packager.py
│   ├── reporting.py
│   ├── scanner.py
│   └── README.md
└── aerocfd_app/                # Desktop app package source
   ├── main.py
   ├── ui/
   └── ...
```

## Building

### Building the Wheel and Source Distribution

From the project root:

```bash
# Install build tools
pip install build

# Build both wheel (.whl) and source distribution (.tar.gz)
pyproject-build
```

Artifacts are created in the `dist/` directory.

### Manual Testing of the Built Wheel

```bash
# Install from local wheel (full runtime)
pip install "dist/aerocfd-1.0.0-py3-none-any.whl[full]"

# Test the CLI command
aerocfd --help

# Use the Python API
python -c "from aerocfd_cli.packager import build_liufs; print(build_liufs.__doc__)"
```

## Distribution Methods

### 1. **PyPI (Recommended)**

The package is automatically published to PyPI from the release workflow.

```bash
pip install "aerocfd[cli]"
pip install "aerocfd[app]"
pip install "aerocfd[full]"
```

Project page: https://pypi.org/project/aerocfd/

### 2. **GitHub Releases**

The CI/CD pipeline automatically builds and attaches wheels to GitHub releases:

1. Create a GitHub release (this triggers the workflow)
2. The CI automatically:
   - Builds desktop application distributions
   - Builds the `aerocfd` wheel and source distribution
   - Publishes the package to PyPI (Trusted Publisher via OIDC)
   - Attaches all artifacts to the release
3. Users download from the release page

### 3. **Direct Installation from Repository**

Users can install directly from the repository:

```bash
# Install from git (requires git to be installed)
pip install "aerocfd @ git+https://github.com/LiU-Formula-Student/LiUFS-AeroCFD.git"

# Install with extras from git
pip install "aerocfd[full] @ git+https://github.com/LiU-Formula-Student/LiUFS-AeroCFD.git"
```

### 4. **Local Installation**

For testing locally:

```bash
# From project root
pip install -e ".[full]"

# This allows modifications to be reflected without reinstalling
```

## Usage After Installation

### As a CLI Tool

```bash
aerocfd /path/to/simulation -o output.liufs --fps 12
```

### As a Library

```python
from aerocfd_cli.packager import build_liufs
from aerocfd_cli.reporting import RichReporter
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
**Version:** `1.0b0.post7`
**Python:** `>=3.12`
**License:** MIT
**Default dependencies:** none

**Optional extras:**
   - `cli`: `opencv-python`, `rich`
   - `app`: `opencv-python`, `PySide6`
   - `full`: `opencv-python`, `rich`, `PySide6`

### CLI Entry Point

The package provides a console script entry point:

```
[console_scripts]
aerocfd = aerocfd_cli.__main__:main
```

This is automatically available after installation via pip.

## CI/CD Integration

### Release Workflow (`.github/workflows/release.yml`)

On release publication:
1. Builds desktop applications (Windows, macOS, Linux)
2. Builds `aerocfd` wheel and source distribution
3. Publishes package artifacts to PyPI via Trusted Publisher
4. Attaches all artifacts to the GitHub release

### CI Workflow (`.github/workflows/ci.yml`)

On push/PR to `main` and `develop`:
1. Runs component tests
2. Builds the `aerocfd` package
3. Verifies wheel contents

## Development

### Installing in Development Mode

```bash
# From project root, install with dev dependencies
pip install -e ".[full,dev]"
```

This installs:
- The package in editable mode (changes to source reflect immediately)
- Optional dependencies: `pytest`, `pytest-cov`, `black`, `ruff`

### Building the Documentation

To view the entry point details:

```bash
python -c "import aerocfd_cli.__main__; help(aerocfd_cli.__main__.main)"
```

## Troubleshooting

### "aerocfd command not found"

Ensure the package is installed:
```bash
pip show aerocfd
```

If not installed, install from wheel or git:
```bash
pip install /path/to/aerocfd-1.0.0-py3-none-any.whl
```

### Import Errors After Installation

If you get `ModuleNotFoundError: No module named 'aerocfd_cli'`:

1. Verify installation: `pip show aerocfd`
2. Reinstall: `pip install --force-reinstall "aerocfd[full]"` or `pip install -e ".[full]"`
3. Check Python version: must be Python 3.12+

### Wheel Build Fails

Ensure build tools are installed:
```bash
pip install --upgrade build setuptools wheel
```

Then rebuild:
```bash
pyproject-build
```

## Next Steps

1. **Documentation**
   - Full API documentation (docstrings)
   - Usage examples in `aerocfd_cli/README.md`
   - Integration guide for other projects

2. **Testing**
   - Add unit tests in `tests/` directory
   - Add integration tests for build end-to-end
