from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def _is_missing_gui_system_lib(error_message: str) -> bool:
    """Return True when import failed due to missing OS-level GUI libraries."""
    missing_markers = [
        "libEGL.so.1",
        "libGL.so.1",
        "libxcb",
        "could not load the Qt platform plugin",
    ]
    lowered = error_message.lower()
    return any(marker.lower() in lowered for marker in missing_markers)


def _is_missing_qt_python_package(exc: Exception) -> bool:
    """Return True when PySide6 itself is not installed."""
    return isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) == "PySide6"


try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication
except Exception as exc:  # pragma: no cover - platform dependent
    if _is_missing_qt_python_package(exc) or _is_missing_gui_system_lib(str(exc)):
        pytest.skip(
            "Skipping GUI viewer tests: missing system GUI libraries in CI environment",
            allow_module_level=True,
        )
    raise

from app.ui.viewer_window import ViewerWindow
from simulation_compressor.packager import DuplicateRunError


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def test_add_run_action_is_disabled_until_a_file_is_loaded() -> None:
    _app()
    window = ViewerWindow()

    try:
        assert not window.add_run_action.isEnabled()

        window.archives.open_archives["arch1"] = SimpleNamespace(file_path=Path("/tmp/example.liufs"))
        window.update_file_actions()
        assert window.add_run_action.isEnabled()

        window.archives.open_archives.clear()
        window.update_file_actions()
        assert not window.add_run_action.isEnabled()
    finally:
        window.close()


def test_add_new_run_prompts_for_duplicate_and_retries(tmp_path: Path, monkeypatch) -> None:
    _app()
    window = ViewerWindow()
    archive_path = tmp_path / "archive.liufs"
    archive_path.write_bytes(b"placeholder")
    source_dir = tmp_path / "candidate"
    source_dir.mkdir()

    captured_calls: list[dict] = []
    prompt_calls: list[str] = []
    loaded_paths: list[str] = []

    def fake_append_run_to_liufs(**kwargs):
        captured_calls.append(kwargs)
        if len(captured_calls) == 1:
            raise DuplicateRunError("candidate", ["candidate"])
        return archive_path

    def fake_get_existing_directory(*_args, **_kwargs):
        return str(source_dir)

    def fake_prompt_for_run_rename(self, suggested_name: str):
        prompt_calls.append(suggested_name)
        return "candidate_renamed"

    def fake_load_liufs_file(self, file_path: str):
        loaded_paths.append(file_path)

    monkeypatch.setattr("app.ui.widgets.panes.append_run_to_liufs", fake_append_run_to_liufs)
    monkeypatch.setattr("app.ui.viewer_window.QFileDialog.getExistingDirectory", fake_get_existing_directory)
    monkeypatch.setattr("app.ui.viewer_window.QMessageBox.critical", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.ui.viewer_window.QMessageBox.warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(ViewerWindow, "load_liufs_file", fake_load_liufs_file)
    monkeypatch.setattr(ViewerWindow, "prompt_for_run_rename", fake_prompt_for_run_rename)

    window.state.set_archive("arch1")
    window.archives.open_archives["arch1"] = SimpleNamespace(file_path=archive_path)

    try:
        window.add_new_run()
        # Process events to let worker thread complete the retry cycle
        for _ in range(500):
            QCoreApplication.processEvents()
            if loaded_paths:  # Wait for the final load to complete
                break
    finally:
        window.close()

    assert prompt_calls == ["candidate"]
    assert len(captured_calls) == 2
    assert captured_calls[0]["run_name"] is None
    assert captured_calls[1]["run_name"] == "candidate_renamed"
    assert loaded_paths == [str(archive_path)]
