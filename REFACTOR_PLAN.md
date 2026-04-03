# LiU FS Viewer - Application Refactor Plan

## Overview
This document outlines the refactoring of the application to split responsibilities from the monolithic `ViewerWindow` class into smaller, focused modules organized into a clear folder structure.

## New Folder Structure

```
app/
├── __init__.py
├── __main__.py
├── main.py                          # Entry point (thin wrapper)
├── liufs_handler.py                 # Core archive handler (unchanged location)
├── video_player.py                  # Video playback (unchanged location)
├── version.py                       # Version info (unchanged location)
│
├── ui/                              # User interface components
│   ├── __init__.py
│   ├── viewer_window.py             # Main window orchestrator (future)
│   │
│   └── widgets/                     # Reusable Qt widgets
│       ├── __init__.py
│       ├── file_tree.py             # File tree navigation widget
│       └── panes.py                 # Pane widgets (ImagePane, SplitPaneWidget, etc.)
│
├── core/                            # Business logic & state management
│   ├── __init__.py
│   ├── view_state.py                # Selection state tracker
│   ├── archive_manager.py           # Archive operations
│   ├── media_loader.py              # Video/image loading & caching
│   ├── pane_manager.py              # Pane state & layout
│   └── export_service.py            # Export operations
│
└── resources/                       # Application resources
    └── __init__.py
```

## Extracted Core Modules

### 1. **ViewState** (`app/core/view_state.py`)
- **Purpose**: Single source of truth for all UI selection state
- **Responsibilities**:
  - Track current archive, run, version, category, dataset, item
  - Maintain available options (versions, categories, datasets)
  - Track media type (video/image) and playback state
  - Frame navigation (current frame, max frame)
- **Key Classes**: `ViewState`

### 2. **ArchiveManager** (`app/core/archive_manager.py`)
- **Purpose**: Manage all open .liufs files
- **Responsibilities**:
  - Load and track multiple open archives
  - Provide archive-related queries (runs, categories, datasets)
  - Resolve paths within archives
  - Extract file contents
- **Key Classes**: `ArchiveManager`

### 3. **MediaController** (`app/core/media_loader.py`)
- **Purpose**: Handle all media loading, caching, and frame access
- **Responsibilities**:
  - Load and cache video players
  - Extract files from archives to temporary storage
  - Get specific frames from videos
  - Load static images
  - Manage temp directory cleanup
- **Key Classes**: `MediaController`

### 4. **PaneManager** (`app/core/pane_manager.py`)
- **Purpose**: Track and manage pane state
- **Responsibilities**:
  - Manage pane layout (single/2-pane/4-pane)
  - Track which runs are loaded in which panes
  - Per-pane selection context (independent of primary selector)
  - Update all pane contexts when selectors change
- **Key Classes**: `PaneManager`, `PaneReference`

### 5. **ExportService** (`app/core/export_service.py`)
- **Purpose**: Handle all export operations
- **Responsibilities**:
  - Export frames as image files
  - Export video clips
  - Copy images to clipboard
  - Validate export paths
- **Key Classes**: `ExportService`

## UI Components (Moved)

### File Tree Widget (`app/ui/widgets/file_tree.py`)
- **Moved from**: `app/file_tree.py`
- **Purpose**: Display simulation runs organized by archive
- **Responsibilities**:
  - Display tree hierarchy
  - Handle drag-and-drop for runs
  - Provide selection queries
- **Key Classes**: `FileTreeWidget`

### Pane Widgets (`app/ui/widgets/panes.py`)
- **Moved from**: `app/view_components.py`
- **Purpose**: Display images/videos in resizable panes
- **Responsibilities**:
  - Render individual panes
  - Handle drag-and-drop into panes
  - Manage image scaling and display
  - Detached window support
- **Key Classes**: 
  - `ImagePane` - Single pane display
  - `SplitPaneWidget` - Container for 1/2/4 panes
  - `DetachedImageWindow` - Detached display window
  - `AppendRunWorker` - Background task for adding runs
  - `GUIReporter` - Reporter for background tasks

## Import Changes

### Before
```python
from .file_tree import FileTreeWidget
from .view_components import (
    GUIReporter, AppendRunWorker, 
    DetachedImageWindow, ImagePane, SplitPaneWidget
)
```

### After
```python
from .ui.widgets.file_tree import FileTreeWidget
from .ui.widgets.panes import (
    GUIReporter, AppendRunWorker, 
    DetachedImageWindow, ImagePane, SplitPaneWidget
)
from .core.view_state import ViewState
from .core.archive_manager import ArchiveManager
from .core.media_loader import MediaController
from .core.pane_manager import PaneManager
from .core.export_service import ExportService
```

## Test File Updates

Updated imports in test files:
- `tests/test_components.py` - Updated to use `app.*` namespace
- `tests/test_error_handling.py` - Updated to use `app.liufs_handler`
- `tests/test_pane_navigation.py` - Updated to import from `app.ui.widgets.panes`

## Migration Phases

### Phase 1: Create new module structure ✓
- Create `app/ui/`, `app/ui/widgets/`, `app/core/`, `app/resources/` directories
- Create `__init__.py` files for each package

### Phase 2: Extract core logic ✓
- Create `ViewState` for state tracking
- Create `ArchiveManager` for archive operations
- Create `MediaController` for media loading
- Create `PaneManager` for pane management
- Create `ExportService` for export operations

### Phase 3: Move UI components ✓
- Move `file_tree.py` to `app/ui/widgets/file_tree.py`
- Move `view_components.py` to `app/ui/widgets/panes.py`

### Phase 4: Update imports ✓
- Update `app/main.py` imports
- Update all test file imports
- Update `app/__main__.py` if needed

### Phase 5: Create orchestrator (Future)
- Extract `ViewerWindow` to `app/ui/viewer_window.py`
- Refactor `ViewerWindow` to use core modules
- Keep `app/main.py` as thin entry point
- Update event handlers to delegate to core services

## Benefits

1. **Separation of Concerns**
   - UI logic separated from business logic
   - State management isolated
   - Easy to test individual components

2. **Reusability**
   - Core modules can be used in different UI contexts
   - Export service can be used programmatically
   - Archive manager can be extended easily

3. **Maintainability**
   - Clear responsibility boundaries
   - Easier to add new features
   - Simpler to debug issues

4. **Scalability**
   - Easy to add new export formats (add ExportService methods)
   - Easy to add new pane layouts (update PaneManager)
   - Easy to add new media types (extend MediaController)

5. **Testing**
   - Core modules can be unit tested without Qt
   - Mocking is simplified with smaller classes
   - State transitions are more predictable

## Next Steps

1. **Extract ViewerWindow** - Move main window class to `app/ui/viewer_window.py`
   - Keep as orchestrator
   - Delegate to core services
   - Use dependency injection

2. **Add Core Services to ViewerWindow**
   - Initialize all core managers in constructor
   - Wire signals to core methods
   - Handle state synchronization

3. **Add Integration Tests**
   - Test workflow sequences
   - Test state consistency
   - Test multi-archive scenarios

4. **Add Documentation**
   - Docstrings for all classes
   - Architecture decision records
   - Integration patterns

## File Status

### Unchanged (but may need future updates)
- `app/liufs_handler.py`
- `app/video_player.py`
- `app/version.py`
- `simulation_compressor/` (external package)

### Deleted (consolidated)
- `app/file_tree.py` → `app/ui/widgets/file_tree.py`
- `app/view_components.py` → `app/ui/widgets/panes.py`

### Updated
- `app/main.py` - Updated imports
- All test files - Updated imports

### Created
- `app/ui/` directory
- `app/ui/widgets/` directory
- `app/core/` directory
- `app/resources/` directory
- `app/core/view_state.py`
- `app/core/archive_manager.py`
- `app/core/media_loader.py`
- `app/core/pane_manager.py`
- `app/core/export_service.py`
- `app/ui/widgets/file_tree.py`
- `app/ui/widgets/panes.py`

## Clean Up (Next Phase)

After phase 5 (ViewerWindow orchestrator extraction), you should:

1. Delete old unpatched files:
   - `app/file_tree.py` ← replaced by `app/ui/widgets/file_tree.py`
   - `app/view_components.py` ← replaced by `app/ui/widgets/panes.py`

2. Verify all imports point to new locations

3. Run full test suite to ensure everything works
