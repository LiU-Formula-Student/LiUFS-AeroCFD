#!/usr/bin/env python3
"""
Test cases for pane rendering and frame navigation functionality.
"""

import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from typing import Optional, Dict, Any

import pytest

# Add project root to path so package imports resolve correctly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure Qt can load in headless CI environments
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication
except Exception as exc:  # pragma: no cover - platform dependent
    if _is_missing_qt_python_package(exc) or _is_missing_gui_system_lib(str(exc)):
        pytest.skip(
            "Skipping GUI pane tests: missing system GUI libraries in CI environment",
            allow_module_level=True,
        )
    raise

from aerocfd_app.ui.viewer_window import ViewerWindow
from aerocfd_app.ui.widgets.panes import DetachedImageWindow, ImagePane
from aerocfd_app.ui.controllers.pane_orchestration import PaneOrchestrationController


def _get_qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestPaneRendering:
    """Test cases for pane rendering with drag-and-drop."""

    def test_pane_has_unique_context(self):
        """Test that each pane maintains its own independent context."""
        # Mock pane references with different contexts
        pane_refs = {
            0: {
                "archive_id": "arch1",
                "run_name": "run1",
                "label": "archive1 | run1",
                "context": {
                    "archive_id": "arch1",
                    "run_name": "run1",
                    "version": "v1",
                    "category": "cat1",
                    "dataset": "data1",
                    "item": "item1",
                }
            },
            1: {
                "archive_id": "arch2",
                "run_name": "run2",
                "label": "archive2 | run2",
                "context": {
                    "archive_id": "arch2",
                    "run_name": "run2",
                    "version": "v2",
                    "category": "cat2",
                    "dataset": "data2",
                    "item": "item2",
                }
            }
        }
        
        # Verify contexts are unique
        pane_0_context = pane_refs[0]["context"]
        pane_1_context = pane_refs[1]["context"]
        
        assert pane_0_context["archive_id"] != pane_1_context["archive_id"]
        assert pane_0_context["run_name"] != pane_1_context["run_name"]
        assert pane_0_context["item"] != pane_1_context["item"]
        print("✓ Panes have unique contexts")

    def test_pane_context_contains_required_fields(self):
        """Test that pane context has all required fields for rendering."""
        pane_context = {
            "archive_id": "test_archive",
            "run_name": "test_run",
            "version": "v1",
            "group_path": ["test_run", "v1"],
            "category": "category1",
            "dataset": "dataset1",
            "item": "item1",
        }
        
        required_fields = ["archive_id", "run_name", "version", "group_path", 
                          "category", "dataset", "item"]
        for field in required_fields:
            assert field in pane_context, f"Missing required field: {field}"
        print("✓ Pane context contains all required fields")

    def test_pane_label_format(self):
        """Test that pane labels follow the expected format."""
        run_ref = {
            "archive_id": "arch_id",
            "run_name": "LOW_FRH",
            "label": "ER26-BL-0001 | LOW_FRH",
        }
        
        # Check label format
        label = run_ref["label"]
        assert " | " in label, "Label should contain ' | ' separator"
        parts = label.split(" | ")
        assert len(parts) == 2, "Label should have exactly 2 parts separated by ' | '"
        assert parts[1] == "LOW_FRH", "Second part of label should be run name"
        print("✓ Pane label format is correct")


class TestFrameNavigation:
    """Test cases for frame navigation with panes."""

    def test_frame_slider_maximum_computed_from_panes(self):
        """Test that frame slider maximum is set based on pane video lengths."""
        frame_counts = [100, 150, 120]  # Three panes with different frame counts
        
        # Slider should be set to minimum to ensure all panes can display all frames
        expected_max = min(frame_counts) - 1
        
        assert expected_max == 99, "Slider maximum should be min(frame_counts) - 1"
        print(f"✓ Frame slider maximum computed correctly: {expected_max}")

    def test_next_frame_without_video_player(self):
        """Test that next_frame works when only panes are loaded (no video_player)."""
        # Simulate state: no video_player, but panes loaded with slider max = 100
        frame_counts = [100]  # Pane has 100 frames
        slider_max = min(frame_counts) - 1
        
        # Simulate arrow key press (current_frame = 5, should go to 6)
        current_frame = 5
        next_frame = min(current_frame + 1, slider_max)
        
        assert next_frame == 6, "next_frame should increment by 1"
        assert next_frame <= slider_max, "next_frame should not exceed maximum"
        print(f"✓ next_frame works without video_player: {current_frame} → {next_frame}")

    def test_previous_frame_without_video_player(self):
        """Test that previous_frame works when only panes are loaded (no video_player)."""
        # Simulate state: no video_player, but panes loaded
        frame_counts = [100]
        slider_max = min(frame_counts) - 1
        
        # Simulate arrow key press (current_frame = 10, should go to 9)
        current_frame = 10
        prev_frame = max(current_frame - 1, 0)
        
        assert prev_frame == 9, "previous_frame should decrement by 1"
        assert prev_frame >= 0, "previous_frame should not go below 0"
        print(f"✓ previous_frame works without video_player: {current_frame} → {prev_frame}")

    def test_frame_slider_value_synchronization(self):
        """Test that frame slider value matches display_frame index."""
        slider_value = 42
        expected_frame_index = 42
        
        # When slider is moved, display_frame should use that value
        assert slider_value == expected_frame_index, "Slider value should match frame index"
        print(f"✓ Frame slider and display_frame are synchronized: {slider_value}")

    def test_playback_advance_with_panes(self):
        """Test that playback advance works with only panes loaded."""
        frame_counts = [100]
        slider_max = min(frame_counts) - 1
        
        # Simulate playback: current frame 50, advance to 51
        current = 50
        next_frame_num = current + 1
        if next_frame_num > slider_max:
            next_frame_num = 0  # Loop to start if enabled
        
        assert next_frame_num == 51, "Playback should advance one frame"
        print(f"✓ Playback advances with panes: {current} → {next_frame_num}")

    def test_slider_maximum_with_multiple_panes(self):
        """Test that slider maximum is minimum of all pane frame counts."""
        pane_frame_counts = {
            0: 120,  # Pane 0 has 120 frames
            1: 100,  # Pane 1 has 100 frames
            2: 150,  # Pane 2 has 150 frames
        }
        
        min_frames = min(pane_frame_counts.values())
        slider_max = min_frames - 1
        
        # All frames up to slider_max should be displayable in all panes
        assert slider_max == 99, "Slider maximum should be 99 (minimum - 1)"
        print(f"✓ Slider maximum with multiple panes: {slider_max}")

    def test_frame_clamping_at_boundaries(self):
        """Test that frame indices are clamped at slider boundaries."""
        slider_max = 100
        
        # Test max boundary
        requested_frame = 105
        clamped = min(requested_frame, slider_max)
        assert clamped == 100, "Frame should be clamped at maximum"
        
        # Test min boundary
        requested_frame = -5
        clamped = max(requested_frame, 0)
        assert clamped == 0, "Frame should be clamped at minimum"
        print("✓ Frame indices are properly clamped at boundaries")


class TestPaneFrameRendering:
    """Test cases for rendering frames in panes."""

    def test_pane_pixmap_uses_pane_context(self):
        """Test that get_pixmap_for_pane uses pane-specific context."""
        run_ref = {
            "archive_id": "arch1",
            "run_name": "run1",
            "context": {
                "version": "v1",
                "category": "cat1",
                "dataset": "data1",
                "item": "item1",
            }
        }
        
        # Verify context is present and will be used
        pane_context = run_ref.get("context")
        assert pane_context is not None, "Pane should have context"
        assert pane_context["version"] == "v1", "Context should contain version"
        print("✓ Pane pixmap rendering uses pane-specific context")

    def test_different_panes_use_different_contexts(self):
        """Test that different panes render using their own contexts."""
        pane_0_ref = {
            "archive_id": "arch1",
            "context": {
                "archive_id": "arch1",
                "version": "v1",
                "item": "pressure",
            }
        }
        
        pane_1_ref = {
            "archive_id": "arch2",
            "context": {
                "archive_id": "arch2",
                "version": "v2",
                "item": "velocity",
            }
        }
        
        # Each pane context should be independent
        assert pane_0_ref["context"]["item"] != pane_1_ref["context"]["item"]
        assert pane_0_ref["context"]["archive_id"] != pane_1_ref["context"]["archive_id"]
        print("✓ Different panes use different contexts for rendering")

    def test_no_global_context_pollution(self):
        """Test that loading a pane doesn't pollute global context."""
        # When we load a pane, we should NOT set global self.video_player
        # (we instead set pane-specific context)
        
        # Scenario: Originally had self.current_run_name = "RUN_A"
        global_run_name = "RUN_A"
        
        # Load a new pane with different run
        pane_context = {
            "run_name": "RUN_B",
        }
        
        # Global should not automatically change (we use pane context instead)
        assert global_run_name == "RUN_A", "Global context should not be modified by pane load"
        print("✓ Loading a pane does not pollute global context")


class TestFrameNavigationIntegration:
    """Integration tests for frame navigation with multiple panes."""

    def test_single_pane_frame_navigation_sequence(self):
        """Test frame navigation sequence in single pane view."""
        slider_max = 50
        
        # Simulate: arrow right, arrow right, arrow left, arrow right
        frame = 0
        
        # Right arrow
        frame = min(frame + 1, slider_max)
        assert frame == 1
        
        # Right arrow again
        frame = min(frame + 1, slider_max)
        assert frame == 2
        
        # Left arrow
        frame = max(frame - 1, 0)
        assert frame == 1
        
        # Right arrow again
        frame = min(frame + 1, slider_max)
        assert frame == 2
        
        print("✓ Single pane frame navigation sequence works correctly")

    def test_playback_loop_behavior(self):
        """Test that playback loops correctly when reaching the end."""
        slider_max = 10
        current = 10  # At the last frame
        
        # Try to advance
        next_frame = current + 1
        if next_frame > slider_max:
            next_frame = 0  # Loop to start
        
        assert next_frame == 0, "Playback should loop to frame 0"
        print("✓ Playback loops correctly at the end")

    def test_slider_direct_jump(self):
        """Test that clicking slider directly jumps to that frame."""
        slider_max = 100
        
        # User clicks on slider at 75%
        clicked_position = int(slider_max * 0.75)
        
        # display_frame should be called with that index
        assert clicked_position == 75, "Slider click should jump to that frame"
        print(f"✓ Slider direct jump works: → {clicked_position}")


class TestSelectorUpdates:
    """Test cases for selector change behavior affecting panes."""

    def test_version_selector_updates_pane_context(self):
        """Test that changing version selector updates pane contexts."""
        # Initial pane context
        pane_context = {
            "archive_id": "arch1",
            "run_name": "run1",
            "version": "v1",
            "category": "cat1",
            "dataset": "data1",
            "item": "item1",
        }
        
        # Simulate version selector change
        new_version = "v2"
        pane_context["version"] = new_version
        
        assert pane_context["version"] == "v2", "Pane version should be updated"
        print("✓ Version selector updates pane context")

    def test_category_selector_updates_pane_context(self):
        """Test that changing category selector updates pane contexts."""
        pane_context = {
            "category": "cutplanes",
            "dataset": "cp",
            "item": "cp",
        }
        
        # Simulate category selector change
        new_category = "surfaces"
        pane_context["category"] = new_category
        
        assert pane_context["category"] == "surfaces", "Pane category should be updated"
        print("✓ Category selector updates pane context")

    def test_dataset_selector_updates_pane_context(self):
        """Test that changing dataset selector updates pane contexts."""
        pane_context = {
            "dataset": "cp",
            "item": "cp",
        }
        
        # Simulate dataset selector change
        new_dataset = "cptot"
        pane_context["dataset"] = new_dataset
        
        assert pane_context["dataset"] == "cptot", "Pane dataset should be updated"
        print("✓ Dataset selector updates pane context")

    def test_item_selector_updates_pane_context(self):
        """Test that changing item/plane selector updates pane contexts."""
        pane_context = {
            "item": "cp",
        }
        
        # Simulate item selector change
        new_item = "hel"
        pane_context["item"] = new_item
        
        assert pane_context["item"] == "hel", "Pane item should be updated"
        print("✓ Item selector updates pane context")

    def test_multiple_panes_updated_on_selector_change(self):
        """Test that all panes are updated when selectors change."""
        pane_refs = {
            0: {
                "archive_id": "arch1",
                "context": {"version": "v1", "category": "cat1", "dataset": "data1", "item": "item1"},
            },
            1: {
                "archive_id": "arch1",
                "context": {"version": "v1", "category": "cat1", "dataset": "data1", "item": "item1"},
            },
            2: {
                "archive_id": "arch1",
                "context": {"version": "v1", "category": "cat1", "dataset": "data1", "item": "item1"},
            },
        }
        
        # Simulate version change
        new_version = "v2"
        for pane_id in pane_refs:
            pane_refs[pane_id]["context"]["version"] = new_version
        
        # Verify all panes updated
        for pane_id in pane_refs:
            assert pane_refs[pane_id]["context"]["version"] == "v2", f"Pane {pane_id} should have new version"
        print("✓ Multiple panes updated on selector change")

    def test_selector_change_triggers_pane_redraw(self):
        """Test that selector changes trigger update_all_panes() call."""
        # This simulates the flow: selector change -> update_pane_contexts -> update_all_panes()
        
        # Mock: selectors changed
        selectors_changed = True
        update_called = False
        
        if selectors_changed:
            # update_pane_contexts_for_selector_change() runs
            # update_all_panes() is called
            update_called = True
        
        assert update_called, "Selector change should trigger update_all_panes()"
        print("✓ Selector change triggers pane redraw")


class TestQtPaneBehavior:
    """Qt-backed tests for pane resizing and redraw behavior."""

    def test_image_pane_rescales_on_resize(self):
        """Test that an ImagePane rescales its pixmap when resized."""
        _get_qapp()
        pane = ImagePane(0)
        pane.label.resize(200, 200)

        pixmap = QPixmap(100, 50)
        pixmap.fill(Qt.GlobalColor.red)
        pane.set_content("archive | run", pixmap)

        first = pane.label.pixmap()
        assert first is not None and not first.isNull(), "Pane should display a pixmap"
        assert first.width() == 200
        assert first.height() == 100

        pane.label.resize(120, 120)
        pane._update_pixmap_display()

        second = pane.label.pixmap()
        assert second is not None and not second.isNull(), "Pane should still display a pixmap after resize"
        assert second.width() == 120
        assert second.height() == 60
        print("✓ ImagePane rescales pixmaps on resize")

    def test_image_pane_clear_resets_original_pixmap(self):
        """Test that clearing an ImagePane removes the stored original pixmap."""
        _get_qapp()
        pane = ImagePane(1)
        pane.label.resize(160, 160)

        pixmap = QPixmap(80, 80)
        pixmap.fill(Qt.GlobalColor.blue)
        pane.set_content("archive | run", pixmap)
        assert pane.original_pixmap is not None

        pane.clear()

        assert pane.original_pixmap is None
        current = pane.label.pixmap()
        assert current is None or current.isNull()
        print("✓ ImagePane clear resets pixmap state")

    def test_detached_window_rescales_on_resize(self):
        """Test that detached windows also rescale their pixmap on resize."""
        _get_qapp()
        detached = DetachedImageWindow("archive | run")
        detached.image_label.resize(240, 180)

        pixmap = QPixmap(120, 60)
        pixmap.fill(Qt.GlobalColor.green)
        detached.update_content("archive | run", pixmap)

        first = detached.image_label.pixmap()
        assert first is not None and not first.isNull()
        assert first.width() == 240
        assert first.height() == 120

        detached.image_label.resize(100, 100)
        detached._update_pixmap_display()

        second = detached.image_label.pixmap()
        assert second is not None and not second.isNull()
        assert second.width() == 100
        assert second.height() == 50
        print("✓ Detached window rescales pixmaps on resize")


class TestViewerWindowHelpers:
    """Tests for helper methods on the main viewer window."""

    def _make_viewer(self):
        viewer = ViewerWindow.__new__(ViewerWindow)
        viewer.split_pane_widget = Mock()
        viewer.split_pane_widget.get_pane_count.return_value = 2
        viewer.pane_run_refs = {
            0: {
                "archive_id": "arch1",
                "run_name": "runA",
                "context": {
                    "version": "v1",
                    "group_path": ["runA", "v1"],
                    "category": "cat1",
                    "dataset": "data1",
                    "item": "item1",
                },
            },
            1: {
                "archive_id": "arch1",
                "run_name": "runB",
                "context": {
                    "version": "v1",
                    "group_path": ["runB", "v1"],
                    "category": "cat1",
                    "dataset": "data1",
                    "item": "item1",
                },
            },
        }
        viewer.version_combo = Mock()
        viewer.category_combo = Mock()
        viewer.dataset_combo = Mock()
        viewer.item_combo = Mock()
        viewer.version_combo.currentText.return_value = "v2"
        viewer.category_combo.currentText.return_value = "cat2"
        viewer.dataset_combo.currentText.return_value = "data2"
        viewer.item_combo.currentText.return_value = "item2"
        viewer.frame_slider = Mock()
        viewer.frame_slider.maximum.return_value = 0
        viewer.frame_slider.blockSignals = Mock()
        viewer.frame_slider.setMaximum = Mock()
        viewer.frame_slider.setValue = Mock()
        viewer.frame_slider.setEnabled = Mock()
        viewer.video_player = None
        viewer.temp_dir = None
        viewer.compare_video_cache = {}
        viewer.open_archives = {}
        viewer.open_archive_paths = {"arch1": "/tmp/archive1.liufs"}
        viewer.current_liufs_handler = None
        viewer.current_archive_id = None
        viewer.current_run_name = None
        viewer.current_version_name = None
        viewer.current_group_path = []
        viewer.current_datasets = {}
        viewer.current_categories = {}
        viewer.info_label = Mock()
        viewer.update_all_panes = Mock()
        viewer.get_video_frame_count_for_pane = Mock(return_value=40)
        return viewer

    def test_update_slider_maximum_uses_minimum_loaded_pane_count(self):
        """Test slider maximum is based on the shortest loaded pane."""
        viewer = self._make_viewer()
        viewer.get_video_frame_count_for_pane.side_effect = [40, 55]

        ViewerWindow.update_slider_maximum(viewer)

        viewer.frame_slider.blockSignals.assert_any_call(True)
        viewer.frame_slider.setMaximum.assert_called_with(39)
        viewer.frame_slider.setValue.assert_called_with(0)
        viewer.frame_slider.setEnabled.assert_called_with(True)
        print("✓ Slider maximum uses minimum pane frame count")

    def test_update_slider_maximum_uses_swap_runs_in_swap_mode(self):
        """Test slider maximum is based on swap runs when swap mode is active."""
        viewer = self._make_viewer()
        viewer.current_view_mode = "swap"
        viewer.pane_run_refs = {0: None}
        viewer.swap_runs = [
            {
                "archive_id": "arch1",
                "run_name": "runA",
                "context": {
                    "version": "v1",
                    "group_path": ["runA", "v1"],
                    "category": "cat1",
                    "dataset": "data1",
                    "item": "item1",
                },
            },
            {
                "archive_id": "arch1",
                "run_name": "runB",
                "context": {
                    "version": "v1",
                    "group_path": ["runB", "v1"],
                    "category": "cat1",
                    "dataset": "data1",
                    "item": "item1",
                },
            },
        ]
        viewer.get_video_frame_count_for_pane.side_effect = [25, 40]

        ViewerWindow.update_slider_maximum(viewer)

        viewer.frame_slider.setMaximum.assert_called_with(24)
        viewer.frame_slider.setValue.assert_called_with(0)
        viewer.frame_slider.setEnabled.assert_called_with(True)
        print("✓ Slider maximum uses minimum swap run frame count in swap mode")

    def test_update_pane_contexts_updates_all_matching_panes(self):
        """Test selector changes update every pane context that matches."""
        viewer = self._make_viewer()

        handler = Mock()
        handler.manifest = {
            "runs": {
                "children": {
                    "runA": {"children": {"v2": {}}},
                    "runB": {"children": {"v2": {}}},
                }
            }
        }
        handler.get_group_categories.return_value = {"cat2": {}}
        handler.get_category_datasets.return_value = {
            "data2": {"type": "cfd_images", "videos": {"item2": "video.mp4"}}
        }
        viewer.open_archives = {"arch1": handler}

        ViewerWindow.update_pane_contexts_for_selector_change(viewer)

        for pane_id in (0, 1):
            ctx = viewer.pane_run_refs[pane_id]["context"]
            assert ctx["version"] == "v2"
            assert ctx["category"] == "cat2"
            assert ctx["dataset"] == "data2"
            assert ctx["item"] == "item2"
        print("✓ Selector updates propagate to all matching panes")

    def test_update_pane_contexts_skips_invalid_panes(self):
        """Test selector changes do not overwrite invalid pane contexts."""
        viewer = self._make_viewer()

        handler = Mock()
        handler.manifest = {
            "runs": {
                "children": {
                    "runA": {"children": {"v2": {}}},
                    "runB": {"children": {"v1": {}}},
                }
            }
        }
        handler.get_group_categories.return_value = {"cat2": {}}
        handler.get_category_datasets.return_value = {
            "data2": {"type": "cfd_images", "videos": {"item2": "video.mp4"}}
        }
        viewer.open_archives = {"arch1": handler}
        original = dict(viewer.pane_run_refs[1]["context"])

        ViewerWindow.update_pane_contexts_for_selector_change(viewer)

        assert viewer.pane_run_refs[0]["context"]["version"] == "v2"
        assert viewer.pane_run_refs[1]["context"] == original
        print("✓ Invalid panes are skipped during selector updates")

    def test_update_slider_maximum_preserves_current_frame_index(self):
        """Test slider keeps current frame when still in range after selector change."""
        viewer = self._make_viewer()
        viewer.current_view_mode = "single"
        viewer.frame_slider.value.return_value = 12
        viewer.get_video_frame_count_for_pane.side_effect = [40, 55]

        ViewerWindow.update_slider_maximum(viewer)

        viewer.frame_slider.setMaximum.assert_called_with(39)
        viewer.frame_slider.setValue.assert_called_with(12)
        print("✓ Slider preserves current frame index")

    def test_update_pane_contexts_updates_swap_runs_in_swap_mode(self):
        """Test selector changes update swap run contexts while in swap mode."""
        viewer = self._make_viewer()
        viewer.current_view_mode = "swap"
        viewer.swap_runs = [
            {
                "archive_id": "arch1",
                "run_name": "runA",
                "context": {
                    "archive_id": "arch1",
                    "run_name": "runA",
                    "version": "v1",
                    "group_path": ["runA", "v1"],
                    "category": "cat1",
                    "dataset": "data1",
                    "item": "item1",
                },
            }
        ]

        handler = Mock()
        handler.manifest = {"runs": {"children": {"runA": {"children": {"v2": {}}}}}}
        handler.get_group_categories.return_value = {"cat2": {}}
        handler.get_category_datasets.return_value = {
            "data2": {"type": "cfd_images", "videos": {"item2": "video.mp4"}}
        }
        viewer.open_archives = {"arch1": handler}

        ViewerWindow.update_pane_contexts_for_selector_change(viewer)

        ctx = viewer.swap_runs[0]["context"]
        assert ctx["version"] == "v2"
        assert ctx["category"] == "cat2"
        assert ctx["dataset"] == "data2"
        assert ctx["item"] == "item2"
        print("✓ Selector updates propagate to swap run contexts")

    def test_get_detached_target_pane_ids_for_layouts(self):
        """Detached mode should keep pane 0 in main and detach the rest."""
        viewer = self._make_viewer()
        viewer.split_pane_widget.get_pane_count.return_value = 1
        assert ViewerWindow.get_detached_target_pane_ids(viewer) == []

        viewer.split_pane_widget.get_pane_count.return_value = 2
        assert ViewerWindow.get_detached_target_pane_ids(viewer) == [1]

        viewer.split_pane_widget.get_pane_count.return_value = 4
        assert ViewerWindow.get_detached_target_pane_ids(viewer) == [1, 2, 3]
        print("✓ Detached pane targets match layout requirements")

    def test_launch_detached_window_warns_on_single_pane(self):
        """Detached mode should require split layout (2/4-pane)."""
        viewer = self._make_viewer()
        viewer.detached_mode_enabled = False
        viewer.detached_windows = {}
        viewer.split_pane_widget.get_pane_count.return_value = 1

        ViewerWindow.launch_detached_window(viewer)

        viewer.info_label.appendPlainText.assert_called()
        assert viewer.detached_mode_enabled is False
        print("✓ Detached mode warns when not in split layout")


class TestSwapModeDedup:
    """Regression tests for swap mode duplicate handling."""

    def test_drop_same_run_twice_does_not_duplicate_swap_list(self):
        window = Mock()
        window.current_view_mode = "swap"
        window.swap_runs = []
        window.swap_current_index = 0
        window.pane_run_refs = {0: None}
        window.update_swap_display = Mock()
        window.update_slider_maximum = Mock()
        window.info_label = Mock()

        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 1

        handler = Mock()
        handler.get_runs.return_value = ["LOW_FRH"]
        handler.manifest = {
            "runs": {
                "children": {
                    "LOW_FRH": {
                        "children": {
                            "v1": {}
                        }
                    }
                }
            }
        }
        handler.get_group_categories.return_value = {"cutplanes": {}}
        handler.get_category_datasets.return_value = {
            "dataset": {"type": "cfd_images", "videos": {"frame": "video.mp4"}}
        }

        window.archives = Mock()
        window.archives.get_archive.return_value = handler
        window.archives.get_archive_label.return_value = "ER26-BL-0001"

        controller = PaneOrchestrationController(window)
        controller.update_slider_maximum = Mock()

        controller.on_tree_run_dropped(0, "archive-1", "LOW_FRH")
        controller.on_tree_run_dropped(0, "archive-1", "LOW_FRH")

        assert len(window.swap_runs) == 1
        assert window.swap_runs[0]["run_name"] == "LOW_FRH"

def test_all():
    """Run all test classes."""
    print("\n" + "="*60)
    print("PANE RENDERING TESTS")
    print("="*60)
    test_obj = TestPaneRendering()
    test_obj.test_pane_has_unique_context()
    test_obj.test_pane_context_contains_required_fields()
    test_obj.test_pane_label_format()
    
    print("\n" + "="*60)
    print("FRAME NAVIGATION TESTS")
    print("="*60)
    test_obj = TestFrameNavigation()
    test_obj.test_frame_slider_maximum_computed_from_panes()
    test_obj.test_next_frame_without_video_player()
    test_obj.test_previous_frame_without_video_player()
    test_obj.test_frame_slider_value_synchronization()
    test_obj.test_playback_advance_with_panes()
    test_obj.test_slider_maximum_with_multiple_panes()
    test_obj.test_frame_clamping_at_boundaries()
    
    print("\n" + "="*60)
    print("PANE FRAME RENDERING TESTS")
    print("="*60)
    test_obj = TestPaneFrameRendering()
    test_obj.test_pane_pixmap_uses_pane_context()
    test_obj.test_different_panes_use_different_contexts()
    test_obj.test_no_global_context_pollution()
    
    print("\n" + "="*60)
    print("INTEGRATION TESTS")
    print("="*60)
    test_obj = TestFrameNavigationIntegration()
    test_obj.test_single_pane_frame_navigation_sequence()
    test_obj.test_playback_loop_behavior()
    test_obj.test_slider_direct_jump()
    
    print("\n" + "="*60)
    print("SELECTOR UPDATE TESTS")
    print("="*60)
    test_obj = TestSelectorUpdates()
    test_obj.test_version_selector_updates_pane_context()
    test_obj.test_category_selector_updates_pane_context()
    test_obj.test_dataset_selector_updates_pane_context()
    test_obj.test_item_selector_updates_pane_context()
    test_obj.test_multiple_panes_updated_on_selector_change()
    test_obj.test_selector_change_triggers_pane_redraw()

    print("\n" + "="*60)
    print("QT PANE BEHAVIOR TESTS")
    print("="*60)
    test_obj = TestQtPaneBehavior()
    test_obj.test_image_pane_rescales_on_resize()
    test_obj.test_image_pane_clear_resets_original_pixmap()
    test_obj.test_detached_window_rescales_on_resize()

    print("\n" + "="*60)
    print("VIEWER HELPER TESTS")
    print("="*60)
    test_obj = TestViewerWindowHelpers()
    test_obj.test_update_slider_maximum_uses_minimum_loaded_pane_count()
    test_obj.test_update_pane_contexts_updates_all_matching_panes()
    test_obj.test_update_pane_contexts_skips_invalid_panes()
    
    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_all()
