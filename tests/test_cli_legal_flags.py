from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _block_rich_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rich" or name.startswith("rich."):
            raise ModuleNotFoundError("No module named 'rich'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)


def _block_cv2_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cv2":
            raise ModuleNotFoundError("No module named 'cv2'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_license_flag_works_without_rich_and_without_source(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _block_rich_imports(monkeypatch)
    sys.modules.pop("aerocfd_cli.__main__", None)
    cli = importlib.import_module("aerocfd_cli.__main__")

    exit_code = cli.main(["--license"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GPL-3.0-only" in captured.out
    assert "Use --license-full to show the full text." in captured.out
    assert captured.err == ""


def test_main_prints_license_when_cv2_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _block_cv2_imports(monkeypatch)
    sys.modules.pop("aerocfd_cli.packager", None)
    sys.modules.pop("aerocfd_cli.__main__", None)

    cli_main = importlib.import_module("aerocfd_cli.__main__")

    exit_code = cli_main.main(["--license"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "GPL-3.0-only" in captured.out


def test_main_prints_version_when_cv2_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _block_cv2_imports(monkeypatch)
    sys.modules.pop("aerocfd_cli.packager", None)
    sys.modules.pop("aerocfd_cli.__main__", None)

    cli_main = importlib.import_module("aerocfd_cli.__main__")

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["--version"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("aerocfd ")


def test_license_full_flag_prints_full_text(capsys: pytest.CaptureFixture[str]) -> None:
    sys.modules.pop("aerocfd_cli.__main__", None)
    cli = importlib.import_module("aerocfd_cli.__main__")

    exit_code = cli.main(["--license-full"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GNU GENERAL PUBLIC LICENSE" in captured.out
    assert "Version 3, 29 June 2007" in captured.out
    assert captured.err == ""


def test_copyright_flag_prints_copyright_notice(capsys: pytest.CaptureFixture[str]) -> None:
    sys.modules.pop("aerocfd_cli.__main__", None)
    cli = importlib.import_module("aerocfd_cli.__main__")

    exit_code = cli.main(["--copyright"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Copyright (C) 2026 LiU Formula Student" in captured.out
    assert captured.err == ""
