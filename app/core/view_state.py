"""
Tracks the current selection state: archive, run, version, category, dataset, item.
Provides a single source of truth for all UI selection state.
"""

from typing import Optional, Dict, Any, List


class ViewState:
    """Manages current viewer selection state."""
    
    def __init__(self):
        """Initialize empty view state."""
        self.current_archive_id: Optional[str] = None
        self.current_run_name: Optional[str] = None
        self.current_version_name: Optional[str] = None
        self.current_group_path: List[str] = []
        self.current_media_type: Optional[str] = None  # "video" or "image"
        self.current_video_path: Optional[str] = None
        
        # Cached available options
        self.current_versions: List[str] = []
        self.current_categories: Dict[str, Dict[str, Any]] = {}
        self.current_datasets: Dict[str, Dict[str, Any]] = {}
        
        # Primary source context (for saving current state)
        self.primary_source: Optional[Dict[str, Any]] = None
        
        # Frame index
        self.current_frame_index: int = 0
        self.max_frame_index: int = 0
        
        # Playback state
        self.is_playing: bool = False
        self.playback_speed: str = "1x"
        self.loop_mode: bool = False
    
    def reset(self):
        """Reset all state to initial values."""
        self.current_archive_id = None
        self.current_run_name = None
        self.current_version_name = None
        self.current_group_path = []
        self.current_media_type = None
        self.current_video_path = None
        self.current_versions = []
        self.current_categories = {}
        self.current_datasets = {}
        self.primary_source = None
        self.current_frame_index = 0
        self.max_frame_index = 0
        self.is_playing = False
        self.playback_speed = "1x"
        self.loop_mode = False
    
    def get_primary_context(self) -> Dict[str, Any]:
        """Get the current primary selection context."""
        return {
            "archive_id": self.current_archive_id,
            "run_name": self.current_run_name,
            "version": self.current_version_name,
            "group_path": list(self.current_group_path),
            "category": self.current_categories,
            "dataset": self.current_datasets,
            "media_type": self.current_media_type,
        }
    
    def set_archive(self, archive_id: Optional[str]):
        """Set the current archive."""
        self.current_archive_id = archive_id
    
    def set_run(self, run_name: Optional[str]):
        """Set the current run."""
        self.current_run_name = run_name
    
    def set_version(self, version_name: Optional[str]):
        """Set the current version."""
        self.current_version_name = version_name
    
    def set_group_path(self, group_path: List[str]):
        """Set the current group path (e.g., [run_name, version_name])."""
        self.current_group_path = list(group_path)
    
    def set_available_versions(self, versions: List[str]):
        """Set the list of available versions for current run."""
        self.current_versions = sorted(versions)
    
    def set_available_categories(self, categories: Dict[str, Dict[str, Any]]):
        """Set the available categories for current version."""
        self.current_categories = categories
    
    def set_available_datasets(self, datasets: Dict[str, Dict[str, Any]]):
        """Set the available datasets for current category."""
        self.current_datasets = datasets
    
    def set_media_type(self, media_type: Optional[str]):
        """Set the current media type (video or image)."""
        self.current_media_type = media_type
    
    def set_video_path(self, path: Optional[str]):
        """Set the current video path."""
        self.current_video_path = path
    
    def set_frame(self, frame_index: int, max_index: int):
        """Set current frame and max frame."""
        self.current_frame_index = frame_index
        self.max_frame_index = max_index
    
    def next_frame(self):
        """Advance to next frame if available."""
        if self.current_frame_index < self.max_frame_index:
            self.current_frame_index += 1
            return self.current_frame_index
        return None
    
    def prev_frame(self):
        """Go back one frame if available."""
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            return self.current_frame_index
        return None
    
    def goto_frame(self, index: int):
        """Jump to specific frame."""
        if 0 <= index <= self.max_frame_index:
            self.current_frame_index = index
            return True
        return False
