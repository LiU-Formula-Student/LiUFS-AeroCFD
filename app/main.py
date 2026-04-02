"""
Main application window for the .liufs viewer.
"""

import platform
import sys
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QSplitter, QMessageBox, QFileDialog, QComboBox,
    QDialog, QDialogButtonBox, QLineEdit, QPlainTextEdit
)
from PySide6.QtCore import Qt, qVersion, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap

from .liufs_handler import LiufsFileHandler
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


class ViewerWindow(QMainWindow):
    """Main viewer window for .liufs files."""
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        
        self.setWindowTitle("LiU FS Simulation Viewer")
        self.setGeometry(100, 100, 1400, 800)
        
        self.current_liufs_handler: Optional[LiufsFileHandler] = None
        self.current_video_path: Optional[str] = None
        self.video_player: Optional[VideoPlayer] = None
        self.temp_dir: Optional[str] = None
        self.current_group_path: list[str] = []
        self.current_categories: Dict[str, Dict[str, Any]] = {}
        self.current_datasets: Dict[str, Dict[str, Any]] = {}
        self.add_run_action = None
        self.append_worker: Optional[AppendRunWorker] = None
        self.current_append_source_dir: Optional[str] = None
        
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
        
        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        self.image_label.setMinimumHeight(600)
        right_layout.addWidget(self.image_label)
        
        # Slider for frame navigation
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.sliderMoved.connect(self.on_slider_moved)
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
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")
    
    def load_liufs_file(self, file_path: str):
        """
        Load a .liufs file and display its structure.
        
        Args:
            file_path: Path to the .liufs file
        """
        try:
            # Clean up previous session
            if self.video_player:
                self.video_player.close()
                self.video_player = None
            
            # Load the file
            self.current_liufs_handler = LiufsFileHandler(file_path)
            
            # Populate the file tree
            self.file_tree.populate_from_manifest(self.current_liufs_handler.manifest)
            
            # Update window title
            sim_name = self.current_liufs_handler.get_simulation_name()
            self.setWindowTitle(f"LiU FS Simulation Viewer - {sim_name}")
            
            self.image_label.setText("Select a run/image-group from the tree to view")
            self.info_label.clear()
            self.info_label.appendPlainText("File loaded successfully")
            self.reset_option_controls()
            self.update_file_actions()
        
        except Exception as e:
            raise e

    def update_file_actions(self):
        """Enable or disable file actions that depend on an open archive."""
        if self.add_run_action is not None:
            self.add_run_action.setEnabled(self.current_liufs_handler is not None)

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
        self.info_label.appendPlainText("\nRun added successfully! Reloading archive...\n")
        try:
            self.load_liufs_file(str(result))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh file after adding run:\n{str(e)}")
            self.info_label.appendPlainText(f"\nError: {str(e)}")

    def _on_append_error(self, error_msg: str):
        """Handle append error."""
        QMessageBox.critical(self, "Error", f"Failed to add run:\n{error_msg}")
        self.info_label.appendPlainText(f"\nError: {error_msg}")

    def _on_append_duplicate_error(self, run_name: str, existing_runs: list):
        """Handle duplicate run error with rename prompt."""
        self.info_label.appendPlainText(f"\nDuplicate run name: '{run_name}'. Prompting for rename...\n")
        renamed_run_name = self.prompt_for_run_rename(run_name)
        if not renamed_run_name:
            self.info_label.appendPlainText("Add run cancelled by user.\n")
            return

        self.info_label.appendPlainText(f"Retrying with run name: '{renamed_run_name}'\n")
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
        if not self.current_liufs_handler:
            return

        path = self.file_tree.get_selected_manifest_path()
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
                    return

                archive_path = self.current_liufs_handler.resolve_archive_path(self.current_group_path, rel_video_path)
                video_data = self.current_liufs_handler.get_file(archive_path)
                if not video_data:
                    self.image_label.setText(f"Error: Cannot extract video file ({archive_path})")
                    return

                if not self.temp_dir:
                    self.temp_dir = tempfile.mkdtemp()

                temp_video_path = Path(self.temp_dir) / Path(archive_path).name
                temp_video_path.write_bytes(video_data)

                if self.video_player:
                    self.video_player.close()

                self.video_player = VideoPlayer(str(temp_video_path))
                self.current_video_path = str(temp_video_path)

                frame_count = self.video_player.get_total_frames()
                self.frame_slider.setMaximum(max(frame_count - 1, 0))
                self.frame_slider.setValue(0)
                self.frame_slider.setEnabled(frame_count > 0)

                self.display_frame(0)
                self.info_label.clear()
                self.info_label.appendPlainText(
                    f"{category_name}/{dataset_name}/{item_name} | Frames: {frame_count} | FPS: {self.video_player.fps:.2f}"
                )

            elif data_type == "3d_views":
                files = dataset_node.get("files") or []
                matching = [path for path in files if isinstance(path, str) and Path(path).name == item_name]
                if not matching:
                    self.image_label.setText("Selected image is missing in manifest")
                    return

                archive_path = self.current_liufs_handler.resolve_archive_path(self.current_group_path, matching[0])
                image_data = self.current_liufs_handler.get_file(archive_path)
                if not image_data:
                    self.image_label.setText(f"Error: Cannot extract image file ({archive_path})")
                    return

                if self.video_player:
                    self.video_player.close()
                    self.video_player = None

                pixmap = QPixmap()
                if not pixmap.loadFromData(image_data):
                    self.image_label.setText("Error: Failed to decode image")
                    return

                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled_pixmap)
                self.frame_slider.setValue(0)
                self.frame_slider.setMaximum(0)
                self.frame_slider.setEnabled(False)
                self.info_label.clear()
                self.info_label.appendPlainText(f"{category_name}/{dataset_name}/{item_name} | Static image")

            else:
                self.image_label.setText("Selected dataset type is not supported yet")
                self.frame_slider.setMaximum(0)
                self.frame_slider.setEnabled(False)

        except Exception as e:
            self.image_label.setText(f"Error: {str(e)}")
            self.info_label.clear()
            self.info_label.appendPlainText(f"Error: {str(e)}")
    
    def display_frame(self, frame_index: int):
        """
        Display a specific frame.
        
        Args:
            frame_index: Index of frame to display
        """
        if not self.video_player:
            return
        
        pixmap = self.video_player.get_frame(frame_index)
        if pixmap:
            # Scale to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaledToHeight(
                self.image_label.height() - 20,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            
            # Update slider without triggering callback
            self.frame_slider.blockSignals(True)
            self.frame_slider.setValue(frame_index)
            self.frame_slider.blockSignals(False)
            
            current_frame = self.video_player.current_frame_index
            total_frames = self.video_player.get_total_frames()
            self.info_label.clear()
            self.info_label.appendPlainText(
                f"Frame: {current_frame + 1}/{total_frames}"
            )
    
    def on_slider_moved(self, value: int):
        """Handle slider movement."""
        self.display_frame(value)
    
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
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.video_player:
            self.video_player.close()
        
        # Clean up temp directory
        if self.temp_dir:
            import shutil
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
