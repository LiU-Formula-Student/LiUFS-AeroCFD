#!/usr/bin/env python3
"""Update version references for release builds.

This script updates:
- aerocfd_app/version.py (UI/display version)
- aerocfd_app/__init__.py (__version__)
- pyproject.toml ([project].version)
- pyproject.toml (Development Status classifier)
- README examples that reference wheel filenames
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def sanitize(value: str) -> str:
    text = value.strip()
    if not text:
        return "dev"
    return re.sub(r"[^0-9A-Za-z._+-]", "-", text)


def to_pep440(raw_version: str) -> str:
    """Convert tag-like version strings to a PEP 440 package version."""
    version = raw_version.strip()
    version = re.sub(r"^[vV]\.??", "", version)
    version = version.strip()
    if not version:
        return "0.0.0"

    # Simple numeric versions: 1.0, 1.2.3
    if re.fullmatch(r"\d+(?:\.\d+)*", version):
        return version

    # Pre-release tags such as 1.0-beta-2, 1.0-beta.2, 1.0-rc.1, or 1.0-beta-0.1
    match = re.fullmatch(
        r"(\d+(?:\.\d+)*)-(alpha|beta|rc)[.-]([0-9]+(?:\.[0-9]+)*)",
        version,
        flags=re.IGNORECASE,
    )
    if match:
        base, phase, number_part = match.groups()
        phase_map = {"alpha": "a", "beta": "b", "rc": "rc"}
        parts = number_part.split(".")
        pep440 = f"{base}{phase_map[phase.lower()]}{parts[0]}"
        if len(parts) > 1:
            pep440 += f".post{''.join(parts[1:])}"
        return pep440

    # Fallback: keep digits/dots and drop unsupported suffixes.
    base_match = re.match(r"(\d+(?:\.\d+)*)", version)
    if base_match:
        return base_match.group(1)
    return "0.0.0"


def classifier_for_tag(raw_version: str) -> str:
    """Return the Development Status classifier based on the release tag.

    Stable tags (e.g. v1.0.0, v1.2.3) -> 5 - Production/Stable
    Pre-release tags (e.g. v1.1.0-beta.1, v2.0.0-rc.1) -> 4 - Beta
    """
    version = raw_version.strip()
    version = re.sub(r"^[vV]", "", version)
    version = version.strip()

    if re.fullmatch(r"\d+\.\d+\.\d+", version):
        return "Development Status :: 5 - Production/Stable"

    if re.fullmatch(r"\d+\.\d+\.\d+-(alpha|beta|rc)[.-]\d+(?:\.\d+)*", version, flags=re.IGNORECASE):
        return "Development Status :: 4 - Beta"

    # Conservative default for unknown/non-release formats.
    return "Development Status :: 4 - Beta"


def replace_or_fail(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Could not update {path} using pattern: {pattern}")
    path.write_text(updated, encoding="utf-8")


def main() -> int:
    raw_version = sys.argv[1] if len(sys.argv) > 1 else "dev"
    app_version = sanitize(raw_version)
    package_version = to_pep440(raw_version)
    development_status = classifier_for_tag(raw_version)

    root = Path(__file__).resolve().parent.parent
    app_version_file = root / "aerocfd_app" / "version.py"
    app_version_file.write_text(
        '"""Application version information.\n\nThis file is updated during release builds by scripts/set_app_version.py.\n"""\n\n'
        f'APP_VERSION = "{app_version}"\n',
        encoding="utf-8",
    )

    replace_or_fail(
        root / "aerocfd_app" / "__init__.py",
        r'^__version__\s*=\s*"[^"]*"$',
        f'__version__ = "{package_version}"',
    )
    replace_or_fail(
        root / "pyproject.toml",
        r'^version\s*=\s*"[^"]*"$',
        f'version = "{package_version}"',
    )
    replace_or_fail(
        root / "pyproject.toml",
        r'^\s*"Development Status :: [^"]+",\s*$',
        f'    "{development_status}",',
    )

    wheel_pattern = f"aerocfd-{package_version}-py3-none-any.whl"
    for relative_path in [
        "README.md",
        "aerocfd_cli/README.md",
        "docs/PACKAGING.md",
    ]:
        path = root / relative_path
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"aerocfd-[0-9A-Za-z.+-]+-py3-none-any\.whl", wheel_pattern, text)
        text = re.sub(r"aerocfd_cli-[0-9A-Za-z.+-]+-py3-none-any\.whl", wheel_pattern, text)
        path.write_text(text, encoding="utf-8")

    print(f"Set app display version to: {app_version}")
    print(f"Set package version to: {package_version}")
    print(f"Set development status classifier to: {development_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
