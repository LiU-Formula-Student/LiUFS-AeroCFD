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


def test_rich_reporter_shows_install_hint_when_rich_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _block_rich_imports(monkeypatch)

    sys.modules.pop("aerocfd_cli.reporting", None)
    reporting = importlib.import_module("aerocfd_cli.reporting")

    with pytest.raises(ModuleNotFoundError, match=r"aerocfd\[cli\]"):
        reporting.RichReporter()


def test_rich_reporter_emit_serializes_stateful_progress_updates() -> None:
    reporting = importlib.import_module("aerocfd_cli.reporting")

    class DummyConsole:
        def log(self, _message: str) -> None:
            pass

    class RecordingLock:
        def __init__(self) -> None:
            self.entered = 0
            self.exited = 0

        def __enter__(self):
            self.entered += 1
            return self

        def __exit__(self, exc_type, exc, tb):
            self.exited += 1
            return False

    class RecordingProgress:
        def __init__(self) -> None:
            self.updates: list[tuple[int, dict[str, int]]] = []

        def update(self, task_id: int, **kwargs):
            self.updates.append((task_id, kwargs))

        def refresh(self) -> None:
            pass

    reporter = reporting.RichReporter(DummyConsole(), show_logs=False, show_progress=True)
    lock = RecordingLock()
    progress = RecordingProgress()
    reporter._lock = lock
    reporter._progress = progress
    reporter._task_id = 7
    reporter._task_total = 5
    reporter._completed_attempts = 2

    reporter.emit(reporting.ProgressEvent(kind="progress_advance", message="", data={"amount": 2}))

    assert lock.entered == 1
    assert lock.exited == 1
    assert progress.updates == [(7, {"completed": 4})]
