"""
Video player component for displaying frames from video files.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt


class VideoPlayer:
    """Handles video frame reading and playback."""
    
    def __init__(self, video_path: str):
        """
        Initialize video player.
        
        Args:
            video_path: Path to video file
            
        Raises:
            ValueError: If video file cannot be opened
        """
        self.video_path = Path(video_path)
        self.cap = cv2.VideoCapture(str(video_path))
        
        if not self.cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")
        
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.current_frame_index = 0
    
    def get_frame(self, frame_index: int) -> Optional[QPixmap]:
        """
        Get a specific frame as QPixmap.
        
        Args:
            frame_index: Frame number to retrieve (0-based)
            
        Returns:
            QPixmap of the frame, or None if frame cannot be read
        """
        if frame_index < 0 or frame_index >= self.frame_count:
            return None
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        
        if not ret:
            return None
        
        self.current_frame_index = frame_index
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to QImage
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        return QPixmap.fromImage(qt_image)
    
    def get_total_frames(self) -> int:
        """Get total number of frames in video."""
        return self.frame_count
    
    def close(self):
        """Release video capture resource."""
        if self.cap:
            self.cap.release()
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()
