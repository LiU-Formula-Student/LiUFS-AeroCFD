"""Help and shortcuts dialog for the viewer application."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class HelpDialog(QDialog):
    """In-app help dialog showing shortcuts, usage, and getting help."""

    def __init__(self, parent=None):
        """Initialize help dialog."""
        super().__init__(parent)
        self.setWindowTitle("Help & Shortcuts")
        self.setGeometry(100, 100, 600, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Create tabs for different help sections
        tabs = QTabWidget()

        # Shortcuts tab
        shortcuts_tab = self._create_shortcuts_tab()
        tabs.addTab(shortcuts_tab, "Shortcuts")

        # Usage tab
        usage_tab = self._create_usage_tab()
        tabs.addTab(usage_tab, "Getting Started")

        # Support tab
        support_tab = self._create_support_tab()
        tabs.addTab(support_tab, "Support & Issues")

        layout.addWidget(tabs)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _create_shortcuts_tab(self) -> QWidget:
        """Create shortcuts reference tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        shortcuts_text = """
<b>Navigation</b>
<table cellpadding="8">
<tr><td><b>→ Right Arrow</b></td><td>Next frame</td></tr>
<tr><td><b>← Left Arrow</b></td><td>Previous frame</td></tr>
<tr><td><b>Space</b></td><td>Play/Pause playback</td></tr>
<tr><td><b>Ctrl+O</b></td><td>Open .liufs file</td></tr>
</table>

<b>Pane Layout</b>
<table cellpadding="8">
<tr><td><b>Ctrl+1</b></td><td>Single pane view</td></tr>
<tr><td><b>Ctrl+2</b></td><td>2-pane split view</td></tr>
<tr><td><b>Ctrl+4</b></td><td>4-pane split view</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Swap pane mode (drag-and-drop)</td></tr>
</table>

<b>Export & Display</b>
<table cellpadding="8">
<tr><td><b>Ctrl+E</b></td><td>Export current frame</td></tr>
<tr><td><b>Ctrl+L</b></td><td>Launch fullscreen / detached window</td></tr>
</table>
        """

        label = QLabel(shortcuts_text)
        label.setFont(QFont("Courier", 10))
        label.setTextFormat(label.textFormat() | 0x04)  # Support HTML
        label.setWordWrap(True)

        scroll = QScrollArea()
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)

        layout.addWidget(scroll)
        return widget

    def _create_usage_tab(self) -> QWidget:
        """Create quick-start usage tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        usage_text = """
<h3>Quick Start</h3>

<b>1. Load a Simulation</b>
<ul>
<li>Click <b>File → Open</b> or press <b>Ctrl+O</b></li>
<li>Select a <code>.liufs</code> file from your computer</li>
</ul>

<b>2. Explore Runs</b>
<ul>
<li>Left panel shows the folder tree of versions/runs</li>
<li>Click a run to load it</li>
</ul>

<b>3. Select Categories</b>
<ul>
<li>Choose category (CpPlot, Cutplanes, Iso, Surf)</li>
<li>Select dataset and image group</li>
</ul>

<b>4. Navigate Frames</b>
<ul>
<li>Use <b>← →</b> arrows to step through frames</li>
<li>Press <b>Space</b> to play/pause animations</li>
<li>Adjust playback speed with FPS slider</li>
</ul>

<b>5. View Layout</b>
<ul>
<li>Switch between single/2-pane/4-pane views</li>
<li>In Swap mode, drag runs from the tree to panes</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Right-click panes for options (fullscreen, detach window)</li>
<li>Keyboard shortcuts work in all view modes</li>
<li>Playback speed is frame-rate dependent</li>
</ul>
        """

        label = QLabel(usage_text)
        label.setTextFormat(label.textFormat() | 0x04)  # Support HTML
        label.setWordWrap(True)

        scroll = QScrollArea()
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)

        layout.addWidget(scroll)
        return widget

    def _create_support_tab(self) -> QWidget:
        """Create support and bug reporting tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        support_text = """
<h3>Getting Help</h3>

<b>Report an Issue</b>
<ul>
<li>Use <b>Help → Report Issue</b> to copy diagnostics</li>
<li>Paste diagnostics when creating a bug report on GitHub</li>
<li>Include:
  <ul>
    <li>Steps to reproduce the issue</li>
    <li>Expected vs. actual behavior</li>
    <li>Any error messages from the console</li>
  </ul>
</li>
</ul>

<b>Documentation</b>
<ul>
<li>https://github.com/LiU-Formula-Student/LiUFS-AeroCFD</li>
<li>PyPI: https://pypi.org/project/aerocfd</li>
<li>README has full installation & usage guide</li>
</ul>

<b>Contact</b>
<ul>
<li>GitHub Issues: Report bugs and request features</li>
<li>LiU Formula Student: Primary development team</li>
</ul>

<h3>Keyboard Shortcuts Cheat Sheet</h3>
<code>→ ← Next/Prev | Space Play/Pause | Ctrl+O Open | Ctrl+1/2/4 Panes | Ctrl+E Export</code>
        """

        label = QLabel(support_text)
        label.setTextFormat(label.textFormat() | 0x04)  # Support HTML
        label.setWordWrap(True)

        scroll = QScrollArea()
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)

        layout.addWidget(scroll)
        return widget
