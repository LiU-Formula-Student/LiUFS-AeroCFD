"""
Handles export operations: frame export, video export, clipboard.
"""

import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication


class ExportService:
    """Handles exporting media files."""
    
    @staticmethod
    def export_frame(pixmap: QPixmap, output_path: str) -> bool:
        """
        Export a pixmap as an image file.
        
        Args:
            pixmap: Image to export
            output_path: Path to save image
            
        Returns:
            True if successful, False otherwise
        """
        if not pixmap:
            return False
        
        return pixmap.save(output_path)
    
    @staticmethod
    def export_video_clip(source_path: str, output_path: str) -> bool:
        """
        Export a video file by copying it.
        
        Args:
            source_path: Path to source video
            output_path: Path to save video
            
        Returns:
            True if successful, False otherwise
        """
        try:
            source = Path(source_path)
            if not source.exists():
                return False
            
            shutil.copy2(str(source), str(output_path))
            return True
        except Exception:
            return False
    
    @staticmethod
    def copy_to_clipboard(pixmap: QPixmap) -> bool:
        """
        Copy a pixmap to the clipboard.
        
        Args:
            pixmap: Image to copy
            
        Returns:
            True if successful, False otherwise
        """
        if not pixmap:
            return False
        
        try:
            QApplication.clipboard().setPixmap(pixmap)
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_export_path(path: str) -> bool:
        """
        Validate that an export path is writable.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path can be written to
        """
        try:
            parent = Path(path).parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False
