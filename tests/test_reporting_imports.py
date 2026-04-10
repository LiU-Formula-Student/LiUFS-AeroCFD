from __future__ import annotations

import builtins
import importlib
import sys

import pytest


def _block_rich_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rich" or name.startswith("rich."):
            raise ModuleNotFoundError("No module named 'rich'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)


def test_packager_import_does_not_require_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_rich_imports(monkeypatch)

    sys.modules.pop("aerocfd_cli.reporting", None)
    sys.modules.pop("aerocfd_cli.packager", None)

    packager = importlib.import_module("aerocfd_cli.packager")
    reporting = importlib.import_module("aerocfd_cli.reporting")

    assert hasattr(packager, "build_liufs")
    assert reporting.NullReporter is not None


def test_rich_reporter_shows_install_hint_when_rich_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_rich_imports(monkeypatch)

    sys.modules.pop("aerocfd_cli.reporting", None)
    reporting = importlib.import_module("aerocfd_cli.reporting")

    with pytest.raises(ModuleNotFoundError, match=r"aerocfd\[cli\]"):
        reporting.RichReporter()
