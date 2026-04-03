"""
Entry point for running the LiU FS Simulation Viewer application.

This allows the application to be run with:
    python -m app
Or directly:
    python app/__main__.py
"""

from .main import main


if __name__ == "__main__":
    raise SystemExit(main())
