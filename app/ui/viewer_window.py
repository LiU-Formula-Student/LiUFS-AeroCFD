"""
Main application window for the .liufs viewer.
"""

import platform
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QFileDialog,
    QDialog, QDialogButtonBox, QLineEdit, QPlainTextEdit,
    QVBoxLayout, QLabel
)
from PySide6.QtCore import Qt, qVersion, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap

from ..liufs_handler import LiufsValidationError
from simulation_compressor.packager import DuplicateRunError, append_run_to_liufs
from ..version import APP_VERSION

from .widgets.panes import GUIReporter, AppendRunWorker, DetachedImageWindow
from .ui_builder import UIBuilder
from ..core.view_state import ViewState
from ..core.archive_manager import ArchiveManager
from ..core.media_loader import MediaController
from ..core.pane_manager import PaneManager
from ..core.export_service import ExportService


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
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        QShortcut(Qt.Key.Key_Right, self, self.next_frame)
        QShortcut(Qt.Key.Key_Left, self, self.previous_frame)
    
    def set_view_mode(self, mode: str):
        """Switch between single/2-pane/4-pane/swap view modes."""
        if mode in {"single", "2-pane", "4-pane"}:
            self.current_view_mode = mode
            self.split_pane_widget.set_layout(mode)
            self.pane_run_refs = {i: None for i in range(self.split_pane_widget.get_pane_count())}
            self.swap_pane_index = 0
            self.setup_pane_signals()
            self.update_all_panes()
        elif mode == "swap":
            if self.current_view_mode != "swap":
                self.current_view_mode = "swap"
        else:
            self.info_label.appendPlainText(f"⚠ Unknown view mode: {mode}")
    
    def setup_pane_signals(self):
        """Connect run_dropped signals from all panes to handler."""
        for pane in self.split_pane_widget.panes.values():
            pane.run_dropped.connect(self.on_tree_run_dropped)
    
    def on_tree_run_dropped(self, pane_id: int, archive_id: str, run_name: str):
        """Handle a run dropped into a specific pane."""
        try:
            if pane_id < 0 or pane_id >= self.split_pane_widget.get_pane_count():
                self.info_label.appendPlainText(f"⚠ Pane {pane_id} is not available in current view")
                return

            # Verify archive and run exist using ArchiveManager
            handler = self.archives.get_archive(archive_id)
            if handler is None:
                self.info_label.appendPlainText(f"⚠ Archive not loaded: {archive_id}")
                return
            
            if run_name not in handler.get_runs():
                self.info_label.appendPlainText(f"⚠ Run not found: {run_name}")
                return
            
            archive_label = self.archives.get_archive_label(archive_id)

            # Build pane-specific context with first available options
            runs = handler.manifest.get("runs", {}).get("children", {})
            run_node = runs.get(run_name, {}) if isinstance(runs, dict) else {}
            children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
            versions = [name for name, node in (children.items() if isinstance(children, dict) else []) if isinstance(node, dict)]
            
            pane_context = {
                "archive_id": archive_id,
                "run_name": run_name,
                "version": None,
                "group_path": [],
                "category": None,
                "dataset": None,
                "item": None,
            }
            
            if versions:
                version_name = sorted(versions)[0]
                pane_context["version"] = version_name
                group_path = [run_name, version_name]
                pane_context["group_path"] = group_path
                categories = handler.get_group_categories(group_path)
                
                if categories:
                    category_name = sorted(categories.keys())[0]
                    pane_context["category"] = category_name
                    datasets = handler.get_category_datasets(group_path, category_name)
                    
                    if datasets:
                        dataset_name = sorted(datasets.keys())[0]
                        pane_context["dataset"] = dataset_name
                        dataset_node = datasets.get(dataset_name, {})
                        items = []
                        if dataset_node.get("type") == "cfd_images":
                            items = sorted((dataset_node.get("videos") or {}).keys())
                        
                        if items:
                            pane_context["item"] = items[0]
            
            # Update the pane reference with its own context
            self.pane_run_refs[pane_id] = {
                "archive_id": archive_id,
                "run_name": run_name,
                "label": f"{archive_label} | {run_name}",
                "context": pane_context
            }
            
            # Trigger pane update with current frame (uses pane-specific context)
            self.update_all_panes()
            
            # Update frame slider maximum based on loaded panes
            self.update_slider_maximum()
            
            self.info_label.appendPlainText(f"✓ Loaded '{run_name}' in pane {pane_id}")
        except Exception as e:
            self.info_label.appendPlainText(f"❌ Error loading run in pane {pane_id}: {str(e)}")
    
    def clear_current_view(self):
        """Clear all panes in the current view."""
        self.pane_run_refs = {i: None for i in range(self.split_pane_widget.get_pane_count())}
        self.split_pane_widget.clear_all()
        self.info_label.appendPlainText("✓ Cleared current view")
    
    def update_all_panes(self):
        """Update all panes with current frame from loaded runs."""
        if not self.split_pane_widget:
            return
        
        frame_index = self.frame_slider.value()
        for pane_id in range(self.split_pane_widget.get_pane_count()):
            pane = self.split_pane_widget.get_pane(pane_id)
            if not pane:
                continue
            
            run_ref = self.pane_run_refs.get(pane_id)
            if not run_ref:
                pane.clear()
                continue
            
            pixmap = self.get_pixmap_for_pane(run_ref, frame_index)
            title = run_ref.get("label", "Run")
            pane.set_content(title, pixmap)
    
    def get_pixmap_for_pane(self, run_ref: Dict[str, Any], frame_index: int) -> Optional[QPixmap]:
        """Get pixmap for a pane from a run reference."""
        # Use pane-specific context if available (from drag-and-drop)
        pane_context = run_ref.get("context")
        if pane_context:
            return self.get_pane_pixmap_with_context(run_ref, frame_index, pane_context)
        
        # If this is the primary run, get from primary video player
        if (run_ref.get("archive_id") == self.state.current_archive_id and 
            run_ref.get("run_name") == self.state.current_run_name):
            player = self.media.get_video_player(self.state.current_archive_id, self.state.current_run_name)
            if player:
                return player.get_frame(frame_index)
            return None
        
        # Otherwise, get from compare video cache
        return self.get_compare_run_pixmap(run_ref, frame_index)
    
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
        archive_id = self.state.current_archive_id
        if not archive_id:
            return

        try:
            handler = self.archives.get_archive(archive_id)
            if not handler:
                return

            runs = handler.manifest.get("runs", {}).get("children", {})
            run_node = runs.get(run_name, {}) if isinstance(runs, dict) else {}
            children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
            versions = [name for name, node in (children.items() if isinstance(children, dict) else []) if isinstance(node, dict)]

            if not versions:
                self.reset_option_controls()
                self.info_label.clear()
                self.info_label.appendPlainText("No versions found for this run")
                self.frame_slider.setMaximum(0)
                return

            self.state.set_run(run_name)
            self.state.set_available_versions(versions)

            self.version_combo.blockSignals(True)
            self.version_combo.clear()
            for version_name in self.state.current_versions:
                self.version_combo.addItem(version_name)
            self.version_combo.blockSignals(False)
            self.version_combo.setEnabled(True)

            self.populate_categories_for_version()
        except Exception as e:
            self.info_label.clear()
            self.info_label.appendPlainText(f"❌ Error: {str(e)}")

    def populate_categories_for_version(self):
        """Populate category selector based on selected version."""
        archive_id = self.state.current_archive_id
        run_name = self.state.current_run_name
        if not archive_id or not run_name:
            return

        handler = self.archives.get_archive(archive_id)
        if not handler:
            return

        version_name = self.version_combo.currentText()
        if not version_name:
            return

        group_path = [run_name, version_name]
        self.state.set_version(version_name)
        self.state.set_group_path(group_path)
        
        categories = handler.get_group_categories(group_path)
        if not categories:
            self.state.set_available_categories({})
            self.category_combo.blockSignals(True)
            self.category_combo.clear()
            self.category_combo.blockSignals(False)
            self.category_combo.setEnabled(False)
            self.dataset_combo.clear()
            self.dataset_combo.setEnabled(False)
            self.item_combo.clear()
            self.item_combo.setEnabled(False)
            self.info_label.clear()
            self.info_label.appendPlainText("No categories found for selected version")
            return

        self.state.set_available_categories(categories)

        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        for category_name in sorted(categories.keys()):
            self.category_combo.addItem(category_name)
        self.category_combo.blockSignals(False)
        self.category_combo.setEnabled(True)

        self.populate_datasets_for_category()

    def populate_datasets_for_category(self):
        """Populate dataset selector based on selected category."""
        archive_id = self.state.current_archive_id
        if not archive_id:
            return

        handler = self.archives.get_archive(archive_id)
        if not handler:
            return

        category_name = self.category_combo.currentText()
        if not category_name:
            return

        datasets = handler.get_category_datasets(self.state.current_group_path, category_name)
        self.state.set_available_datasets(datasets)

        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        for dataset_name in sorted(datasets.keys()):
            self.dataset_combo.addItem(dataset_name)
        self.dataset_combo.blockSignals(False)
        self.dataset_combo.setEnabled(bool(datasets))

        self.populate_items_for_dataset()

    def populate_items_for_dataset(self):
        """Populate item selector (planes/views) based on selected dataset."""
        dataset_name = self.dataset_combo.currentText()
        dataset_node = self.state.current_datasets.get(dataset_name, {})

        items: list[str] = []
        if dataset_node.get("type") == "cfd_images":
            items = sorted((dataset_node.get("videos") or {}).keys())
        elif dataset_node.get("type") == "3d_views":
            files = dataset_node.get("files") or []
            items = sorted(Path(path).name for path in files if isinstance(path, str))

        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        for item in items:
            self.item_combo.addItem(item)
        self.item_combo.blockSignals(False)
        self.item_combo.setEnabled(bool(items))

        if items:
            self.info_label.clear()
            self.info_label.appendPlainText("Select a plane to load media, or drag a run into any pane.")

    def on_version_changed(self, _index: int):
        """Handle version selector change."""
        self.populate_categories_for_version()
        self.update_pane_contexts_for_selector_change()
        self.update_all_panes()
        self.update_slider_maximum()

    def on_category_changed(self, _index: int):
        """Handle category selector change."""
        self.populate_datasets_for_category()
        self.update_pane_contexts_for_selector_change()
        self.update_all_panes()
        self.update_slider_maximum()

    def on_dataset_changed(self, _index: int):
        """Handle dataset selector change."""
        self.populate_items_for_dataset()
        self.update_pane_contexts_for_selector_change()
        self.update_all_panes()
        self.update_slider_maximum()

    def on_item_changed(self, _index: int):
        """Handle item selector change."""
        self.load_selected_media()
        self.update_pane_contexts_for_selector_change()
        self.update_all_panes()
        self.update_slider_maximum()

    def update_pane_contexts_for_selector_change(self):
        """Update pane contexts when selectors change, skipping invalid panes."""
        version_name = self.version_combo.currentText() if self.version_combo else ""
        category_name = self.category_combo.currentText() if self.category_combo else ""
        dataset_name = self.dataset_combo.currentText() if self.dataset_combo else ""
        item_name = self.item_combo.currentText() if self.item_combo else ""

        if not version_name:
            return

        for pane_id, run_ref in self.pane_run_refs.items():
            if not run_ref:
                continue

            archive_id = run_ref.get("archive_id")
            run_name = run_ref.get("run_name")
            if not archive_id or not run_name:
                continue

            handler = None
            if hasattr(self, "archives") and self.archives:
                handler = self.archives.get_archive(archive_id)
            if handler is None:
                open_archives = getattr(self, "open_archives", {})
                handler = open_archives.get(archive_id)
            if handler is None:
                continue

            runs = handler.manifest.get("runs", {}).get("children", {})
            run_node = runs.get(run_name, {}) if isinstance(runs, dict) else {}
            children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
            if version_name not in children:
                continue

            group_path = [run_name, version_name]
            categories = handler.get_group_categories(group_path)
            if category_name and category_name not in categories:
                continue

            selected_category = category_name or (sorted(categories.keys())[0] if categories else None)
            if not selected_category:
                continue

            datasets = handler.get_category_datasets(group_path, selected_category)
            if dataset_name and dataset_name not in datasets:
                continue

            selected_dataset = dataset_name or (sorted(datasets.keys())[0] if datasets else None)
            if not selected_dataset:
                continue

            dataset_node = datasets.get(selected_dataset, {})
            selected_item = item_name

            if dataset_node.get("type") == "cfd_images":
                videos = dataset_node.get("videos") or {}
                if selected_item and selected_item not in videos:
                    continue
                if not selected_item:
                    video_items = sorted(videos.keys())
                    selected_item = video_items[0] if video_items else None
            elif dataset_node.get("type") == "3d_views":
                files = dataset_node.get("files") or []
                file_items = sorted(Path(path).name for path in files if isinstance(path, str))
                if selected_item and selected_item not in file_items:
                    continue
                if not selected_item:
                    selected_item = file_items[0] if file_items else None

            pane_context = run_ref.get("context") or {}
            pane_context.update({
                "archive_id": archive_id,
                "run_name": run_name,
                "version": version_name,
                "group_path": group_path,
                "category": selected_category,
                "dataset": selected_dataset,
                "item": selected_item,
            })
            run_ref["context"] = pane_context
            self.pane_run_refs[pane_id] = run_ref

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
        if not self.split_pane_widget:
            return
        
        # Collect frame counts from all loaded panes
        frame_counts = []
        for pane_id in range(self.split_pane_widget.get_pane_count()):
            run_ref = self.pane_run_refs.get(pane_id)
            if run_ref and run_ref.get("context"):
                count = self.get_video_frame_count_for_pane(run_ref)
                if count > 0:
                    frame_counts.append(count)
        
        # Also add primary video player if available
        player = None
        if hasattr(self, "media") and hasattr(self, "state") and self.media and self.state:
            player = self.media.get_video_player(self.state.current_archive_id, self.state.current_run_name)
        elif hasattr(self, "video_player"):
            player = self.video_player
        if player:
            frame_counts.append(player.get_total_frames())
        
        # Set slider to minimum of all counts (so all panes can show all frames)
        if frame_counts:
            max_frames = min(frame_counts)
            self.frame_slider.blockSignals(True)
            self.frame_slider.setMaximum(max(max_frames - 1, 0))
            self.frame_slider.setValue(0)
            self.frame_slider.blockSignals(False)
            self.frame_slider.setEnabled(True)
        else:
            self.frame_slider.setMaximum(0)
            self.frame_slider.setEnabled(False)

    def load_selected_media(self):
        """Load currently selected video or static image."""
        archive_id = self.state.current_archive_id
        run_name = self.state.current_run_name
        if not archive_id or not run_name:
            return

        category_name = self.category_combo.currentText()
        dataset_name = self.dataset_combo.currentText()
        item_name = self.item_combo.currentText()
        if not category_name or not dataset_name or not item_name:
            return

        dataset_node = self.state.current_datasets.get(dataset_name)
        if not dataset_node:
            return

        try:
            handler = self.archives.get_archive(archive_id)
            if not handler:
                return
            
            data_type = dataset_node.get("type")

            if data_type == "cfd_images":
                rel_video_path = (dataset_node.get("videos") or {}).get(item_name)
                if not isinstance(rel_video_path, str):
                    self.info_label.clear()
                    self.info_label.appendPlainText("⚠ Warning: Video path not found in manifest")
                    return

                archive_path = handler.resolve_archive_path(self.state.current_group_path, rel_video_path)
                player = self.media.get_video_player(archive_id, archive_path)
                if not player:
                    self.info_label.clear()
                    self.info_label.appendPlainText(f"❌ Error: Cannot load video")
                    return

                self.state.set_media_type("video")
                self.state.set_video_path(archive_path)
                frame_count = player.get_total_frames()
                self.frame_slider.setMaximum(max(frame_count - 1, 0))
                self.frame_slider.setValue(0)
                self.frame_slider.setEnabled(frame_count > 0)

                self.display_frame(0)
                self.update_all_panes()
                self.update_slider_maximum()
                self.info_label.clear()
                self.info_label.appendPlainText(
                    f"✓ Loaded: {category_name}/{dataset_name}/{item_name}\n"
                    f"  Frames: {frame_count} | FPS: {player.fps:.2f}"
                )

            elif data_type == "3d_views":
                files = dataset_node.get("files") or []
                matching = [path for path in files if isinstance(path, str) and Path(path).name == item_name]
                if not matching:
                    self.info_label.clear()
                    self.info_label.appendPlainText("⚠ Warning: Image path not found in manifest")
                    return

                archive_path = handler.resolve_archive_path(self.state.current_group_path, matching[0])
                pixmap = self.media.load_static_image(archive_id, archive_path)
                if not pixmap:
                    self.info_label.clear()
                    self.info_label.appendPlainText(f"❌ Error: Cannot read image file")
                    return

                self.state.set_media_type("image")
                self.frame_slider.setMaximum(0)
                self.frame_slider.setEnabled(False)
                
                pane = self.split_pane_widget.get_pane(0)
                if pane:
                    pane.set_content(f"{category_name}/{dataset_name}/{item_name}", pixmap)
                self.info_label.clear()
                self.info_label.appendPlainText(
                    f"✓ Loaded: {category_name}/{dataset_name}/{item_name}\n"
                    f"  Size: {pixmap.width()}x{pixmap.height()} px"
                )
            else:
                self.info_label.clear()
                self.info_label.appendPlainText(f"⚠ Warning: Unknown media type '{data_type}'")
        except Exception as e:
            self.info_label.clear()
            self.info_label.appendPlainText(f"❌ Error: {str(e)}")
    
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
