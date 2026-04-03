"""
Main application window for the .liufs viewer.
"""

import platform
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QSplitter, QMessageBox, QFileDialog, QComboBox,
    QDialog, QDialogButtonBox, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt, qVersion, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap

from .liufs_handler import LiufsFileHandler, LiufsValidationError
from .file_tree import FileTreeWidget
from simulation_compressor.packager import DuplicateRunError, append_run_to_liufs
from .video_player import VideoPlayer
from .version import APP_VERSION

from .view_components import GUIReporter, AppendRunWorker, DetachedImageWindow, ImagePane, SplitPaneWidget


class ViewerWindow(QMainWindow):
    """Main viewer window for .liufs files."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("LiU FS Simulation Viewer")
        self.setGeometry(100, 100, 1400, 800)
        
        self.current_liufs_handler: Optional[LiufsFileHandler] = None
        self.current_archive_id: Optional[str] = None
        self.open_archives: Dict[str, LiufsFileHandler] = {}
        self.open_archive_paths: Dict[str, str] = {}
        self.current_video_path: Optional[str] = None
        self.video_player: Optional[VideoPlayer] = None
        self.compare_video_path: Optional[str] = None
        self.compare_video_player: Optional[VideoPlayer] = None
        self.temp_dir: Optional[str] = None
        self.current_group_path: list[str] = []
        self.current_run_name: Optional[str] = None
        self.current_version_name: Optional[str] = None
        self.current_versions: list[str] = []
        self.current_categories: Dict[str, Dict[str, Any]] = {}
        self.current_datasets: Dict[str, Dict[str, Any]] = {}
        self.current_media_type: Optional[str] = None
        self.primary_source: Optional[Dict[str, Any]] = None
        self.compare_run_refs: list[Dict[str, Any]] = []
        self.selected_compare_index: int = 0
        self.swap_index: int = 0
        self.compare_video_cache: Dict[tuple[str, ...], VideoPlayer] = {}
        self.add_run_action = None
        self.append_worker: Optional[AppendRunWorker] = None
        self.current_append_source_dir: Optional[str] = None
        self.detached_windows: Dict[str, DetachedImageWindow] = {}
        
        # Split pane state
        self.split_pane_widget: Optional[SplitPaneWidget] = None
        self.pane_run_refs: Dict[int, Optional[Dict[str, str]]] = {}
        self.current_view_mode = "single"
        self.swap_pane_index = 0

        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.advance_playback)
        
        self.setup_ui()
        self.setup_shortcuts()
    
    def setup_ui(self):
        """Setup the user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create splitter for left (tree) and right (viewer) panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: File tree
        self.file_tree = FileTreeWidget()
        self.file_tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        splitter.addWidget(self.file_tree)
        
        # Right panel: Video viewer with split panes
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        # Split pane widget - replaces image_panel and compare_section
        self.split_pane_widget = SplitPaneWidget()
        self.setup_pane_signals()
        right_layout.addWidget(self.split_pane_widget, 1)

        # Playback controls
        playback_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.play_button.clicked.connect(self.start_playback)
        self.pause_button.clicked.connect(self.pause_playback)
        self.stop_button.clicked.connect(self.stop_playback)

        playback_layout.addWidget(self.play_button)
        playback_layout.addWidget(self.pause_button)
        playback_layout.addWidget(self.stop_button)

        playback_layout.addSpacing(12)
        playback_layout.addWidget(QLabel("Speed"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "1x", "2x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.currentIndexChanged.connect(self.on_speed_changed)
        playback_layout.addWidget(self.speed_combo)

        playback_layout.addSpacing(12)
        playback_layout.addWidget(QLabel("Loop"))
        self.loop_combo = QComboBox()
        self.loop_combo.addItems(["Off", "Loop"])
        playback_layout.addWidget(self.loop_combo)
        playback_layout.addStretch(1)
        right_layout.addLayout(playback_layout)
        
        # Slider for frame navigation
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.sliderMoved.connect(self.on_slider_moved)
        self.frame_slider.valueChanged.connect(self.on_slider_value_changed)
        right_layout.addWidget(self.frame_slider)

        # Controls for version/category/dataset/item selection
        controls_layout = QHBoxLayout()

        version_label = QLabel("Version")
        self.version_combo = QComboBox()
        self.version_combo.setEnabled(False)
        self.version_combo.currentIndexChanged.connect(self.on_version_changed)

        category_label = QLabel("Category")
        self.category_combo = QComboBox()
        self.category_combo.setEnabled(False)
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)

        dataset_label = QLabel("Dataset")
        self.dataset_combo = QComboBox()
        self.dataset_combo.setEnabled(False)
        self.dataset_combo.currentIndexChanged.connect(self.on_dataset_changed)

        item_label = QLabel("Plane")
        self.item_combo = QComboBox()
        self.item_combo.setEnabled(False)
        self.item_combo.currentIndexChanged.connect(self.on_item_changed)

        controls_layout.addWidget(version_label)
        controls_layout.addWidget(self.version_combo)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(category_label)
        controls_layout.addWidget(self.category_combo)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(dataset_label)
        controls_layout.addWidget(self.dataset_combo)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(item_label)
        controls_layout.addWidget(self.item_combo)
        controls_layout.addStretch(1)
        right_layout.addLayout(controls_layout)
        
        # Frame info label
        self.info_label = QPlainTextEdit()
        self.info_label.setReadOnly(True)
        self.info_label.setMaximumHeight(80)
        self.info_label.setStyleSheet("color: #888888; font-size: 11px; background-color: #1e1e1e;")
        right_layout.addWidget(self.info_label)
        
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        # Create menu bar
        self.create_menu_bar()
    
    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = file_menu.addAction("&Open .liufs File")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)

        self.add_run_action = file_menu.addAction("&Add New Run")
        self.add_run_action.triggered.connect(self.add_new_run)
        self.add_run_action.setEnabled(False)

        file_menu.addSeparator()

        export_frame_action = file_menu.addAction("Export Current &Frame")
        export_frame_action.triggered.connect(self.export_current_frame)

        export_clip_action = file_menu.addAction("Export Current Video &Clip")
        export_clip_action.triggered.connect(self.export_current_video_clip)

        copy_frame_action = file_menu.addAction("&Copy Current Frame")
        copy_frame_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_frame_action.triggered.connect(self.copy_current_frame)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)

        # View menu
        view_menu = menubar.addMenu("&View")
        
        single_view_action = view_menu.addAction("&Single View")
        single_view_action.triggered.connect(lambda: self.set_view_mode("single"))
        
        view_menu.addSeparator()
        
        split_2_action = view_menu.addAction("&Split Screen: 2 Panes")
        split_2_action.triggered.connect(lambda: self.set_view_mode("2-pane"))
        
        split_4_action = view_menu.addAction("S&plit Screen: 4 Panes")
        split_4_action.triggered.connect(lambda: self.set_view_mode("4-pane"))
        
        view_menu.addSeparator()
        
        swap_action = view_menu.addAction("&Swap View (Cycle)")
        swap_action.triggered.connect(lambda: self.set_view_mode("swap"))
        
        view_menu.addSeparator()
        
        clear_view_action = view_menu.addAction("&Clear Current View")
        clear_view_action.triggered.connect(self.clear_current_view)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        info_action = help_menu.addAction("&Info")
        info_action.triggered.connect(self.show_app_info)

    def show_app_info(self):
        """Show application and environment information in a popup dialog."""
        sim_name = "No file loaded"
        if self.current_liufs_handler:
            try:
                sim_name = self.current_liufs_handler.get_simulation_name()
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

            # Verify archive and run exist
            if archive_id not in self.open_archives:
                self.info_label.appendPlainText(f"⚠ Archive not loaded: {archive_id}")
                return
            
            handler = self.open_archives[archive_id]
            if run_name not in handler.get_runs():
                self.info_label.appendPlainText(f"⚠ Run not found: {run_name}")
                return
            
            archive_label = Path(self.open_archive_paths.get(archive_id, archive_id)).stem

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
        if (run_ref.get("archive_id") == self.current_archive_id and 
            run_ref.get("run_name") == self.current_run_name):
            if self.video_player:
                return self.video_player.get_frame(frame_index)
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
            handler = LiufsFileHandler(file_path)

            archive_id = str(Path(file_path).resolve())
            self.open_archives[archive_id] = handler
            self.open_archive_paths[archive_id] = file_path
            self.current_archive_id = archive_id
            self.current_liufs_handler = handler

            self.refresh_file_tree()

            # Update window title
            sim_name = handler.get_simulation_name()
            self.setWindowTitle(
                f"LiU FS Simulation Viewer - {sim_name} ({len(self.open_archives)} open file(s))"
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
        archives_data: list[Dict[str, Any]] = []
        for archive_id, handler in self.open_archives.items():
            label = f"{Path(self.open_archive_paths.get(archive_id, archive_id)).name} | {handler.get_simulation_name()}"
            archives_data.append(
                {
                    "archive_id": archive_id,
                    "label": label,
                    "manifest": handler.manifest,
                }
            )
        self.file_tree.populate_from_archives(archives_data)

    def update_file_actions(self):
        """Enable or disable file actions that depend on an open archive."""
        if self.add_run_action is not None:
            self.add_run_action.setEnabled(bool(self.open_archives))

    def add_new_run(self):
        """Add a new run directory to the currently open .liufs archive."""
        if not self.current_liufs_handler:
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
        if not self.current_liufs_handler:
            return

        self.current_append_source_dir = source_dir

        self.info_label.clear()
        self.info_label.appendPlainText("Starting to add new run...\n")

        self.append_worker = AppendRunWorker(
            self,
            source_dir,
            self.current_liufs_handler.file_path,
            self.current_liufs_handler.file_path,
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
        if not self.open_archives:
            return

        selected = self.file_tree.get_selected_reference()
        archive_id = selected.get("archive_id")
        path = selected.get("path", [])
        if isinstance(archive_id, str) and archive_id in self.open_archives:
            self.current_archive_id = archive_id
            self.current_liufs_handler = self.open_archives[archive_id]

        if len(path) != 1:
            self.reset_option_controls()
            return

        self.load_run_node(path[0])

    def reset_option_controls(self):
        """Reset version/category/dataset/item selectors."""
        self.current_run_name = None
        self.current_version_name = None
        self.current_versions = []
        self.current_group_path = []
        self.current_categories = {}
        self.current_datasets = {}

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
        if not self.current_liufs_handler:
            return

        try:
            runs = self.current_liufs_handler.manifest.get("runs", {}).get("children", {})
            run_node = runs.get(run_name, {}) if isinstance(runs, dict) else {}
            children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
            versions = [name for name, node in (children.items() if isinstance(children, dict) else []) if isinstance(node, dict)]

            if not versions:
                self.reset_option_controls()
                self.info_label.clear()
                self.info_label.appendPlainText("No versions found for this run")
                self.frame_slider.setMaximum(0)
                return

            self.current_run_name = run_name
            self.current_versions = sorted(versions)

            self.version_combo.blockSignals(True)
            self.version_combo.clear()
            for version_name in self.current_versions:
                self.version_combo.addItem(version_name)
            self.version_combo.blockSignals(False)
            self.version_combo.setEnabled(True)

            self.populate_categories_for_version()
        except Exception as e:
            self.info_label.clear()
            self.info_label.appendPlainText(f"❌ Error: {str(e)}")

    def populate_categories_for_version(self):
        """Populate category selector based on selected version."""
        if not self.current_liufs_handler or not self.current_run_name:
            return

        version_name = self.version_combo.currentText()
        if not version_name:
            return

        group_path = [self.current_run_name, version_name]
        self.current_version_name = version_name
        categories = self.current_liufs_handler.get_group_categories(group_path)
        if not categories:
            self.current_group_path = group_path
            self.current_categories = {}
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

        self.current_version_name = version_name
        self.current_group_path = group_path
        self.current_categories = categories

        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        for category_name in sorted(categories.keys()):
            self.category_combo.addItem(category_name)
        self.category_combo.blockSignals(False)
        self.category_combo.setEnabled(True)

        self.populate_datasets_for_category()

    def populate_datasets_for_category(self):
        """Populate dataset selector based on selected category."""
        if not self.current_liufs_handler:
            return

        category_name = self.category_combo.currentText()
        if not category_name:
            return

        datasets = self.current_liufs_handler.get_category_datasets(self.current_group_path, category_name)
        self.current_datasets = datasets

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
        dataset_node = self.current_datasets.get(dataset_name, {})

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
        """Update all pane contexts when selectors change to use new version/category/dataset/item."""
        if not self.split_pane_widget:
            return
        
        # Get current selector values
        version_name = self.version_combo.currentText()
        category_name = self.category_combo.currentText()
        dataset_name = self.dataset_combo.currentText()
        item_name = self.item_combo.currentText()
        
        if not version_name or not category_name or not dataset_name or not item_name:
            return
        
        # Update context for each pane that has a drag-dropped run
        for pane_id in range(self.split_pane_widget.get_pane_count()):
            run_ref = self.pane_run_refs.get(pane_id)
            if not run_ref or not run_ref.get("context"):
                continue
            
            archive_id = run_ref.get("archive_id")
            run_name = run_ref.get("run_name")
            handler = self.open_archives.get(archive_id)
            if not handler:
                continue
            
            # Verify the new selections are valid for this run
            group_path = [run_name, version_name]
            try:
                # Check if version exists for this run
                runs = handler.manifest.get("runs", {}).get("children", {})
                run_node = runs.get(run_name, {})
                children = run_node.get("children", {})
                if version_name not in children:
                    # Version doesn't exist for this run, skip update
                    continue
                
                # Check if category/dataset/item exist
                categories = handler.get_group_categories(group_path)
                if category_name not in categories:
                    continue
                
                datasets = handler.get_category_datasets(group_path, category_name)
                if dataset_name not in datasets:
                    continue
                
                dataset_node = datasets.get(dataset_name, {})
                if dataset_node.get("type") == "cfd_images":
                    items = sorted((dataset_node.get("videos") or {}).keys())
                    if item_name not in items:
                        continue
                
                # All checks passed, update the pane context
                run_ref["context"]["version"] = version_name
                run_ref["context"]["category"] = category_name
                run_ref["context"]["dataset"] = dataset_name
                run_ref["context"]["item"] = item_name
                run_ref["context"]["group_path"] = group_path
            except Exception:
                # Skip if any error occurs during validation
                continue

    def get_compare_run_count(self) -> int:
        return len(self.compare_run_refs)

    def collect_run_refs(self) -> list[Dict[str, Any]]:
        """Collect unique run references from currently open archives."""
        run_refs: list[Dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for archive_id, handler in self.open_archives.items():
            runs = handler.manifest.get("runs", {}).get("children", {})
            if not isinstance(runs, dict):
                continue
            for run_name, run_node in runs.items():
                if not isinstance(run_node, dict):
                    continue
                if not isinstance(run_node.get("children"), dict):
                    continue
                key = (archive_id, run_name)
                if key in seen:
                    continue
                seen.add(key)
                run_refs.append(
                    {
                        "archive_id": archive_id,
                        "run_name": run_name,
                        "label": f"{Path(self.open_archive_paths.get(archive_id, archive_id)).name} | {run_name}",
                    }
                )
        return run_refs

    def get_primary_selection_context(self) -> Dict[str, Any]:
        """Get the current primary selection context (version, category, dataset, item)."""
        return {
            "archive_id": self.current_archive_id,
            "run_name": self.current_run_name,
            "version": self.current_version_name,
            "group_path": list(self.current_group_path),
            "category": self.category_combo.currentText(),
            "dataset": self.dataset_combo.currentText(),
            "item": self.item_combo.currentText(),
        }

    def get_compare_run_pixmap(self, ref: Dict[str, Any], frame_index: int) -> Optional[QPixmap]:
        """Get a frame from a compare run's video."""
        context = self.get_primary_selection_context()
        key = (
            str(ref.get("archive_id")),
            str(ref.get("run_name")),
            str(context.get("version") or ""),
            str(context.get("category") or ""),
            str(context.get("dataset") or ""),
            str(context.get("item") or ""),
        )
        cached_player = self.compare_video_cache.get(key)
        if cached_player is not None:
            pixmap = cached_player.get_frame(min(frame_index, max(cached_player.get_total_frames() - 1, 0)))
            if pixmap:
                return pixmap

        handler = self.open_archives.get(ref.get("archive_id"))
        if not handler:
            return None

        version = context.get("version")
        category = context.get("category")
        dataset = context.get("dataset")
        item = context.get("item")
        if not isinstance(version, str) or not version:
            return None

        compare_group_path = [ref.get("run_name"), version]
        datasets = handler.get_category_datasets(compare_group_path, category)
        dataset_node = datasets.get(dataset, {})
        if not isinstance(dataset_node, dict):
            return None

        rel_video_path = (dataset_node.get("videos") or {}).get(item)
        if not isinstance(rel_video_path, str):
            return None

        archive_path = handler.resolve_archive_path(compare_group_path, rel_video_path)
        video_data = handler.get_file(archive_path)
        if not video_data:
            return None

        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp()

        safe_name = hashlib.sha1(
            f"{key[0]}::{key[1]}::{archive_path}".encode("utf-8")
        ).hexdigest()
        temp_video_path = Path(self.temp_dir) / f"compare_{safe_name}.mp4"
        temp_video_path.parent.mkdir(parents=True, exist_ok=True)
        temp_video_path.write_bytes(video_data)

        player = VideoPlayer(str(temp_video_path))
        self.compare_video_cache[key] = player
        pixmap = player.get_frame(min(frame_index, max(player.get_total_frames() - 1, 0)))
        return pixmap

    def get_pane_pixmap_with_context(self, run_ref: Dict[str, Any], frame_index: int, pane_context: Dict[str, Any]) -> Optional[QPixmap]:
        """Get pixmap for a pane that has its own selection context (from drag-and-drop)."""
        archive_id = run_ref.get("archive_id")
        run_name = run_ref.get("run_name")
        handler = self.open_archives.get(archive_id)
        if not handler:
            return None
        
        version = pane_context.get("version")
        category = pane_context.get("category")
        dataset = pane_context.get("dataset")
        item = pane_context.get("item")
        
        if not isinstance(version, str) or not version:
            return None
        
        group_path = pane_context.get("group_path", [])
        datasets = handler.get_category_datasets(group_path, category)
        dataset_node = datasets.get(dataset, {})
        if not isinstance(dataset_node, dict):
            return None
        
        rel_video_path = (dataset_node.get("videos") or {}).get(item)
        if not isinstance(rel_video_path, str):
            return None
        
        # Create a cache key that includes the full pane context
        key = (
            str(archive_id),
            str(run_name),
            str(version),
            str(category),
            str(dataset),
            str(item),
        )
        
        cached_player = self.compare_video_cache.get(key)
        if cached_player is not None:
            pixmap = cached_player.get_frame(min(frame_index, max(cached_player.get_total_frames() - 1, 0)))
            if pixmap:
                return pixmap
        
        archive_path = handler.resolve_archive_path(group_path, rel_video_path)
        video_data = handler.get_file(archive_path)
        if not video_data:
            return None
        
        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp()
        
        safe_name = hashlib.sha1(
            f"{key[0]}::{key[1]}::{archive_path}".encode("utf-8")
        ).hexdigest()
        temp_video_path = Path(self.temp_dir) / f"pane_{safe_name}.mp4"
        temp_video_path.parent.mkdir(parents=True, exist_ok=True)
        temp_video_path.write_bytes(video_data)
        
        player = VideoPlayer(str(temp_video_path))
        self.compare_video_cache[key] = player
        pixmap = player.get_frame(min(frame_index, max(player.get_total_frames() - 1, 0)))
        return pixmap
    
    def get_video_frame_count_for_pane(self, run_ref: Dict[str, Any]) -> int:
        """Get frame count for a pane's video without displaying it."""
        pane_context = run_ref.get("context")
        if not pane_context:
            return 0
        
        archive_id = run_ref.get("archive_id")
        run_name = run_ref.get("run_name")
        handler = self.open_archives.get(archive_id)
        if not handler:
            return 0
        
        version = pane_context.get("version")
        category = pane_context.get("category")
        dataset = pane_context.get("dataset")
        item = pane_context.get("item")
        
        if not isinstance(version, str) or not version:
            return 0
        
        group_path = pane_context.get("group_path", [])
        datasets = handler.get_category_datasets(group_path, category)
        dataset_node = datasets.get(dataset, {})
        if not isinstance(dataset_node, dict):
            return 0
        
        rel_video_path = (dataset_node.get("videos") or {}).get(item)
        if not isinstance(rel_video_path, str):
            return 0
        
        # Create a cache key
        key = (
            str(archive_id),
            str(run_name),
            str(version),
            str(category),
            str(dataset),
            str(item),
        )
        
        cached_player = self.compare_video_cache.get(key)
        if cached_player is not None:
            return cached_player.get_total_frames()
        
        # Try to load it temporarily to get frame count
        try:
            archive_path = handler.resolve_archive_path(group_path, rel_video_path)
            video_data = handler.get_file(archive_path)
            if not video_data:
                return 0
            
            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp()
            
            safe_name = hashlib.sha1(
                f"{key[0]}::{key[1]}::{archive_path}".encode("utf-8")
            ).hexdigest()
            temp_video_path = Path(self.temp_dir) / f"pane_probe_{safe_name}.mp4"
            temp_video_path.parent.mkdir(parents=True, exist_ok=True)
            temp_video_path.write_bytes(video_data)
            
            player = VideoPlayer(str(temp_video_path))
            self.compare_video_cache[key] = player
            return player.get_total_frames()
        except Exception:
            return 0
    
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
        if self.video_player:
            frame_counts.append(self.video_player.get_total_frames())
        
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
        """Load currently selected video frame set or static image."""
        if not self.current_liufs_handler:
            return

        category_name = self.category_combo.currentText()
        dataset_name = self.dataset_combo.currentText()
        item_name = self.item_combo.currentText()
        if not category_name or not dataset_name or not item_name:
            return

        dataset_node = self.current_datasets.get(dataset_name)
        if not dataset_node:
            return

        try:
            data_type = dataset_node.get("type")

            if data_type == "cfd_images":
                rel_video_path = (dataset_node.get("videos") or {}).get(item_name)
                if not isinstance(rel_video_path, str):
                    self.info_label.clear()
                    self.info_label.appendPlainText("⚠ Warning: Video path not found in manifest")
                    return

                archive_path = self.current_liufs_handler.resolve_archive_path(self.current_group_path, rel_video_path)
                video_data = self.current_liufs_handler.get_file(archive_path)
                if not video_data:
                    self.info_label.clear()
                    self.info_label.appendPlainText(f"❌ Error: Video file not found in archive\n  Path: {archive_path}")
                    return

                if not self.temp_dir:
                    self.temp_dir = tempfile.mkdtemp()

                temp_video_path = Path(self.temp_dir) / Path(archive_path).name
                temp_video_path.write_bytes(video_data)

                if self.video_player:
                    self.video_player.close()

                try:
                    self.video_player = VideoPlayer(str(temp_video_path))
                except Exception as e:
                    self.info_label.clear()
                    self.info_label.appendPlainText(
                        f"❌ Error: Cannot play video\n"
                        f"  This may be a codec issue or corrupted video file.\n"
                        f"  Details: {str(e)}"
                    )
                    return

                self.current_video_path = str(temp_video_path)
                self.current_media_type = "video"
                self.primary_source = {
                    "archive_id": self.current_archive_id,
                    "group_path": list(self.current_group_path),
                    "category": category_name,
                    "dataset": dataset_name,
                    "item": item_name,
                }

                frame_count = self.video_player.get_total_frames()
                self.frame_slider.setMaximum(max(frame_count - 1, 0))
                self.frame_slider.setValue(0)
                self.frame_slider.setEnabled(frame_count > 0)

                # Set primary run reference for pane 0
                self.pane_run_refs[0] = {
                    "archive_id": self.current_archive_id,
                    "run_name": self.current_run_name,
                    "label": f"{Path(self.open_archive_paths.get(self.current_archive_id, '')).stem} | {self.current_run_name}"
                }
                self.display_frame(0)
                self.update_all_panes()
                self.update_slider_maximum()
                self.info_label.clear()
                self.info_label.appendPlainText(
                    f"✓ Loaded: {category_name}/{dataset_name}/{item_name}\n"
                    f"  Frames: {frame_count} | FPS: {self.video_player.fps:.2f}"
                )

            elif data_type == "3d_views":
                files = dataset_node.get("files") or []
                matching = [path for path in files if isinstance(path, str) and Path(path).name == item_name]
                if not matching:
                    self.info_label.clear()
                    self.info_label.appendPlainText("⚠ Warning: Image path not found in manifest")
                    return

                archive_path = self.current_liufs_handler.resolve_archive_path(self.current_group_path, matching[0])
                image_data = self.current_liufs_handler.get_file(archive_path)
                if not image_data:
                    self.info_label.clear()
                    self.info_label.appendPlainText(f"❌ Error: Image file not found in archive\n  Path: {archive_path}")
                    return

                if self.video_player:
                    self.video_player.close()
                    self.video_player = None

                pixmap = QPixmap()
                if not pixmap.loadFromData(image_data):
                    self.info_label.clear()
                    self.info_label.appendPlainText("❌ Error: Cannot read image file\n  The file may be corrupted or in an unsupported format")
                    return

                self.current_media_type = "image"
                self.primary_source = None
                self.frame_slider.setMaximum(0)
                self.frame_slider.setEnabled(False)
                # Set primary run reference for pane 0
                self.pane_run_refs[0] = {
                    "archive_id": self.current_archive_id,
                    "run_name": self.current_run_name,
                    "label": f"{Path(self.open_archive_paths.get(self.current_archive_id, '')).stem} | {self.current_run_name}"
                }
                # Display the static image
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
        """
        Display a specific frame in all panes.
        
        Args:
            frame_index: Index of frame to display
        """
        if not self.video_player and not self.pane_run_refs:
            return

        try:
            self.frame_slider.blockSignals(True)
            self.frame_slider.setValue(frame_index)
            self.frame_slider.blockSignals(False)

            self.update_all_panes()

            if self.video_player:
                frame_count = self.video_player.get_total_frames()
                self.info_label.clear()
                self.info_label.appendPlainText(f"Frame: {frame_index + 1}/{frame_count}")
            else:
                self.info_label.clear()
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
        if not self.video_player:
            return 80
        fps = self.video_player.fps if self.video_player.fps and self.video_player.fps > 0 else 12.0
        speed = self.get_speed_multiplier()
        interval = int(1000 / max(fps * speed, 0.1))
        return max(interval, 10)

    def start_playback(self):
        """Start playback."""
        # Allow playback if we have video player or panes with content
        if not self.video_player and not any(self.pane_run_refs.values()):
            return
        self.playback_timer.start(self.get_playback_interval_ms())

    def pause_playback(self):
        """Pause playback."""
        self.playback_timer.stop()

    def stop_playback(self):
        """Stop playback and return to frame 0."""
        self.playback_timer.stop()
        # Return to frame 0 if we have video or panes
        if self.video_player or any(self.pane_run_refs.values()):
            self.display_frame(0)

    def on_speed_changed(self, _index: int):
        """Update playback timer interval when speed changes."""
        if self.playback_timer.isActive():
            self.playback_timer.start(self.get_playback_interval_ms())

    def advance_playback(self):
        """Advance playback by one synchronized frame."""
        # Get max frame count from video player or panes
        max_frame = 0
        if self.video_player:
            max_frame = self.video_player.get_total_frames() - 1
            if self.compare_video_player:
                max_frame = min(max_frame, self.compare_video_player.get_total_frames() - 1)
        else:
            # No main video, use frame slider maximum from panes
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
        # Get max frame count from video player or panes
        max_frame = 0
        if self.video_player:
            max_frame = self.video_player.get_total_frames() - 1
        else:
            # No main video, check frame slider for frame count from panes
            max_frame = self.frame_slider.maximum()
        
        if max_frame <= 0:
            return
        
        current = self.frame_slider.value()
        next_frame = min(current + 1, max_frame)
        self.display_frame(next_frame)
    
    def previous_frame(self):
        """Move to previous frame."""
        # Get max frame count from video player or panes
        max_frame = 0
        if self.video_player:
            max_frame = self.video_player.get_total_frames() - 1
        else:
            # No main video, use frame slider for frame count from panes
            max_frame = self.frame_slider.maximum()
        
        if max_frame <= 0:
            return
        
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

        if pixmap.save(output_path):
            self.info_label.appendPlainText(f"✓ Exported frame: {output_path}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to export current frame.")

    def export_current_video_clip(self):
        """Export currently selected video clip file."""
        source = self.current_video_path
        if not source:
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

        try:
            shutil.copy2(source, output_path)
            self.info_label.appendPlainText(f"✓ Exported video clip: {output_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export clip:\n{str(e)}")

    def copy_current_frame(self):
        """Copy current frame to clipboard."""
        pixmap = self.get_current_pixmap()
        if not pixmap:
            self.info_label.appendPlainText("⚠ Warning: No frame to copy")
            return
        QApplication.clipboard().setPixmap(pixmap)
        self.info_label.appendPlainText("✓ Copied current frame to clipboard")
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.playback_timer.stop()
        if self.video_player:
            self.video_player.close()
        if self.compare_video_player:
            self.compare_video_player.close()
        for player in self.compare_video_cache.values():
            player.close()
        for window in self.detached_windows.values():
            window.close()
        
        # Clean up temp directory
        if self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
        
        event.accept()


if __name__ == "__main__":
    # For direct execution: python app/main.py
    app = QApplication(sys.argv)
    
    window = ViewerWindow()
    window.show()
    
    sys.exit(app.exec())
