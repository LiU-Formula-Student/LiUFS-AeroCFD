"""Thin application entrypoint for the LiU FS viewer."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.viewer_window import ViewerWindow


def main() -> int:
    """Launch the Qt application and return process exit code."""
    app = QApplication(sys.argv)
    window = ViewerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
