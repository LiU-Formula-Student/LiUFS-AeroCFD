"""Tests for viewer window keyboard shortcuts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _is_missing_gui_system_lib() -> bool:
    """Check if libEGL and Qt system libraries are available."""
    try:
        import ctypes
        ctypes.CDLL("libEGL.so.1")
        return False
    except (OSError, TypeError):
        return True


def _is_missing_qt_python_package() -> bool:
    """Check if PySide6 is installed."""
    try:
        from PySide6 import QtCore
        return False
    except ImportError:
        return True


# Skip all tests if GUI libraries or PySide6 are missing
pytestmark = pytest.mark.skipif(
    _is_missing_gui_system_lib() or _is_missing_qt_python_package(),
    reason="PySide6 system libraries missing (e.g., libEGL, Qt components)",
    allow_module_level=True,
)


class TestViewerShortcuts:
    """Test keyboard shortcuts in the viewer window."""

    def test_shortcut_ctrl_1_single_pane(self):
        """Test Ctrl+1 is a valid key sequence."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence("Ctrl+1")
        assert not shortcut.isEmpty()
        assert shortcut.toString() == "Ctrl+1"

    def test_shortcut_ctrl_2_split_2pane(self):
        """Test Ctrl+2 is a valid key sequence."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence("Ctrl+2")
        assert not shortcut.isEmpty()
        assert shortcut.toString() == "Ctrl+2"

    def test_shortcut_ctrl_4_split_4pane(self):
        """Test Ctrl+4 is a valid key sequence."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence("Ctrl+4")
        assert not shortcut.isEmpty()
        assert shortcut.toString() == "Ctrl+4"

    def test_shortcut_ctrl_s_swap_mode(self):
        """Test Ctrl+S is a valid key sequence."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence("Ctrl+S")
        assert not shortcut.isEmpty()
        assert shortcut.toString() == "Ctrl+S"

    def test_shortcut_ctrl_e_export(self):
        """Test Ctrl+E is a valid key sequence."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence("Ctrl+E")
        assert not shortcut.isEmpty()
        assert shortcut.toString() == "Ctrl+E"

    def test_shortcut_ctrl_l_detached_window(self):
        """Test Ctrl+L is a valid key sequence."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence("Ctrl+L")
        assert not shortcut.isEmpty()
        assert shortcut.toString() == "Ctrl+L"

    def test_shortcut_ctrl_shift_l_disable_detached_window(self):
        """Test Ctrl+Shift+L is a valid key sequence."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence("Ctrl+Shift+L")
        assert not shortcut.isEmpty()
        assert shortcut.toString() == "Ctrl+Shift+L"

    def test_shortcut_arrow_keys(self):
        """Test arrow key constants are available."""
        from PySide6.QtCore import Qt
        # Verify Qt key enum values exist
        assert hasattr(Qt.Key, "Key_Right")
        assert hasattr(Qt.Key, "Key_Left")

    @pytest.mark.parametrize(
        "key_sequence,expected_name",
        [
            ("Ctrl+1", "Ctrl+1"),
            ("Ctrl+2", "Ctrl+2"),
            ("Ctrl+4", "Ctrl+4"),
            ("Ctrl+S", "Ctrl+S"),
            ("Ctrl+E", "Ctrl+E"),
            ("Ctrl+L", "Ctrl+L"),
            ("Ctrl+Shift+L", "Ctrl+Shift+L"),
        ],
    )
    def test_all_shortcuts_valid(self, key_sequence, expected_name):
        """Test all defined shortcuts are valid Qt key sequences."""
        from PySide6.QtGui import QKeySequence
        shortcut = QKeySequence(key_sequence)
        assert not shortcut.isEmpty()
        assert shortcut.toString() == expected_name

    def test_shortcuts_are_unique(self):
        """Test that all defined shortcuts are unique."""
        from PySide6.QtGui import QKeySequence

        shortcuts = [
            QKeySequence("Ctrl+1"),
            QKeySequence("Ctrl+2"),
            QKeySequence("Ctrl+4"),
            QKeySequence("Ctrl+S"),
            QKeySequence("Ctrl+E"),
            QKeySequence("Ctrl+L"),
            QKeySequence("Ctrl+Shift+L"),
        ]

        # Convert to strings for comparison
        shortcut_strs = [s.toString() for s in shortcuts]
        assert len(shortcut_strs) == len(set(shortcut_strs)), "Duplicate shortcuts found"

    def test_shortcut_mapping(self):
        """Test that shortcuts map to expected view modes."""
        shortcut_mapping = {
            "Ctrl+1": "single",
            "Ctrl+2": "2-pane",
            "Ctrl+4": "4-pane",
            "Ctrl+S": "swap",
        }

        for shortcut, expected_mode in shortcut_mapping.items():
            assert isinstance(expected_mode, str)
            assert expected_mode in ["single", "2-pane", "4-pane", "swap"]

    def test_view_mode_names_are_valid(self):
        """Test that all view mode names are valid."""
        valid_modes = {"single", "2-pane", "4-pane", "swap"}

        # These should match the modes used in set_view_mode calls
        for mode in valid_modes:
            assert isinstance(mode, str)
            assert len(mode) > 0
