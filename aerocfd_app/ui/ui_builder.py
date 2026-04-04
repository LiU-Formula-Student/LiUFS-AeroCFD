"""
Builds and configures the user interface for the viewer application.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel, 
    QPushButton, QComboBox, QSlider, QPlainTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from aerocfd_app.ui.widgets.file_tree import FileTreeWidget
from aerocfd_app.ui.widgets.panes import SplitPaneWidget


class UIBuilder:
    """Builds the main window UI components."""
    
    def __init__(self, main_window):
        """
        Initialize the UI builder.
        
        Args:
            main_window: The main ViewerWindow instance
        """
        self.window = main_window
    
    def setup_ui(self):
        """Setup the central user interface."""
        # Central widget
        central_widget = QWidget()
        self.window.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create splitter for left (tree) and right (viewer) panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: File tree
        self.window.file_tree = FileTreeWidget()
        self.window.file_tree.itemSelectionChanged.connect(self.window.on_tree_selection_changed)
        splitter.addWidget(self.window.file_tree)
        
        # Right panel: Video viewer with split panes
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        # Split pane widget - replaces image_panel and compare_section
        self.window.split_pane_widget = SplitPaneWidget()
        self.window.setup_pane_signals()
        right_layout.addWidget(self.window.split_pane_widget, 1)

        # Playback controls
        self._build_playback_controls(right_layout)
        
        # Slider for frame navigation
        self.window.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.window.frame_slider.setMinimum(0)
        self.window.frame_slider.setMaximum(0)
        self.window.frame_slider.sliderMoved.connect(self.window.on_slider_moved)
        self.window.frame_slider.valueChanged.connect(self.window.on_slider_value_changed)
        right_layout.addWidget(self.window.frame_slider)

        # Controls for version/category/dataset/item selection
        self._build_selection_controls(right_layout)
        
        # Frame info label
        self.window.info_label = QPlainTextEdit()
        self.window.info_label.setReadOnly(True)
        self.window.info_label.setMaximumHeight(80)
        self.window.info_label.setStyleSheet("color: #888888; font-size: 11px; background-color: #1e1e1e;")
        right_layout.addWidget(self.window.info_label)
        
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        # Create menu bar
        self.create_menu_bar()
    
    def _build_playback_controls(self, parent_layout: QVBoxLayout):
        """Build playback control widgets."""
        playback_layout = QHBoxLayout()
        
        self.window.play_button = QPushButton("Play")
        self.window.pause_button = QPushButton("Pause")
        self.window.stop_button = QPushButton("Stop")
        self.window.play_button.clicked.connect(self.window.start_playback)
        self.window.pause_button.clicked.connect(self.window.pause_playback)
        self.window.stop_button.clicked.connect(self.window.stop_playback)

        playback_layout.addWidget(self.window.play_button)
        playback_layout.addWidget(self.window.pause_button)
        playback_layout.addWidget(self.window.stop_button)

        playback_layout.addSpacing(12)
        playback_layout.addWidget(QLabel("Speed"))
        self.window.speed_combo = QComboBox()
        self.window.speed_combo.addItems(["0.5x", "1x", "2x"])
        self.window.speed_combo.setCurrentText("1x")
        self.window.speed_combo.currentIndexChanged.connect(self.window.on_speed_changed)
        playback_layout.addWidget(self.window.speed_combo)

        playback_layout.addSpacing(12)
        playback_layout.addWidget(QLabel("Loop"))
        self.window.loop_combo = QComboBox()
        self.window.loop_combo.addItems(["Off", "Loop"])
        playback_layout.addWidget(self.window.loop_combo)
        playback_layout.addStretch(1)
        parent_layout.addLayout(playback_layout)
    
    def _build_selection_controls(self, parent_layout: QVBoxLayout):
        """Build version/category/dataset/item selection controls."""
        controls_layout = QHBoxLayout()

        version_label = QLabel("Version")
        self.window.version_combo = QComboBox()
        self.window.version_combo.setEnabled(False)
        self.window.version_combo.currentIndexChanged.connect(self.window.on_version_changed)

        category_label = QLabel("Category")
        self.window.category_combo = QComboBox()
        self.window.category_combo.setEnabled(False)
        self.window.category_combo.currentIndexChanged.connect(self.window.on_category_changed)

        dataset_label = QLabel("Dataset")
        self.window.dataset_combo = QComboBox()
        self.window.dataset_combo.setEnabled(False)
        self.window.dataset_combo.currentIndexChanged.connect(self.window.on_dataset_changed)

        item_label = QLabel("Plane")
        self.window.item_combo = QComboBox()
        self.window.item_combo.setEnabled(False)
        self.window.item_combo.currentIndexChanged.connect(self.window.on_item_changed)

        controls_layout.addWidget(version_label)
        controls_layout.addWidget(self.window.version_combo)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(category_label)
        controls_layout.addWidget(self.window.category_combo)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(dataset_label)
        controls_layout.addWidget(self.window.dataset_combo)
        controls_layout.addSpacing(16)
        controls_layout.addWidget(item_label)
        controls_layout.addWidget(self.window.item_combo)
        controls_layout.addStretch(1)
        parent_layout.addLayout(controls_layout)
    
    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.window.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = file_menu.addAction("&Open .liufs File")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.window.open_file)

        self.window.add_run_action = file_menu.addAction("&Add New Run")
        self.window.add_run_action.triggered.connect(self.window.add_new_run)
        self.window.add_run_action.setEnabled(False)

        file_menu.addSeparator()

        export_frame_action = file_menu.addAction("Export Current &Frame")
        export_frame_action.triggered.connect(self.window.export_current_frame)

        export_clip_action = file_menu.addAction("Export Current Video &Clip")
        export_clip_action.triggered.connect(self.window.export_current_video_clip)

        copy_frame_action = file_menu.addAction("&Copy Current Frame")
        copy_frame_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_frame_action.triggered.connect(self.window.copy_current_frame)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.window.close)

        # View menu
        view_menu = menubar.addMenu("&View")
        
        single_view_action = view_menu.addAction("&Single View")
        single_view_action.triggered.connect(lambda: self.window.set_view_mode("single"))
        
        view_menu.addSeparator()
        
        split_2_action = view_menu.addAction("&Split Screen: 2 Panes")
        split_2_action.triggered.connect(lambda: self.window.set_view_mode("2-pane"))
        
        split_4_action = view_menu.addAction("S&plit Screen: 4 Panes")
        split_4_action.triggered.connect(lambda: self.window.set_view_mode("4-pane"))
        
        view_menu.addSeparator()
        
        swap_action = view_menu.addAction("&Swap View (Cycle)")
        swap_action.triggered.connect(lambda: self.window.set_view_mode("swap"))
        
        view_menu.addSeparator()
        
        clear_view_action = view_menu.addAction("&Clear Current View")
        clear_view_action.triggered.connect(self.window.clear_current_view)

        view_menu.addSeparator()

        disable_detached_action = view_menu.addAction("Disable &Detached Mode")
        disable_detached_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
        disable_detached_action.triggered.connect(self.window.disable_detached_mode)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        help_action = help_menu.addAction("&Shortcuts & Usage")
        help_action.triggered.connect(self.window.show_help_dialog)
        
        help_menu.addSeparator()
        
        report_issue_action = help_menu.addAction("&Report Issue / Copy Diagnostics")
        report_issue_action.triggered.connect(self.window.show_report_issue_dialog)
        
        help_menu.addSeparator()
        
        info_action = help_menu.addAction("&About")
        info_action.triggered.connect(self.window.show_app_info)
