"""Tests for selector orchestration behavior."""

from __future__ import annotations

from unittest.mock import Mock

from aerocfd_app.ui.controllers.selection_orchestration import SelectionOrchestrationController


class _FakeCombo:
    def __init__(self, text: str = ""):
        self._items: list[str] = []
        self._current_index: int = -1
        self._enabled = True
        if text:
            self._items = [text]
            self._current_index = 0

    def currentText(self):
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return ""

    def blockSignals(self, _value: bool):
        return None

    def clear(self):
        self._items = []
        self._current_index = -1

    def addItem(self, item: str):
        self._items.append(item)
        if self._current_index < 0:
            self._current_index = 0

    def setCurrentText(self, text: str):
        if text in self._items:
            self._current_index = self._items.index(text)

    def setCurrentIndex(self, index: int):
        if 0 <= index < len(self._items):
            self._current_index = index

    def setEnabled(self, enabled: bool):
        self._enabled = enabled


def test_populate_items_for_dataset_preserves_previous_plane_when_available():
    window = Mock()
    window.dataset_combo = _FakeCombo("CpTot")
    window.item_combo = _FakeCombo("YY")
    window.state = Mock()
    window.state.current_datasets = {
        "CpTot": {
            "type": "cfd_images",
            "videos": {
                "XX": "xx.mp4",
                "YY": "yy.mp4",
                "ZZ": "zz.mp4",
            },
        }
    }
    window.info_label = Mock()

    controller = SelectionOrchestrationController(window)
    controller.populate_items_for_dataset()

    assert window.item_combo.currentText() == "YY"
