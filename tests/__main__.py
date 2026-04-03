"""Run the full test suite with `python -m tests`."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    try:
        import pytest
    except ModuleNotFoundError:
        print("pytest is not installed in the active environment.")
        print("Install it with: python -m pip install pytest")
        return 1

    return pytest.main([str(Path(__file__).resolve().parent), "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
