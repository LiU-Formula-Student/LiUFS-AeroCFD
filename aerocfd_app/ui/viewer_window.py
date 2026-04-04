"""
Main application window for the .liufs viewer.
"""

import platform
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QFileDialog,
    QDialog, QDialogButtonBox, QLineEdit, QPlainTextEdit,
    QVBoxLayout, QLabel, QApplication
)
from PySide6.QtCore import Qt, qVersion, QTimer, QMimeData
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap

from ..liufs_handler import LiufsValidationError
from aerocfd_cli.packager import DuplicateRunError, append_run_to_liufs
from ..version import APP_VERSION

from .widgets.panes import GUIReporter, AppendRunWorker, DetachedImageWindow
from .widgets.help_dialog import HelpDialog
from .controllers import PaneOrchestrationController, SelectionOrchestrationController
from .ui_builder import UIBuilder
from ..core.view_state import ViewState
from ..core.archive_manager import ArchiveManager
from ..core.media_loader import MediaController
from ..core.pane_manager import PaneManager
from ..core.export_service import ExportService
from ..core.diagnostics import collect_diagnostics


class ViewerWindow(QMainWindow):
    """Main viewer window for .liufs files."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("LiU FS Simulation Viewer")
        self.setGeometry(100, 100, 1400, 800)
        
        # Core services
        self.state = ViewState()
        self.archives = ArchiveManager()
        self.media = MediaController(self.archives)
        self.panes_mgr = PaneManager()
        self.exporter = ExportService()
        
        # Background worker for appending runs
        self.append_worker: Optional[AppendRunWorker] = None
        self.current_append_source_dir: Optional[str] = None
        
        # Detached windows
        self.detached_windows: Dict[str, DetachedImageWindow] = {}
        
        # Pane tracking (maps pane_id to {archive_id, run_name, label, context})
        self.pane_run_refs: Dict[int, Optional[Dict[str, Any]]] = {}
        self.current_view_mode: str = "single"
        self.swap_pane_index: int = 0
        
        # Playback timer
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.advance_playback)

        self.pane_orchestration = PaneOrchestrationController(self)
        self.selection_orchestration = SelectionOrchestrationController(self)
        
        UIBuilder(self).setup_ui()
        self.setup_shortcuts()
    
    def show_app_info(self):
        """Show application and environment information in a popup dialog."""
        sim_name = "No file loaded"
        if self.state.current_archive_id:
            try:
                handler = self.archives.get_archive(self.state.current_archive_id)
                if handler:
                    sim_name = handler.get_simulation_name()
            except Exception:
                sim_name = "Unknown"

        info_text = (
            f"Application: LiU FS Simulation Viewer\n"
            f"Version: {APP_VERSION}\n"
            f"Current Simulation: {sim_name}\n"
            f"Python: {platform.python_version()}\n"
            f"Qt: {qVersion()}\n"
            f"Platform: {platform.system()} {platform.release()}"
        )

        QMessageBox.information(self, "Application Info", info_text)
    
    def show_help_dialog(self):
        """Show in-app help dialog with shortcuts and usage guide."""
        dialog = HelpDialog(self)
        dialog.exec()
    
    def show_report_issue_dialog(self):
        """Show report issue dialog with diagnostics copying."""
        sim_name = "No file loaded"
        if self.state.current_archive_id:
            try:
                handler = self.archives.get_archive(self.state.current_archive_id)
                if handler:
                    sim_name = handler.get_simulation_name()
            except Exception:
                sim_name = "Unknown"

        diagnostics = collect_diagnostics(sim_name)

        dialog = QDialog(self)
        dialog.setWindowTitle("Report Issue / Copy Diagnostics")
        dialog.setGeometry(100, 100, 700, 500)

        layout = QVBoxLayout(dialog)

        # Instructions label
        instructions = QLabel(
            "Copy the diagnostics below and paste them into a GitHub issue.\n"
            "Include steps to reproduce and a description of the problem."
        )
        layout.addWidget(instructions)

        # Diagnostics text area
        diagnostics_text = QPlainTextEdit()
        diagnostics_text.setPlainText(diagnostics)
        diagnostics_text.setReadOnly(True)
        layout.addWidget(diagnostics_text)

        # Buttons
        button_layout = QVBoxLayout()
        
        copy_btn = QMessageBox.StandardButton.Ok
        from PySide6.QtWidgets import QPushButton
        
        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(diagnostics)
        )
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)

        button_layout.addWidget(copy_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        dialog.exec()
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Frame navigation
        QShortcut(Qt.Key.Key_Right, self, self.next_frame)
        QShortcut(Qt.Key.Key_Left, self, self.previous_frame)
        
        # View modes
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.set_view_mode("single"))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self.set_view_mode("2-pane"))
        QShortcut(QKeySequence("Ctrl+4"), self, lambda: self.set_view_mode("4-pane"))
        QShortcut(QKeySequence("Ctrl+S"), self, lambda: self.set_view_mode("swap"))
        
        # Export
        QShortcut(QKeySequence("Ctrl+E"), self, self.export_current_frame)
    
    def set_view_mode(self, mode: str):
        """Switch between single/2-pane/4-pane/swap view modes."""
        self.pane_orchestration.set_view_mode(mode)
    
    def setup_pane_signals(self):
        """Connect run_dropped signals from all panes to handler."""
        self.pane_orchestration.setup_pane_signals()
    
    def on_tree_run_dropped(self, pane_id: int, archive_id: str, run_name: str):
        """Handle a run dropped into a specific pane."""
        self.pane_orchestration.on_tree_run_dropped(pane_id, archive_id, run_name)
    
    def clear_current_view(self):
        """Clear all panes in the current view."""
        self.pane_orchestration.clear_current_view()
    
    def update_all_panes(self):
        """Update all panes with current frame from loaded runs."""
        self.pane_orchestration.update_all_panes()
    
    def get_pixmap_for_pane(self, run_ref: Dict[str, Any], frame_index: int) -> Optional[QPixmap]:
        """Get pixmap for a pane from a run reference."""
        controller = getattr(self, "pane_orchestration", None) or PaneOrchestrationController(self)
        return controller.get_pixmap_for_pane(run_ref, frame_index)
    
    def open_file(self):
        """Open a .liufs file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open .liufs File",
            "",
            "LIUFS Files (*.liufs);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            self.load_liufs_file(file_path)
        except FileNotFoundError as e:
            QMessageBox.critical(
                self,
                "File Not Found",
                f"The file could not be found.\n\n{str(e)}"
            )
            self.info_label.clear()
            self.info_label.appendPlainText("❌ Error: File not found")
        except LiufsValidationError as e:
            QMessageBox.critical(
                self,
                "Invalid .liufs File",
                f"This file is not a valid .liufs archive.\n\n{str(e)}"
            )
            self.info_label.clear()
            self.info_label.appendPlainText("❌ Error: File validation failed\nSee error dialog for details")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Opening File",
                f"An unexpected error occurred while opening the file.\n\n{str(e)}"
            )
            self.info_label.clear()
            self.info_label.appendPlainText(f"❌ Error: {str(e)}")
    
    def load_liufs_file(self, file_path: str):
        """
        Load a .liufs file and display its structure.
        
        Args:
            file_path: Path to the .liufs file
            
        Raises:
            LiufsValidationError: If file validation fails
            FileNotFoundError: If file doesn't exist
        """
        try:
            # Load archive using manager
            archive_id = self.archives.load_archive(file_path)
            handler = self.archives.get_archive(archive_id)
            
            self.state.set_archive(archive_id)
            
            self.refresh_file_tree()

            # Update window title
            sim_name = handler.get_simulation_name()
            self.setWindowTitle(
                f"LiU FS Simulation Viewer - {sim_name} ({len(self.archives.open_archives)} open file(s))"
            )
            
            self.info_label.clear()
            visible_runs = handler.get_runs()
            self.info_label.appendPlainText(
                f"✓ File loaded successfully\n"
                f"  File: {Path(file_path).name}\n"
                f"  Simulation: {sim_name}\n"
                f"  Runs: {', '.join(visible_runs) if visible_runs else '(none)'}\n"
                f"  Tip: Drag runs from the tree to the panes above"
            )

            warnings = handler.get_validation_warnings()
            for warning in warnings:
                self.info_label.appendPlainText(f"⚠ Warning: {warning}")

            self.reset_option_controls()
            self.update_file_actions()
        
        except Exception:
            # Re-raise validation errors so they can be caught in open_file
            raise

    def refresh_file_tree(self):
        """Rebuild file tree from all currently open archives."""
        self.file_tree.populate_from_archives(self.archives.list_archives())

    def update_file_actions(self):
        """Enable or disable file actions that depend on an open archive."""
        if self.add_run_action is not None:
            self.add_run_action.setEnabled(bool(self.archives.open_archives))

    def add_new_run(self):
        """Add a new run directory to the currently open .liufs archive."""
        if not self.state.current_archive_id:
            return

        source_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Run Directory",
            "",
        )

        if not source_dir:
            return

        self._append_new_run(source_dir)

    def _append_new_run(self, source_dir: str, run_name: Optional[str] = None):
        if not self.state.current_archive_id:
            return

        handler = self.archives.get_archive(self.state.current_archive_id)
        if not handler:
            return

        self.current_append_source_dir = source_dir

        self.info_label.clear()
        self.info_label.appendPlainText("Starting to add new run...\n")

        self.append_worker = AppendRunWorker(
            self,
            source_dir,
            handler.file_path,
            handler.file_path,
            run_name,
        )
        self.append_worker.progress_updated.connect(self._on_progress_update)
        self.append_worker.finished.connect(self._on_append_finished)
        self.append_worker.error.connect(self._on_append_error)
        self.append_worker.duplicate_error.connect(self._on_append_duplicate_error)
        self.append_worker.start()

    def _on_progress_update(self, message: str):
        """Append progress message to the info text area."""
        self.info_label.appendPlainText(message)

    def _on_append_finished(self, result: Path):
        """Handle successful append completion."""
        self.info_label.appendPlainText("✓ Run added successfully! Reloading archive...\n")
        try:
            self.load_liufs_file(str(result))
        except LiufsValidationError as e:
            QMessageBox.critical(
                self,
                "Error Reloading File",
                f"The file was modified but cannot be read back.\n\n{str(e)}"
            )
            self.info_label.appendPlainText(f"❌ Error: File reload failed\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Reloading File",
                f"An error occurred while reloading the file after adding the run.\n\n{str(e)}"
            )
            self.info_label.appendPlainText(f"❌ Error: {str(e)}")

    def _on_append_error(self, error_msg: str):
        """Handle append error."""
        QMessageBox.critical(
            self,
            "Error Adding Run",
            f"Failed to add the run to the archive.\n\n{error_msg}"
        )
        self.info_label.appendPlainText(f"\n❌ Error: {error_msg}")

    def _on_append_duplicate_error(self, run_name: str, existing_runs: list):
        """Handle duplicate run error with rename prompt."""
        self.info_label.appendPlainText(
            f"\n⚠ Warning: A run named '{run_name}' already exists.\n"
            f"  Existing runs: {', '.join(existing_runs)}"
        )
        renamed_run_name = self.prompt_for_run_rename(run_name)
        if not renamed_run_name:
            self.info_label.appendPlainText("ℹ Operation cancelled by user.\n")
            return

        self.info_label.appendPlainText(f"↻ Retrying with run name: '{renamed_run_name}'\n")
        self._append_new_run(self.current_append_source_dir, run_name=renamed_run_name)

    def prompt_for_run_rename(self, suggested_name: str) -> Optional[str]:
        """Ask the user for a replacement run name after a duplicate collision."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Run Already Exists")

        layout = QVBoxLayout(dialog)

        message_label = QLabel("A run with this name already exists. Do you want to rename the file to:")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        name_input = QLineEdit(suggested_name, dialog)
        layout.addWidget(name_input)

        button_box = QDialogButtonBox(dialog)
        rename_button = button_box.addButton("Rename", QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)

        def accept_rename():
            candidate = name_input.text().strip()
            if not candidate:
                QMessageBox.warning(dialog, "Invalid Name", "Run name cannot be empty.")
                return
            dialog.accept()

        rename_button.clicked.connect(accept_rename)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return name_input.text().strip()
        return None
    
    def on_tree_selection_changed(self):
        """Handle tree selection change."""
        if not self.archives.open_archives:
            return

        selected = self.file_tree.get_selected_reference()
        archive_id = selected.get("archive_id")
        path = selected.get("path", [])
        if isinstance(archive_id, str) and archive_id in self.archives.open_archives:
            self.state.set_archive(archive_id)

        if len(path) != 1:
            self.reset_option_controls()
            return

        self.load_run_node(path[0])

    def reset_option_controls(self):
        """Reset version/category/dataset/item selectors."""
        self.state.reset()
        
        self.version_combo.blockSignals(True)
        self.category_combo.blockSignals(True)
        self.dataset_combo.blockSignals(True)
        self.item_combo.blockSignals(True)

        self.version_combo.clear()
        self.category_combo.clear()
        self.dataset_combo.clear()
        self.item_combo.clear()

        self.version_combo.blockSignals(False)
        self.category_combo.blockSignals(False)
        self.dataset_combo.blockSignals(False)
        self.item_combo.blockSignals(False)

        self.version_combo.setEnabled(False)
        self.category_combo.setEnabled(False)
        self.dataset_combo.setEnabled(False)
        self.item_combo.setEnabled(False)

    def load_run_node(self, run_name: str):
        """Load available versions from selected run."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.load_run_node(run_name)

    def populate_categories_for_version(self):
        """Populate category selector based on selected version."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.populate_categories_for_version()

    def populate_datasets_for_category(self):
        """Populate dataset selector based on selected category."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.populate_datasets_for_category()

    def populate_items_for_dataset(self):
        """Populate item selector (planes/views) based on selected dataset."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.populate_items_for_dataset()

    def on_version_changed(self, _index: int):
        """Handle version selector change."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.on_version_changed(_index)

    def on_category_changed(self, _index: int):
        """Handle category selector change."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.on_category_changed(_index)

    def on_dataset_changed(self, _index: int):
        """Handle dataset selector change."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.on_dataset_changed(_index)

    def on_item_changed(self, _index: int):
        """Handle item selector change."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.on_item_changed(_index)

    def update_pane_contexts_for_selector_change(self):
        """Update pane contexts when selectors change, skipping invalid panes."""
        controller = getattr(self, "pane_orchestration", None) or PaneOrchestrationController(self)
        controller.update_pane_contexts_for_selector_change()

    def get_compare_run_pixmap(self, ref: Dict[str, Any], frame_index: int) -> Optional[QPixmap]:
        """Get pixmap from MediaController."""
        archive_id = ref.get("archive_id")
        run_name = ref.get("run_name")
        version = self.state.current_version_name
        category = self.category_combo.currentText()
        dataset = self.dataset_combo.currentText()
        item = self.item_combo.currentText()
        
        if not all([archive_id, run_name, version, category, dataset, item]):
            return None
        
        handler = self.archives.get_archive(archive_id)
        if not handler:
            return None
        
        group_path = [run_name, version]
        datasets = handler.get_category_datasets(group_path, category)
        dataset_node = datasets.get(dataset, {})
        if not isinstance(dataset_node, dict):
            return None
        
        rel_video_path = (dataset_node.get("videos") or {}).get(item)
        if not isinstance(rel_video_path, str):
            return None
        
        archive_path = handler.resolve_archive_path(group_path, rel_video_path)
        return self.media.get_frame_from_video(archive_id, archive_path, frame_index)
    
    def get_pane_pixmap_with_context(self, run_ref: Dict[str, Any], frame_index: int, pane_context: Dict[str, Any]) -> Optional[QPixmap]:
        """Get pixmap for a pane using MediaController."""
        archive_id = run_ref.get("archive_id")
        run_name = run_ref.get("run_name")
        version = pane_context.get("version")
        category = pane_context.get("category")
        dataset = pane_context.get("dataset")
        item = pane_context.get("item")
        
        if not all([archive_id, run_name, version, category, dataset, item]):
            return None
        
        handler = self.archives.get_archive(archive_id)
        if not handler:
            return None
        
        group_path = pane_context.get("group_path", [])
        datasets = handler.get_category_datasets(group_path, category)
        dataset_node = datasets.get(dataset, {})
        if not isinstance(dataset_node, dict):
            return None
        
        rel_video_path = (dataset_node.get("videos") or {}).get(item)
        if not isinstance(rel_video_path, str):
            return None
        
        archive_path = handler.resolve_archive_path(group_path, rel_video_path)
        return self.media.get_frame_from_video(archive_id, archive_path, frame_index)
    
    def get_video_frame_count_for_pane(self, run_ref: Dict[str, Any]) -> int:
        """Get frame count for a pane video using MediaController."""
        pane_context = run_ref.get("context")
        if not pane_context:
            return 0
        
        archive_id = run_ref.get("archive_id")
        run_name = run_ref.get("run_name")
        version = pane_context.get("version")
        category = pane_context.get("category")
        dataset = pane_context.get("dataset")
        item = pane_context.get("item")
        
        if not all([archive_id, run_name, version, category, dataset, item]):
            return 0
        
        handler = self.archives.get_archive(archive_id)
        if not handler:
            return 0
        
        group_path = pane_context.get("group_path", [])
        datasets = handler.get_category_datasets(group_path, category)
        dataset_node = datasets.get(dataset, {})
        if not isinstance(dataset_node, dict):
            return 0
        
        rel_video_path = (dataset_node.get("videos") or {}).get(item)
        if not isinstance(rel_video_path, str):
            return 0
        
        archive_path = handler.resolve_archive_path(group_path, rel_video_path)
        return self.media.get_total_frames(archive_id, archive_path)
    
    def update_slider_maximum(self):
        """Update frame slider maximum based on currently loaded panes."""
        controller = getattr(self, "pane_orchestration", None) or PaneOrchestrationController(self)
        controller.update_slider_maximum()

    def load_selected_media(self):
        """Load currently selected video or static image."""
        controller = getattr(self, "selection_orchestration", None) or SelectionOrchestrationController(self)
        controller.load_selected_media()
    
    def display_frame(self, frame_index: int):
        """Display a specific frame in all panes."""
        try:
            self.frame_slider.blockSignals(True)
            self.frame_slider.setValue(frame_index)
            self.frame_slider.blockSignals(False)

            self.state.goto_frame(frame_index)
            self.update_all_panes()

            self.info_label.clear()
            if self.state.max_frame_index > 0:
                self.info_label.appendPlainText(f"Frame: {frame_index + 1}/{self.state.max_frame_index + 1}")
            else:
                self.info_label.appendPlainText("Frame n/a (static images)")
        except Exception as e:
            self.info_label.clear()
            self.info_label.appendPlainText(f"⚠ Warning: Failed to display frame\n  {str(e)}")

    def on_slider_moved(self, value: int):
        """Handle slider movement."""
        self.display_frame(value)

    def on_slider_value_changed(self, value: int):
        """Handle slider value changes (including click-to-jump)."""
        if self.frame_slider.isSliderDown():
            return
        self.display_frame(value)

    def get_speed_multiplier(self) -> float:
        text = self.speed_combo.currentText().replace("x", "")
        try:
            return float(text)
        except ValueError:
            return 1.0

    def get_playback_interval_ms(self) -> int:
        # Get FPS from media controller's primary video
        fps = 12.0
        speed = self.get_speed_multiplier()
        interval = int(1000 / max(fps * speed, 0.1))
        return max(interval, 10)

    def start_playback(self):
        """Start playback."""
        if self.frame_slider.maximum() <= 0:
            return
        self.playback_timer.start(self.get_playback_interval_ms())

    def pause_playback(self):
        """Pause playback."""
        self.playback_timer.stop()

    def stop_playback(self):
        """Stop playback and return to frame 0."""
        self.playback_timer.stop()
        if self.frame_slider.maximum() >= 0:
            self.display_frame(0)

    def on_speed_changed(self, _index: int):
        """Update playback timer interval when speed changes."""
        if self.playback_timer.isActive():
            self.playback_timer.start(self.get_playback_interval_ms())

    def advance_playback(self):
        """Advance playback by one frame."""
        max_frame = self.frame_slider.maximum()
        if max_frame <= 0:
            self.pause_playback()
            return

        current = self.frame_slider.value()
        next_frame = current + 1
        if next_frame > max_frame:
            if self.loop_combo.currentText() == "Loop":
                next_frame = 0
            else:
                self.pause_playback()
                return
        self.display_frame(next_frame)
    
    def next_frame(self):
        """Move to next frame."""
        max_frame = self.frame_slider.maximum()
        if max_frame <= 0:
            return
        
        current = self.frame_slider.value()
        next_frame = min(current + 1, max_frame)
        self.display_frame(next_frame)
    
    def previous_frame(self):
        """Move to previous frame."""
        current = self.frame_slider.value()
        prev_frame = max(current - 1, 0)
        self.display_frame(prev_frame)

    def get_current_pixmap(self) -> Optional[QPixmap]:
        """Return currently displayed pixmap from the primary pane (pane 0)."""
        pane = self.split_pane_widget.get_pane(0)
        if pane and pane.label:
            pixmap = pane.label.pixmap()
            return pixmap if pixmap else None
        return None

    def export_current_frame(self):
        """Export current frame as image file."""
        pixmap = self.get_current_pixmap()
        if not pixmap:
            self.info_label.appendPlainText("⚠ Warning: No frame to export")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Current Frame",
            "frame.png",
            "PNG (*.png);;JPEG (*.jpg *.jpeg)",
        )
        if not output_path:
            return

        if self.exporter.export_frame(pixmap, output_path):
            self.info_label.appendPlainText(f"✓ Exported frame: {output_path}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export current frame.")

    def export_current_video_clip(self):
        """Export currently selected video clip file."""
        if not self.state.current_video_path:
            self.info_label.appendPlainText("⚠ Warning: No video loaded to export")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Current Video Clip",
            "clip.mp4",
            "MP4 (*.mp4);;All Files (*)",
        )
        if not output_path:
            return

        if self.exporter.export_video_clip(self.state.current_video_path, output_path):
            self.info_label.appendPlainText(f"✓ Exported video clip: {output_path}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export clip.")

    def copy_current_frame(self):
        """Copy current frame to clipboard."""
        pixmap = self.get_current_pixmap()
        if not pixmap:
            self.info_label.appendPlainText("⚠ Warning: No frame to copy")
            return
        if self.exporter.copy_to_clipboard(pixmap):
            self.info_label.appendPlainText("✓ Copied current frame to clipboard")
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.playback_timer.stop()
        
        # Clean up media resources
        self.media.cleanup()
        
        # Close detached windows
        for window in self.detached_windows.values():
            window.close()
        
        # Clean up archive manager
        self.archives.close_all()
        
        event.accept()
