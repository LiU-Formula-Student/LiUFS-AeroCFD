"""Reusable viewer components for pane rendering and background tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel

from aerocfd_cli.packager import DuplicateRunError, append_run_to_liufs
from aerocfd_cli.reporting import BaseReporter, ProgressEvent


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


class DetachedImageWindow(QMainWindow):
    """Detached single-stream image window for multi-screen comparison."""

    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setGeometry(150, 150, 1000, 700)
        self.original_pixmap: Optional[QPixmap] = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self.title_label)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        layout.addWidget(self.image_label)

    def update_content(self, title: str, pixmap: Optional[QPixmap]):
        self.setWindowTitle(title)
        self.title_label.setText(title)
        if pixmap is None:
            self.image_label.setText("No image available")
            self.image_label.setPixmap(QPixmap())
            self.original_pixmap = None
            return
        self.original_pixmap = pixmap
        self._update_pixmap_display()

    def _update_pixmap_display(self):
        """Scale and display the original pixmap to fit current label size."""
        if not self.original_pixmap:
            return
        scaled = self.original_pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        """Handle window resize events to rescale displayed pixmap."""
        super().resizeEvent(event)
        self._update_pixmap_display()


class ImagePane(QWidget):
    """Single image display pane with run info."""

    run_dropped = Signal(int, str, str)  # pane_id, archive_id, run_name

    def __init__(self, pane_id: int):
        super().__init__()
        self.pane_id = pane_id
        self.run_info: Optional[Dict[str, Any]] = None
        self.original_pixmap: Optional[QPixmap] = None  # Store original for resizing

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        self.setLayout(layout)

        self.title_label = QLabel(f"Pane {pane_id}")
        self.title_label.setStyleSheet("color: #cccccc; font-size: 11px; font-weight: 600;")
        self.title_label.setFixedHeight(20)
        layout.addWidget(self.title_label)

        self.label = QLabel("(Drag run here)")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("background-color: #1e1e1e; color: #888888; font-size: 11px;")
        self.label.setMinimumHeight(200)
        layout.addWidget(self.label)

        self.setAcceptDrops(True)

    def set_content(self, title: str, pixmap: Optional[QPixmap]):
        """Update pane content."""
        self.run_info = {"title": title}
        self.title_label.setText(title)
        if pixmap is None:
            self.label.setText("(no image)")
            self.label.setPixmap(QPixmap())
            self.original_pixmap = None
            return
        self.label.setText("")
        # Store original pixmap for resizing
        self.original_pixmap = pixmap
        # Scale to current label size
        self._update_pixmap_display()

    def _update_pixmap_display(self):
        """Scale and display the original pixmap to fit current label size."""
        if not self.original_pixmap:
            return
        scaled = self.original_pixmap.scaled(
            self.label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.label.setPixmap(scaled)

    def clear(self):
        """Clear pane content."""
        self.run_info = None
        self.original_pixmap = None
        self.title_label.setText(f"Pane {self.pane_id}")
        self.label.setPixmap(QPixmap())
        self.label.setText("(Drag run here)")
        self.label.setStyleSheet("background-color: #1e1e1e; color: #888888; font-size: 11px;")

    def resizeEvent(self, event):
        """Handle window resize events to rescale displayed pixmap."""
        super().resizeEvent(event)
        self._update_pixmap_display()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept drag events with run reference MIME type."""
        if event.mimeData().hasFormat("application/x-run-ref"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle drop events to load a run into this pane."""
        mime_data = event.mimeData()
        if mime_data.hasFormat("application/x-run-ref"):
            import json
            try:
                raw_payload = mime_data.data("application/x-run-ref")
                payload = bytes(raw_payload)
                if not payload:
                    event.ignore()
                    return
                data = json.loads(payload.decode("utf-8"))
                archive_id = data.get("archive_id")
                run_name = data.get("run_name")
                if archive_id and run_name:
                    self.run_dropped.emit(self.pane_id, archive_id, run_name)
                    event.acceptProposedAction()
                else:
                    event.ignore()
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
                event.ignore()
        else:
            event.ignore()


class SplitPaneWidget(QWidget):
    """Resizable split pane container supporting 1, 2, or 4 panes."""

    def __init__(self):
        super().__init__()
        self.panes: Dict[int, ImagePane] = {}
        self.current_layout = "single"

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)
        self.set_layout("single")

    def set_layout(self, layout_type: str):
        """Switch between single/2-pane/4-pane layouts."""
        if layout_type == self.current_layout and self.panes:
            return

        # Clear existing layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.panes.clear()
        self.current_layout = layout_type

        if layout_type == "single":
            pane = ImagePane(0)
            self.panes[0] = pane
            self.main_layout.addWidget(pane)

        elif layout_type == "2-pane":
            container = QWidget()
            v_layout = QVBoxLayout()
            v_layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(v_layout)

            for i in range(2):
                pane = ImagePane(i)
                self.panes[i] = pane
                v_layout.addWidget(pane)

            self.main_layout.addWidget(container)

        elif layout_type == "4-pane":
            container = QWidget()
            grid_layout = QVBoxLayout()
            grid_layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(grid_layout)

            for row in range(2):
                row_layout = QHBoxLayout()
                row_layout.setContentsMargins(0, 0, 0, 0)
                for col in range(2):
                    pane_id = row * 2 + col
                    pane = ImagePane(pane_id)
                    self.panes[pane_id] = pane
                    row_layout.addWidget(pane)
                grid_layout.addLayout(row_layout)

            self.main_layout.addWidget(container)

    def get_pane(self, index: int) -> Optional[ImagePane]:
        """Get pane by index."""
        return self.panes.get(index)

    def get_pane_count(self) -> int:
        """Get number of panes in current layout."""
        return len(self.panes)

    def clear_all(self):
        """Clear all panes."""
        for pane in self.panes.values():
            pane.clear()
