"""
Entry point for running the LiU FS Simulation Viewer application.

This allows the application to be run with:
    python -m app
Or directly:
    python app/__main__.py
"""

import sys
from .main import ViewerWindow
from PySide6.QtWidgets import QApplication


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    window = ViewerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
