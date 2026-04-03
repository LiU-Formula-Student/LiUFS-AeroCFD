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
from PySide6.QtCore import Qt, qVersion, QThread, Signal, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap

from .liufs_handler import LiufsFileHandler, LiufsValidationError
from .file_tree import FileTreeWidget
from simulation_compressor.packager import DuplicateRunError, append_run_to_liufs
from simulation_compressor.reporting import BaseReporter, ProgressEvent
from .video_player import VideoPlayer
from .version import APP_VERSION


class GUIReporter(BaseReporter):
    """Reporter that updates through a callback signal."""

    def __init__(self, progress_signal):
        self.progress_signal = progress_signal

    def emit(self, event: ProgressEvent) -> None:
        """Update via signal with progress information."""
        if event.kind == "step_start":
            message = event.data.get("message", "Processing...") if event.data else "Processing..."
            self.progress_signal.emit(f"► {message}")
        elif event.kind == "step_end":
            message = event.data.get("message", "Step complete") if event.data else "Step complete"
            self.progress_signal.emit(f"✓ {message}")
        elif event.kind == "progress":
            message = event.data.get("message", "") if event.data else ""
            if message:
                self.progress_signal.emit(f"  {message}")
        elif event.kind == "log":
            message = event.data.get("message", "") if event.data else ""
            if message:
                self.progress_signal.emit(message)
        elif event.kind == "warning":
            message = event.data.get("message", "") if event.data else ""
            if message:
                self.progress_signal.emit(f"⚠ {message}")

    def advance(self, message: str, **data: Any) -> None:
        """Emit an advance message."""
        self.progress_signal.emit(f"  {message}")

    def log(self, message: str, **data: Any) -> None:
        """Log a message."""
        self.progress_signal.emit(message)

    def warn(self, message: str, **data: Any) -> None:
        """Emit a warning."""
        self.progress_signal.emit(f"⚠ {message}")

class AppendRunWorker(QThread):
    """Worker thread for appending a run to an existing archive."""

    progress_updated = Signal(str)
    finished = Signal(Path)
    error = Signal(str)
    duplicate_error = Signal(str, list)

    def __init__(self, parent, source_dir: str, archive_file: Path, output_file: Path, run_name: str | None):
        super().__init__(parent)
        self.source_dir = source_dir
        self.archive_file = archive_file
        self.output_file = output_file
        self.run_name = run_name

    def run(self):
        """Run the append operation in the background."""
        try:
            reporter = GUIReporter(self.progress_updated)
            result = append_run_to_liufs(
                source_dir=self.source_dir,
                archive_file=self.archive_file,
                output_file=self.output_file,
                run_name=self.run_name,
                reporter=reporter,
            )
            self.finished.emit(result)
        except DuplicateRunError as exc:
            self.duplicate_error.emit(exc.run_name, exc.existing_runs)
        except Exception as e:
            self.error.emit(str(e))


class CompareWindow(QMainWindow):
    """Detached window for stacked comparison on a second screen."""

    def __init__(self, main_window: "ViewerWindow"):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Compare Runs")
        self.setGeometry(150, 150, 1200, 900)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.title_label = QLabel("Comparisons")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(self.title_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.scroll)

        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll.setWidget(self.scroll_widget)

    def sync_from_main(self):
        """Refresh content from the main window state."""
        primary = self.main_window.describe_current_primary_run()
        self.title_label.setText(f"Primary: {primary}")
        self.rebuild_compare_panels()

    def rebuild_compare_panels(self):
        """Render the compare stack in this window."""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.main_window.compare_run_refs:
            empty = QLabel("Add runs to compare")
            self.scroll_layout.addWidget(empty)
            return

        context = self.main_window.get_primary_selection_context()
        available_height = max(self.height(), 600)
        panel_height = max(int((available_height - 40) / (1 + len(self.main_window.compare_run_refs))), 180)

        primary_pixmap = self.main_window.get_current_primary_pixmap()
        self.scroll_layout.addWidget(
            self.main_window.create_compare_panel(
                title=f"Primary: {self.main_window.describe_current_primary_run()}",
                pixmap=primary_pixmap,
                height=panel_height,
            )
        )

        for ref in self.main_window.compare_run_refs:
            pixmap = self.main_window.get_compare_run_pixmap(ref, self.main_window.frame_slider.value())
            self.scroll_layout.addWidget(
                self.main_window.create_compare_panel(
                    title=f"Compare: {ref.get('label', 'Run')}",
                    pixmap=pixmap,
                    height=panel_height,
                )
            )

        self.scroll_layout.addStretch(1)


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
        self.current_categories: Dict[str, Dict[str, Any]] = {}
        self.current_datasets: Dict[str, Dict[str, Any]] = {}
        self.current_media_type: Optional[str] = None
        self.primary_source: Optional[Dict[str, Any]] = None
        self.compare_run_refs: list[Dict[str, Any]] = []
        self.selected_compare_index: int = 0
        self.swap_index: int = 0
        self.compare_video_cache: Dict[tuple[str, str], VideoPlayer] = {}
        self.add_run_action = None
        self.append_worker: Optional[AppendRunWorker] = None
        self.current_append_source_dir: Optional[str] = None
        self.compare_window = None

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
        
        # Right panel: Video viewer with slider
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        # Mode controls
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("View Mode"))
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Single", "Side by Side", "Swap"])
        self.view_mode_combo.currentIndexChanged.connect(self.on_view_mode_changed)
        mode_layout.addWidget(self.view_mode_combo)

        mode_layout.addSpacing(12)
        mode_layout.addWidget(QLabel("Compare Run"))
        self.compare_run_combo = QComboBox()
        self.compare_run_combo.setEnabled(False)
        mode_layout.addWidget(self.compare_run_combo)

        self.add_compare_button = QPushButton("Add")
        self.add_compare_button.setEnabled(False)
        self.add_compare_button.clicked.connect(self.add_compare_run)
        mode_layout.addWidget(self.add_compare_button)

        self.remove_compare_button = QPushButton("Remove")
        self.remove_compare_button.setEnabled(False)
        self.remove_compare_button.clicked.connect(self.remove_last_compare_run)
        mode_layout.addWidget(self.remove_compare_button)

        self.clear_compare_button = QPushButton("Clear")
        self.clear_compare_button.setEnabled(False)
        self.clear_compare_button.clicked.connect(self.clear_compare_runs)
        mode_layout.addWidget(self.clear_compare_button)

        self.popout_compare_button = QPushButton("Pop Out")
        self.popout_compare_button.setEnabled(False)
        self.popout_compare_button.clicked.connect(self.open_compare_window)
        mode_layout.addWidget(self.popout_compare_button)

        mode_layout.addStretch(1)
        right_layout.addLayout(mode_layout)

        # Image display area
        self.image_panel = QWidget()
        image_layout = QHBoxLayout()
        image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_panel.setLayout(image_layout)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        self.image_label.setMinimumHeight(600)
        image_layout.addWidget(self.image_label)

        self.compare_image_label = QLabel()
        self.compare_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compare_image_label.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        self.compare_image_label.setMinimumHeight(600)
        self.compare_image_label.hide()
        image_layout.addWidget(self.compare_image_label)

        right_layout.addWidget(self.image_panel)

        self.compare_section = QWidget()
        compare_section_layout = QVBoxLayout()
        compare_section_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_section.setLayout(compare_section_layout)

        self.compare_section_title = QLabel("Comparisons")
        compare_section_layout.addWidget(self.compare_section_title)

        self.compare_scroll = QScrollArea()
        self.compare_scroll.setWidgetResizable(True)
        self.compare_scroll.setMinimumHeight(220)
        self.compare_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.compare_scroll_widget = QWidget()
        self.compare_scroll_layout = QVBoxLayout()
        self.compare_scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.compare_scroll_widget.setLayout(self.compare_scroll_layout)
        self.compare_scroll.setWidget(self.compare_scroll_widget)
        compare_section_layout.addWidget(self.compare_scroll)

        self.compare_section.hide()
        right_layout.addWidget(self.compare_section)

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

        # Controls for category/dataset/item selection
        controls_layout = QHBoxLayout()

        category_label = QLabel("Category")
        self.category_combo = QComboBox()
        self.category_combo.setEnabled(False)
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)

        dataset_label = QLabel("Dataset")
        self.dataset_combo = QComboBox()
        self.dataset_combo.setEnabled(False)
        self.dataset_combo.currentIndexChanged.connect(self.on_dataset_changed)

        item_label = QLabel("Item")
        self.item_combo = QComboBox()
        self.item_combo.setEnabled(False)
        self.item_combo.currentIndexChanged.connect(self.on_item_changed)

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
        QShortcut(Qt.Key.Key_Up, self, self.swap_previous)
        QShortcut(Qt.Key.Key_Down, self, self.swap_next)
    
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
            
            self.image_label.setText("Select a run/image-group from the tree to view")
            self.info_label.clear()
            visible_runs = handler.get_runs()
            self.info_label.appendPlainText(
                f"✓ File loaded successfully\n"
                f"  File: {Path(file_path).name}\n"
                f"  Simulation: {sim_name}\n"
                f"  Runs: {', '.join(visible_runs) if visible_runs else '(none)'}"
            )

            warnings = handler.get_validation_warnings()
            for warning in warnings:
                self.info_label.appendPlainText(f"⚠ Warning: {warning}")

            self.reset_option_controls()
            self.refresh_compare_sources()
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

        if len(path) != 2:
            self.reset_option_controls()
            return

        self.load_group_node(path)

    def reset_option_controls(self):
        """Reset category/dataset/item selectors."""
        self.current_group_path = []
        self.current_categories = {}
        self.current_datasets = {}

        self.category_combo.blockSignals(True)
        self.dataset_combo.blockSignals(True)
        self.item_combo.blockSignals(True)

        self.category_combo.clear()
        self.dataset_combo.clear()
        self.item_combo.clear()

        self.category_combo.blockSignals(False)
        self.dataset_combo.blockSignals(False)
        self.item_combo.blockSignals(False)

        self.category_combo.setEnabled(False)
        self.dataset_combo.setEnabled(False)
        self.item_combo.setEnabled(False)

    def load_group_node(self, group_path: list[str]):
        """Load available categories from selected [run, image_group]."""
        if not self.current_liufs_handler:
            return

        try:
            categories = self.current_liufs_handler.get_group_categories(group_path)
            if not categories:
                self.reset_option_controls()
                self.image_label.setText("No categories found for this node")
                self.frame_slider.setMaximum(0)
                return

            self.current_group_path = group_path
            self.current_categories = categories

            self.category_combo.blockSignals(True)
            self.category_combo.clear()
            for category_name in sorted(categories.keys()):
                self.category_combo.addItem(category_name)
            self.category_combo.blockSignals(False)
            self.category_combo.setEnabled(True)

            self.populate_datasets_for_category()
        except Exception as e:
            self.image_label.setText(f"Error: {str(e)}")
            self.info_label.setText("Failed to load options")

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
            self.load_selected_media()

    def on_category_changed(self, _index: int):
        """Handle category selector change."""
        self.populate_datasets_for_category()

    def on_dataset_changed(self, _index: int):
        """Handle dataset selector change."""
        self.populate_items_for_dataset()

    def on_item_changed(self, _index: int):
        """Handle item selector change."""
        self.load_selected_media()

    def on_view_mode_changed(self, _index: int):
        """Handle view mode changes between single/side-by-side/swap."""
        mode = self.view_mode_combo.currentText()
        self.compare_section.setVisible(mode == "Side by Side")
        self.compare_image_label.setVisible(False)
        self.compare_run_combo.setEnabled(mode in {"Side by Side", "Swap"})
        self.add_compare_button.setEnabled(mode in {"Side by Side", "Swap"})
        self.remove_compare_button.setEnabled(mode in {"Side by Side", "Swap"})
        self.clear_compare_button.setEnabled(mode in {"Side by Side", "Swap"})
        self.popout_compare_button.setEnabled(mode in {"Side by Side", "Swap"})
        if mode == "Single":
            if self.compare_video_player:
                self.compare_video_player.close()
                self.compare_video_player = None
            self.compare_image_label.clear()
            self.compare_section.hide()
            self.swap_index = 0
            self.update_compare_display_for_frame(self.frame_slider.value())

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

    def refresh_compare_sources(self):
        """Refresh run-only compare selector from all open archives."""
        refs = self.collect_run_refs()
        current = self.compare_run_combo.currentData()
        current_key = None
        if isinstance(current, dict):
            current_key = (current.get("archive_id"), current.get("run_name"))

        self.compare_run_combo.blockSignals(True)
        self.compare_run_combo.clear()
        self.compare_run_combo.addItem("(Select run)", None)
        for ref in refs:
            self.compare_run_combo.addItem(ref["label"], ref)
        if current_key:
            for idx in range(self.compare_run_combo.count()):
                data = self.compare_run_combo.itemData(idx)
                if isinstance(data, dict) and (data.get("archive_id"), data.get("run_name")) == current_key:
                    self.compare_run_combo.setCurrentIndex(idx)
                    break
        self.compare_run_combo.blockSignals(False)
        self.update_compare_controls_state()

    def update_compare_controls_state(self):
        enabled = bool(self.open_archives) and self.view_mode_combo.currentText() in {"Side by Side", "Swap"}
        self.compare_run_combo.setEnabled(enabled)
        self.add_compare_button.setEnabled(enabled)
        self.remove_compare_button.setEnabled(enabled)
        self.clear_compare_button.setEnabled(enabled)
        self.popout_compare_button.setEnabled(enabled)
        self.compare_section.setVisible(self.view_mode_combo.currentText() == "Side by Side" and bool(self.compare_run_refs))
        self.compare_image_label.setVisible(False)

    def add_compare_run(self):
        """Add selected run to comparison list."""
        ref = self.compare_run_combo.currentData()
        if not isinstance(ref, dict):
            return

        key = (ref.get("archive_id"), ref.get("run_name"))
        if key in {(r.get("archive_id"), r.get("run_name")) for r in self.compare_run_refs}:
            return

        self.compare_run_refs.append(ref)
        self.selected_compare_index = max(0, len(self.compare_run_refs) - 1)
        self.swap_index = self.selected_compare_index
        self.update_compare_views()

    def remove_last_compare_run(self):
        """Remove the most recently added compare run."""
        if self.compare_run_refs:
            self.compare_run_refs.pop()
            self.selected_compare_index = min(self.selected_compare_index, max(len(self.compare_run_refs) - 1, 0))
            self.swap_index = min(self.swap_index, max(len(self.compare_run_refs), 0))
            self.update_compare_views()

    def clear_compare_runs(self):
        """Clear all compare runs."""
        self.compare_run_refs.clear()
        self.selected_compare_index = 0
        self.swap_index = 0
        self.update_compare_views()

    def open_compare_window(self):
        """Open a separate compare window for multi-screen workflows."""
        if self.compare_window is None:
            self.compare_window = CompareWindow(self)
        self.compare_window.show()
        self.compare_window.raise_()
        self.compare_window.activateWindow()

    def update_compare_views(self):
        """Refresh compare panels and swap view from current primary frame."""
        self.update_compare_controls_state()
        self.rebuild_compare_panels()
        self.update_compare_display_for_frame(self.frame_slider.value())
        if self.compare_window:
            self.compare_window.sync_from_main()

    def get_primary_selection_context(self) -> Dict[str, Any]:
        return {
            "archive_id": self.current_archive_id,
            "group_path": list(self.current_group_path),
            "category": self.category_combo.currentText(),
            "dataset": self.dataset_combo.currentText(),
            "item": self.item_combo.currentText(),
        }

    def rebuild_compare_panels(self):
        """Rebuild stacked compare panels in the main window."""
        while self.compare_scroll_layout.count():
            item = self.compare_scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.compare_run_refs or self.view_mode_combo.currentText() != "Side by Side":
            return

        context = self.get_primary_selection_context()
        total_panels = 1 + len(self.compare_run_refs)
        available_height = max(self.image_label.height(), 600)
        panel_height = max(int((available_height - 10 * total_panels) / total_panels), 180)

        primary_panel = self.create_compare_panel(
            title=f"Primary: {context.get('run_label', self.describe_current_primary_run())}",
            pixmap=self.get_current_primary_pixmap(),
            height=panel_height,
        )
        self.compare_scroll_layout.addWidget(primary_panel)

        for ref in self.compare_run_refs:
            panel = self.create_compare_panel(
                title=f"Compare: {ref.get('label', 'Run')}",
                pixmap=self.get_compare_run_pixmap(ref, self.frame_slider.value()),
                height=panel_height,
            )
            self.compare_scroll_layout.addWidget(panel)

        self.compare_scroll_layout.addStretch(1)

    def describe_current_primary_run(self) -> str:
        if not self.current_archive_id or not self.current_group_path:
            return "Primary"
        archive_name = Path(self.open_archive_paths.get(self.current_archive_id, self.current_archive_id)).name
        return f"{archive_name} | {self.current_group_path[0]}"

    def create_compare_panel(self, title: str, pixmap: Optional[QPixmap], height: int) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel.setLayout(layout)

        label = QLabel(title)
        label.setStyleSheet("font-weight: 600; color: #cccccc;")
        layout.addWidget(label)

        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        image.setMinimumHeight(height)
        image.setMaximumHeight(height)
        if pixmap:
            image.setPixmap(self.scale_pixmap_to_fit(pixmap, height))
        else:
            image.setText("No image available")
        layout.addWidget(image)
        return panel

    def get_current_primary_pixmap(self) -> Optional[QPixmap]:
        return self.image_label.pixmap()

    def scale_pixmap_to_fit(self, pixmap: QPixmap, target_height: int) -> QPixmap:
        return pixmap.scaledToHeight(max(target_height - 20, 50), Qt.TransformationMode.SmoothTransformation)

    def get_compare_run_pixmap(self, ref: Dict[str, Any], frame_index: int) -> Optional[QPixmap]:
        key = (str(ref.get("archive_id")), str(ref.get("run_name")))
        cached_player = self.compare_video_cache.get(key)
        if cached_player is not None:
            pixmap = cached_player.get_frame(min(frame_index, max(cached_player.get_total_frames() - 1, 0)))
            if pixmap:
                return pixmap

        handler = self.open_archives.get(ref.get("archive_id"))
        if not handler:
            return None

        primary_context = self.get_primary_selection_context()
        group_path = primary_context.get("group_path")
        category = primary_context.get("category")
        dataset = primary_context.get("dataset")
        item = primary_context.get("item")
        if not isinstance(group_path, list) or len(group_path) < 2:
            return None

        compare_group_path = [ref.get("run_name"), group_path[1]]
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

    def update_compare_display_for_frame(self, frame_index: int):
        """Render current frame according to selected view mode."""
        mode = self.view_mode_combo.currentText()
        if mode == "Single":
            return

        if mode == "Side by Side":
            self.rebuild_compare_panels()
            if self.compare_window:
                self.compare_window.rebuild_compare_panels()
        elif mode == "Swap":
            if not self.compare_run_refs:
                self.image_label.setText("Add runs to compare")
                return
            active_ref = self.compare_run_refs[self.swap_index % len(self.compare_run_refs)]
            pixmap = self.get_compare_run_pixmap(active_ref, frame_index)
            if pixmap:
                self.image_label.setPixmap(self.scale_pixmap_to_fit(pixmap, self.image_label.height()))
                self.image_label.setText("")
                self.info_label.clear()
                self.info_label.appendPlainText(
                    f"Swap view\n"
                    f"  Primary: {self.describe_current_primary_run()}\n"
                    f"  Selected: {active_ref.get('label', 'Run')}"
                )

    def swap_next(self):
        """Advance to next compare run in swap mode (Down key)."""
        if self.view_mode_combo.currentText() != "Swap" or not self.compare_run_refs:
            return
        self.swap_index = (self.swap_index + 1) % len(self.compare_run_refs)
        self.display_frame(self.frame_slider.value())

    def swap_previous(self):
        """Move to previous compare run in swap mode (Up key)."""
        if self.view_mode_combo.currentText() != "Swap" or not self.compare_run_refs:
            return
        self.swap_index = (self.swap_index - 1) % len(self.compare_run_refs)
        self.display_frame(self.frame_slider.value())

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
                    self.image_label.setText("Selected plane video is missing in manifest")
                    self.info_label.clear()
                    self.info_label.appendPlainText("⚠ Warning: Video path not found in manifest")
                    return

                archive_path = self.current_liufs_handler.resolve_archive_path(self.current_group_path, rel_video_path)
                video_data = self.current_liufs_handler.get_file(archive_path)
                if not video_data:
                    self.image_label.setText("Error: Cannot extract video file")
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
                    self.image_label.setText("Error: Cannot read video file")
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

                self.display_frame(0)
                self.info_label.clear()
                self.info_label.appendPlainText(
                    f"✓ Loaded: {category_name}/{dataset_name}/{item_name}\n"
                    f"  Frames: {frame_count} | FPS: {self.video_player.fps:.2f}"
                )
                self.refresh_compare_sources()
                self.update_compare_views()

            elif data_type == "3d_views":
                files = dataset_node.get("files") or []
                matching = [path for path in files if isinstance(path, str) and Path(path).name == item_name]
                if not matching:
                    self.image_label.setText("Selected image is missing in manifest")
                    self.info_label.clear()
                    self.info_label.appendPlainText("⚠ Warning: Image path not found in manifest")
                    return

                archive_path = self.current_liufs_handler.resolve_archive_path(self.current_group_path, matching[0])
                image_data = self.current_liufs_handler.get_file(archive_path)
                if not image_data:
                    self.image_label.setText("Error: Cannot extract image file")
                    self.info_label.clear()
                    self.info_label.appendPlainText(f"❌ Error: Image file not found in archive\n  Path: {archive_path}")
                    return

                if self.video_player:
                    self.video_player.close()
                    self.video_player = None

                pixmap = QPixmap()
                if not pixmap.loadFromData(image_data):
                    self.image_label.setText("Error: Failed to decode image")
                    self.info_label.clear()
                    self.info_label.appendPlainText("❌ Error: Cannot read image file\n  The file may be corrupted or in an unsupported format")
                    return

                scaled = pixmap.scaledToHeight(600, Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled)
                self.current_media_type = "image"
                self.primary_source = None
                self.frame_slider.setMaximum(0)
                self.frame_slider.setEnabled(False)
                self.info_label.clear()
                self.info_label.appendPlainText(
                    f"✓ Loaded: {category_name}/{dataset_name}/{item_name}\n"
                    f"  Size: {pixmap.width()}x{pixmap.height()} px"
                )
                self.refresh_compare_sources()
                self.update_compare_views()
            else:
                self.image_label.setText(f"Unknown media type: {data_type}")
                self.info_label.clear()
                self.info_label.appendPlainText(f"⚠ Warning: Unknown media type '{data_type}'")
        except Exception as e:
            self.image_label.setText("Error loading media")
            self.info_label.clear()
            self.info_label.appendPlainText(f"❌ Error: {str(e)}")
    
    def display_frame(self, frame_index: int):
        """
        Display a specific frame.
        
        Args:
            frame_index: Index of frame to display
        """
        if not self.video_player:
            return

        mode = self.view_mode_combo.currentText()

        try:
            active_player = self.video_player
            active_label = "Primary"
            if mode == "Swap" and self.compare_run_refs:
                active_ref = self.compare_run_refs[self.swap_index % len(self.compare_run_refs)]
                pixmap = self.get_compare_run_pixmap(active_ref, frame_index)
                active_label = active_ref.get("label", "Run")
            else:
                pixmap = active_player.get_frame(frame_index)
            if not pixmap:
                self.image_label.setText(f"Error: Cannot read frame {frame_index}")
                return
            
            # Scale to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaledToHeight(
                self.image_label.height() - 20,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.update_compare_display_for_frame(frame_index)

            self.frame_slider.blockSignals(True)
            self.frame_slider.setValue(frame_index)
            self.frame_slider.blockSignals(False)

            current_frame = frame_index
            total_frames = active_player.get_total_frames() if mode != "Swap" or not self.compare_run_refs else max(1, frame_index + 1)
            self.info_label.clear()
            if mode == "Swap" and self.compare_run_refs:
                self.info_label.appendPlainText(
                    f"Frame: {current_frame + 1}/{total_frames}\n"
                    f"Primary: {self.describe_current_primary_run()}\n"
                    f"Selected: {active_label}"
                )
            else:
                self.info_label.appendPlainText(f"Frame: {current_frame + 1}/{total_frames}")
            if mode == "Side by Side":
                self.update_compare_display_for_frame(frame_index)
        except Exception as e:
            self.image_label.setText(f"Error displaying frame: {str(e)}")
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
        if not self.video_player:
            return
        self.playback_timer.start(self.get_playback_interval_ms())

    def pause_playback(self):
        """Pause playback."""
        self.playback_timer.stop()

    def stop_playback(self):
        """Stop playback and return to frame 0."""
        self.playback_timer.stop()
        if self.video_player:
            self.display_frame(0)

    def on_speed_changed(self, _index: int):
        """Update playback timer interval when speed changes."""
        if self.playback_timer.isActive():
            self.playback_timer.start(self.get_playback_interval_ms())

    def advance_playback(self):
        """Advance playback by one synchronized frame."""
        if not self.video_player:
            self.pause_playback()
            return

        max_frame = self.video_player.get_total_frames() - 1
        if self.compare_video_player:
            max_frame = min(max_frame, self.compare_video_player.get_total_frames() - 1)

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
        if not self.video_player:
            return
        
        current = self.video_player.current_frame_index
        next_frame = min(current + 1, self.video_player.get_total_frames() - 1)
        self.display_frame(next_frame)
    
    def previous_frame(self):
        """Move to previous frame."""
        if not self.video_player:
            return
        
        current = self.video_player.current_frame_index
        prev_frame = max(current - 1, 0)
        self.display_frame(prev_frame)

    def get_current_pixmap(self) -> Optional[QPixmap]:
        """Return currently displayed pixmap from active view."""
        pixmap = self.image_label.pixmap()
        return pixmap if pixmap else None

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
