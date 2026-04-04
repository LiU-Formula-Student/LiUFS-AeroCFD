"""Diagnostics and environment reporting utilities for bug reports."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import cv2
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion

from aerocfd_app.version import APP_VERSION
from aerocfd_app import __version__ as aerocfd_version


def collect_diagnostics(simulation_name: str = "No file loaded") -> str:
    """Collect comprehensive environment and app diagnostics for bug reports.

    Returns a formatted multi-line string suitable for copying to clipboard or issue trackers.
    """
    python_path = str(Path(sys.executable).resolve())
    opencv_version = cv2.__version__

    diagnostics = (
        "=== LiU FS Simulation Viewer - Diagnostics ===\n"
        "\n[Application]\n"
        f"App Version: {APP_VERSION}\n"
        f"Package Version: {aerocfd_version}\n"
        f"Loaded Simulation: {simulation_name}\n"
        "\n[Environment]\n"
        f"Python Version: {platform.python_version()}\n"
        f"Python Path: {python_path}\n"
        f"Platform: {platform.system()} {platform.release()}\n"
        f"Architecture: {platform.machine()}\n"
        "\n[Dependencies]\n"
        f"Qt Version: {qVersion()}\n"
        f"PySide6 Version: {pyside_version}\n"
        f"OpenCV Version: {opencv_version}\n"
        "\n[System Info]\n"
        f"Processor: {platform.processor()}\n"
        f"CPU Count: {platform.processors() if hasattr(platform, 'processors') else 'N/A'}\n"
    )

    return diagnostics.strip()
