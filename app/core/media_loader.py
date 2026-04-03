"""
Handles media loading, caching, and frame access.
Manages both video and static image resources.
"""

import hashlib
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from PySide6.QtGui import QPixmap

from app.video_player import VideoPlayer
from app.core.archive_manager import ArchiveManager


class MediaController:
    """Manages media loading and caching."""
    
    def __init__(self, archive_manager: ArchiveManager):
        """
        Initialize media controller.
        
        Args:
            archive_manager: ArchiveManager instance for accessing archive data
        """
        self.archive_manager = archive_manager
        self.video_cache: Dict[Tuple[str, ...], VideoPlayer] = {}
        self.temp_dir: Optional[str] = None
    
    def _ensure_temp_dir(self) -> str:
        """Ensure temporary directory exists."""
        if not self.temp_dir:
            self.temp_dir = tempfile.mkdtemp()
        return self.temp_dir
    
    def _make_cache_key(self, archive_id: str, archive_path: str) -> Tuple[str, ...]:
        """Create a cache key for a video."""
        return (str(archive_id), str(archive_path))
    
    def _extract_to_temp(self, archive_id: str, archive_path: str) -> Optional[Path]:
        """Extract a file from archive to temp storage."""
        video_data = self.archive_manager.get_file(archive_id, archive_path)
        if not video_data:
            return None
        
        temp_dir = self._ensure_temp_dir()
        safe_name = hashlib.sha1(
            f"{archive_id}::{archive_path}".encode("utf-8")
        ).hexdigest()
        
        # Use original extension if available
        ext = Path(archive_path).suffix or ".mp4"
        temp_video_path = Path(temp_dir) / f"video_{safe_name}{ext}"
        temp_video_path.parent.mkdir(parents=True, exist_ok=True)
        temp_video_path.write_bytes(video_data)
        
        return temp_video_path
    
    def get_video_player(
        self, archive_id: str, archive_path: str, use_cache: bool = True
    ) -> Optional[VideoPlayer]:
        """
        Get a VideoPlayer for an archive's video file.
        Caches players to avoid reloading.
        
        Args:
            archive_id: Archive ID
            archive_path: Path within archive
            use_cache: Whether to use cached player if available
            
        Returns:
            VideoPlayer instance or None if file not found
        """
        cache_key = self._make_cache_key(archive_id, archive_path)
        
        if use_cache and cache_key in self.video_cache:
            return self.video_cache[cache_key]
        
        temp_path = self._extract_to_temp(archive_id, archive_path)
        if not temp_path:
            return None
        
        try:
            player = VideoPlayer(str(temp_path))
            self.video_cache[cache_key] = player
            return player
        except Exception:
            return None
    
    def get_frame_from_video(
        self, archive_id: str, archive_path: str, frame_index: int
    ) -> Optional[QPixmap]:
        """
        Get a specific frame from a video.
        
        Args:
            archive_id: Archive ID
            archive_path: Path within archive
            frame_index: Frame number
            
        Returns:
            QPixmap of frame or None
        """
        player = self.get_video_player(archive_id, archive_path)
        if not player:
            return None
        
        # Clamp to valid range
        max_frame = max(player.get_total_frames() - 1, 0)
        safe_frame = min(frame_index, max_frame)
        
        return player.get_frame(safe_frame)
    
    def get_total_frames(self, archive_id: str, archive_path: str) -> int:
        """Get total frame count for a video."""
        player = self.get_video_player(archive_id, archive_path)
        if not player:
            return 0
        return player.get_total_frames()
    
    def load_static_image(self, archive_id: str, archive_path: str) -> Optional[QPixmap]:
        """
        Load a static image from an archive.
        
        Args:
            archive_id: Archive ID
            archive_path: Path within archive
            
        Returns:
            QPixmap or None if not found or can't load
        """
        image_data = self.archive_manager.get_file(archive_id, archive_path)
        if not image_data:
            return None
        
        pixmap = QPixmap()
        if pixmap.loadFromData(image_data):
            return pixmap
        return None
    
    def get_video_fps(self, archive_id: str, archive_path: str) -> float:
        """Get FPS for a video."""
        player = self.get_video_player(archive_id, archive_path)
        if not player:
            return 0.0
        return player.fps or 0.0
    
    def clear_cache(self):
        """Clear all cached videos."""
        for player in self.video_cache.values():
            try:
                player.close()
            except Exception:
                pass
        self.video_cache.clear()
    
    def cleanup(self):
        """Clean up temporary files."""
        self.clear_cache()
        if self.temp_dir:
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
            self.temp_dir = None
