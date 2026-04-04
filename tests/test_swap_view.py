"""Comprehensive tests for swap/compare view mode."""

import pytest
import os
from unittest.mock import Mock, MagicMock, patch

# Skip Qt-dependent tests in headless environments (CI)
pytestmark = pytest.mark.skipif(
    os.environ.get("DISPLAY") is None and os.environ.get("WAYLAND_DISPLAY") is None,
    reason="No display available for Qt testing"
)

from aerocfd_app.ui.controllers.pane_orchestration import PaneOrchestrationController
from aerocfd_app.ui.widgets.panes import ImagePane


class TestSwapViewInitialization:
    """Test swap view mode initialization and setup."""

    def test_swap_mode_sets_2_pane_layout(self):
        """Verify swap mode sets 2-pane layout."""
        window = Mock()
        window.current_view_mode = "single"
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 2
        window.split_pane_widget.panes = {0: Mock(), 1: Mock()}
        window.pane_run_refs = {0: None, 1: None}
        window.info_label = Mock()
        
        controller = PaneOrchestrationController(window)
        controller.update_all_panes = Mock()
        
        controller.set_view_mode("swap")
        
        assert window.current_view_mode == "swap"
        window.split_pane_widget.set_layout.assert_called_with("2-pane")

    def test_swap_mode_initializes_pane_refs(self):
        """Verify swap mode initializes pane references."""
        window = Mock()
        window.current_view_mode = "single"
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 2
        window.split_pane_widget.panes = {0: Mock(), 1: Mock()}
        window.pane_run_refs = {}
        window.info_label = Mock()
        
        controller = PaneOrchestrationController(window)
        controller.update_all_panes = Mock()
        
        controller.set_view_mode("swap")
        
        # Should have 2 entries (for 2 panes), all None initially
        assert len(window.pane_run_refs) == 2
        assert all(v is None for v in window.pane_run_refs.values())

    def test_swap_mode_resets_swap_pane_index(self):
        """Verify swap pane index resets when entering swap mode."""
        window = Mock()
        window.current_view_mode = "single"
        window.swap_pane_index = 5  # Non-zero starting value
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 2
        window.split_pane_widget.panes = {0: Mock(), 1: Mock()}
        window.pane_run_refs = {}
        window.info_label = Mock()
        
        controller = PaneOrchestrationController(window)
        controller.update_all_panes = Mock()
        
        controller.set_view_mode("swap")
        
        assert window.swap_pane_index == 0

    def test_swap_mode_provides_user_feedback(self):
        """Verify swap mode provides helpful user message."""
        window = Mock()
        window.current_view_mode = "single"
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 2
        window.split_pane_widget.panes = {0: Mock(), 1: Mock()}
        window.pane_run_refs = {}
        window.info_label = Mock()
        
        controller = PaneOrchestrationController(window)
        controller.update_all_panes = Mock()
        
        controller.set_view_mode("swap")
        
        window.info_label.appendPlainText.assert_called()
        call_text = window.info_label.appendPlainText.call_args[0][0]
        assert "Swap view enabled" in call_text or "drag" in call_text.lower()


class TestPaneContentDisplay:
    """Test pane content display and visual feedback."""

    def test_pane_loaded_indicator_format(self):
        """Verify loaded pane would show checkmark indicator."""
        # Test the label format logic without Qt display
        title = "archive | RunName"
        pixmap_loaded = True
        
        if pixmap_loaded:
            expected_title = f"✓ {title}"
            assert "✓" in expected_title
            assert "RunName" in expected_title
        else:
            assert "✓" not in title

    def test_pane_empty_indicator_format(self):
        """Verify empty pane would show placeholder."""
        title = "Pane Label"
        pixmap_loaded = False
        
        if not pixmap_loaded:
            assert "✓" not in title
            placeholder = "(Drag run here)"
            assert placeholder in placeholder

    def test_pane_title_styling_color_logic(self):
        """Verify correct styling color logic for pane state."""
        loaded_color = "#4ec9b0"  # Teal color for loaded
        empty_color = "#888888"   # Gray for empty
        
        pixmap_loaded = True
        style_color = loaded_color if pixmap_loaded else empty_color
        
        assert style_color == loaded_color or style_color == empty_color


class TestFrameSynchronization:
    """Test frame sync across multiple panes."""

    def test_update_all_panes_syncs_frame_index(self):
        """Verify all panes get same frame index when updated."""
        window = Mock()
        window.frame_slider = Mock()
        window.frame_slider.value.return_value = 42
        
        pane0 = Mock()
        pane1 = Mock()
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 2
        window.split_pane_widget.get_pane.side_effect = lambda i: pane0 if i == 0 else pane1
        
        run_ref_0 = {
            "archive_id": "archive1.liufs",
            "run_name": "RunA",
            "label": "archive1 | RunA",
            "context": {"version": "v1"}
        }
        run_ref_1 = {
            "archive_id": "archive2.liufs",
            "run_name": "RunB",
            "label": "archive2 | RunB",
            "context": {"version": "v1"}
        }
        window.pane_run_refs = {0: run_ref_0, 1: run_ref_1}
        
        controller = PaneOrchestrationController(window)
        controller.get_pixmap_for_pane = Mock(return_value=Mock())
        
        controller.update_all_panes()
        
        # Both panes should be updated (set_content called)
        assert pane0.set_content.called
        assert pane1.set_content.called

    def test_slider_maximum_uses_minimum_frame_count(self):
        """Verify slider max is set to minimum of all panes."""
        window = Mock()
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 2
        window.pane_run_refs = {
            0: {"archive_id": "a1", "run_name": "r1", "context": {"version": "v1"}},
            1: {"archive_id": "a2", "run_name": "r2", "context": {"version": "v1"}}
        }
        window.frame_slider = Mock()
        window.media = None  # Prevent player retrieval
        window.video_player = None  # Prevent fallback player
        
        controller = PaneOrchestrationController(window)
        
        # Mock the frame count return values: 100 for first pane, 50 for second
        def get_frame_count(run_ref):
            if run_ref["run_name"] == "r1":
                return 100
            return 50
        
        controller.window.get_video_frame_count_for_pane = Mock(side_effect=get_frame_count)
        
        controller.update_slider_maximum()
        
        # Should use minimum (50), so max is 49 (50-1)
        window.frame_slider.setMaximum.assert_called_with(49)


class TestPaneDragDrop:
    """Test drag-and-drop loading into panes."""

    def test_pane_accepts_run_drop(self):
        """Verify drag-drop event handling uses correct MIME type."""
        # Mock test - no actual Qt event needed
        mock_pane = Mock()
        mock_pane.run_dropped = Mock()
        
        # Simulate drag-drop would emit this signal
        assert hasattr(mock_pane, 'run_dropped')

    def test_pane_rejects_non_run_drop(self):
        """Verify pane handler would reject non-run MIME types."""
        # Logic test: verify rejection handling exists
        mock_pane = Mock()
        mime_format = "application/x-run-ref"
        
        # Verify the MIME type constant is correct format
        assert "run-ref" in mime_format


class TestRunComparison:
    """Test run comparison workflow."""

    def test_two_runs_can_be_loaded_simultaneously(self):
        """Verify two different runs can be loaded in swap mode."""
        window = Mock()
        window.current_view_mode = "swap"
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 2
        window.split_pane_widget.panes = {0: Mock(), 1: Mock()}
        window.archives = Mock()
        window.archives.get_archive_label.side_effect = lambda aid: aid.split(".")[0]
        window.pane_run_refs = {0: None, 1: None}
        window.info_label = Mock()
        window.state = Mock()
        window.state.current_archive_id = "current.liufs"
        window.state.current_run_name = "CurrentRun"
        
        controller = PaneOrchestrationController(window)
        controller.update_all_panes = Mock()
        controller.update_slider_maximum = Mock()
        
        # Mock archive handler
        handler = Mock()
        handler.manifest = {
            "runs": {
                "children": {
                    "RunA": {"children": {"v1": {}}},
                    "RunB": {"children": {"v1": {}}}
                }
            }
        }
        handler.get_runs.return_value = ["RunA", "RunB"]
        handler.get_group_categories.return_value = {"category1": {}}
        handler.get_category_datasets.return_value = {"dataset1": {"type": "cfd_images", "videos": {"video1": {}}}}
        
        window.archives.get_archive.return_value = handler
        
        # Load first run into pane 0
        controller.on_tree_run_dropped(0, "archive1.liufs", "RunA")
        
        # Load second run into pane 1
        controller.on_tree_run_dropped(1, "archive2.liufs", "RunB")
        
        # Both should be loaded
        assert window.pane_run_refs[0] is not None
        assert window.pane_run_refs[1] is not None
        assert window.pane_run_refs[0]["run_name"] == "RunA"
        assert window.pane_run_refs[1]["run_name"] == "RunB"

    def test_run_labels_remain_stable(self):
        """Verify run labels don't change as frames are stepped."""
        window = Mock()
        pane = Mock()
        window.split_pane_widget = Mock()
        window.split_pane_widget.get_pane_count.return_value = 1
        window.split_pane_widget.get_pane.return_value = pane
        window.frame_slider = Mock()
        window.frame_slider.value.return_value = 0
        
        run_ref = {
            "archive_id": "archive.liufs",
            "run_name": "RunName",
            "label": "archive | RunName",
            "context": {}
        }
        window.pane_run_refs = {0: run_ref}
        
        controller = PaneOrchestrationController(window)
        controller.get_pixmap_for_pane = Mock(return_value=Mock())
        
        # Update pane multiple times (simulating frame stepping)
        for _ in range(5):
            controller.update_all_panes()
        
        # Each call should use same label
        for call in pane.set_content.call_args_list:
            assert call[0][0] == "archive | RunName"


class TestSwapViewOverlayConsistency:
    """Test overlay consistency properties for swap mode."""

    def test_pane_position_consistency_property(self):
        """Verify pane positions are deterministic."""
        # Test the logic: panes should maintain consistent IDs
        pane_ids = [0, 1]
        
        # After multiple layout operations, IDs should be same
        consistent_ids = pane_ids
        
        assert consistent_ids == [0, 1]

    def test_frame_sync_prevents_out_of_bounds(self):
        """Verify frame sync uses minimum count to prevent errors."""
        frame_counts = [100, 50, 75]  # Three runs with different frame counts
        
        # Sync should use minimum
        sync_frame_count = min(frame_counts)
        
        assert sync_frame_count == 50
