# LiU FS Simulation Viewer - Application Guide

## Project Structure

The application is organized into modular components:

### Core Modules

#### `liufs_handler.py`
Handles all `.liufs` file operations with a lightweight approach:
- **`LiufsFileHandler` class**: Main interface for working with `.liufs` files
  - Validates files by checking for `manifest.json` at root (no recursive checks)
  - Extracts and parses the manifest structure
  - Provides methods to list files and extract data from the archive
  - Raises `ValueError` if file is malformed or manifest is missing

**Key Methods:**
- `manifest` - Get the parsed manifest dictionary
- `get_runs()` - List all run names
- `get_simulation_name()` - Get simulation name
- `get_file(path)` - Extract specific file from archive
- `list_files(folder_path)` - List files in archive folder

#### `video_player.py`
Handles video frame extraction and display:
- **`VideoPlayer` class**: OpenCV-based video frame reader
  - Uses OpenCV's VideoCapture for efficient frame seeking
  - Converts frames to Qt-compatible QPixmap format
  - Tracks playback position and metadata

**Key Methods:**
- `get_frame(frame_index)` - Get specific frame as QPixmap
- `get_total_frames()` - Get frame count
- `close()` - Release video resource

#### `file_tree.py`
Qt-based file tree widget for displaying hierarchy:
- **`FileTreeWidget` class**: Extends QTreeWidget
  - Recursively populates tree from manifest structure
  - Displays image/file counts as leaf metadata
  - Provides path retrieval for selected items
  - Automatically expands all items

**Key Methods:**
- `populate_from_manifest(manifest)` - Build tree from manifest
- `get_selected_path()` - Get path to selected item

#### `main.py`
Main application window and entry point:
- **`ViewerWindow` class**: Extends QMainWindow
  - Manages application layout and user interactions
  - Handles file opening and manifest loading
  - Controls video playback and frame display
  - Implements keyboard navigation

## Application Layout

```
┌─────────────────────────────────────────────────────┐
│  LiU FS Simulation Viewer                      File ✕ │
├──────────────────┬────────────────────────────────────┤
│                  │                                    │
│  File Tree       │     Video Frame Display           │
│  (Manifest       │     (Shows current frame)         │
│   Structure)     │                                    │
│                  │                                    │
│                  ├────────────────────────────────────┤
│                  │  [=======●─────────────] Frame Bar │
│                  │  Frame: 42/289 | FPS: 12.00       │
└──────────────────┴────────────────────────────────────┘
```

## Features

### Navigation
- **Arrow Keys**: 
  - `→` (Right): Next frame
  - `←` (Left): Previous frame
- **Slider**: Drag to seek, or click to jump to specific frame
- **Mouse**: Tree selection for different video/image groups

### File Operations
- **File → Open**: Select `.liufs` file to load
- **File → Exit**: Close application
- **Ctrl+O**: Open file (shortcut)
- **Ctrl+Q**: Quit (shortcut)

### Display Modes
- **Frame-by-frame viewing**: Manual stepping through frames
- **Slider quick-jump**: Instant navigation to any frame
- **Info display**: Shows current frame, total frames, and FPS

## How to Use

### Installation via pip

Install app dependencies:

```bash
pip install "aerocfd[app]"
```

Install everything (app + CLI):

```bash
pip install "aerocfd[full]"
```

### Running the Application

**Option 1: Using the launcher script (Recommended)**

```bash
cd /home/gustav/Documents/LiUFS/AeroCFD
./run_viewer.sh
```

**Option 2: Using python -m**

```bash
cd /home/gustav/Documents/LiUFS/AeroCFD
python -m aerocfd_app
```

**Option 3: Direct execution**

```bash
cd /home/gustav/Documents/LiUFS/AeroCFD
python aerocfd_app/main.py
```

Or if virtual environment is already activated:

```bash
python -m aerocfd_app
```

### Opening a File

1. Click **File → Open** or press **Ctrl+O**
2. Select a `.liufs` file
3. The file structure appears in the left panel
4. Expand entries by clicking the tree items
5. Click on a video entry to load it in the viewer

### Viewing Videos

1. Once a video loads, the first frame displays
2. Use arrow keys or slider to navigate
3. Frame information shows at the bottom
4. Click/drag the slider for quick navigation

## Architecture Decisions

### Lightweight File Handling
- Only `manifest.json` is checked at root level
- No recursive validation or file listing on open
- Files extracted on-demand to temporary directory
- Significantly reduces memory usage and startup time

### Modular Design
- Separate concerns: file handling, video playback, UI, tree display
- Easy to extend with new features
- Components can be tested independently
- Suitable for future CLI tool (shares same logic)

### Performance Optimizations
- Frame-by-frame extraction only when needed
- Temporary file caching for current video
- Lazy loading of video data
- Efficient slider seeking using OpenCV

## Dependencies

- **PySide6**: Qt-based GUI framework
- **OpenCV (cv2)**: Video frame extraction
- **NumPy**: Array operations for image processing

## Requirements File

```
PySide6>=6.7.0
opencv-python>=4.8.0
numpy<2
```

## Future Enhancements

The foundation is set for:
- Image comparison/side-by-side viewing
- Playback controls (play, pause, speed)
- Grid view of multiple sequences
- Timeline navigation
- Export functionality
- CLI tool using same backend

## Testing

Run component tests:

```bash
python test_components.py
```

This verifies:
- Module imports
- Core class functionality
- Data structure validation
