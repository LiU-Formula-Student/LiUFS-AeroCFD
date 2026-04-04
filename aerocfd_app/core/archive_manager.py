"""
Manages open .liufs archives and provides archive-related queries.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any

from aerocfd_app.liufs_handler import LiufsFileHandler, LiufsValidationError


class ArchiveManager:
    """Manages multiple open .liufs archives."""
    
    def __init__(self):
        """Initialize the archive manager."""
        self.open_archives: Dict[str, LiufsFileHandler] = {}
        self.open_archive_paths: Dict[str, str] = {}
    
    def load_archive(self, file_path: str) -> str:
        """
        Load a .liufs file.
        
        Args:
            file_path: Path to the .liufs file
            
        Returns:
            Archive ID (file path hash)
            
        Raises:
            LiufsValidationError: If file is invalid
            FileNotFoundError: If file doesn't exist
        """
        handler = LiufsFileHandler(file_path)
        archive_id = str(Path(file_path).resolve())
        self.open_archives[archive_id] = handler
        self.open_archive_paths[archive_id] = file_path
        return archive_id
    
    def get_archive(self, archive_id: str) -> Optional[LiufsFileHandler]:
        """Get an archive by ID."""
        return self.open_archives.get(archive_id)
    
    def get_archive_path(self, archive_id: str) -> Optional[str]:
        """Get the file path for an archive."""
        return self.open_archive_paths.get(archive_id)
    
    def get_archive_name(self, archive_id: str) -> str:
        """Get the display name for an archive (filename)."""
        path = self.open_archive_paths.get(archive_id)
        if path:
            return Path(path).name
        return "Unknown"
    
    def get_archive_label(self, archive_id: str) -> str:
        """Get the display label for an archive (stem/basename without extension)."""
        path = self.open_archive_paths.get(archive_id)
        if path:
            return Path(path).stem
        return "Unknown"
    
    def list_archives(self) -> List[Dict[str, Any]]:
        """Get list of all open archives with metadata."""
        archives = []
        for archive_id, handler in self.open_archives.items():
            label = f"{self.get_archive_name(archive_id)} | {handler.get_simulation_name()}"
            archives.append({
                "archive_id": archive_id,
                "label": label,
                "path": self.get_archive_path(archive_id),
                "simulation_name": handler.get_simulation_name(),
                "manifest": handler.manifest,
            })
        return archives
    
    def get_runs(self, archive_id: str) -> List[str]:
        """Get list of runs from an archive."""
        handler = self.get_archive(archive_id)
        if not handler:
            return []
        return handler.get_runs()
    
    def get_group_categories(self, archive_id: str, group_path: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get categories under a run/version group."""
        handler = self.get_archive(archive_id)
        if not handler:
            return {}
        return handler.get_group_categories(group_path)
    
    def get_category_datasets(
        self, archive_id: str, group_path: List[str], category_name: str
    ) -> Dict[str, Dict[str, Any]]:
        """Get datasets under a category."""
        handler = self.get_archive(archive_id)
        if not handler:
            return {}
        return handler.get_category_datasets(group_path, category_name)
    
    def resolve_archive_path(self, archive_id: str, group_path: List[str], rel_path: str) -> str:
        """Resolve a relative path within an archive."""
        handler = self.get_archive(archive_id)
        if not handler:
            return rel_path
        return handler.resolve_archive_path(group_path, rel_path)
    
    def get_file(self, archive_id: str, archive_path: str) -> Optional[bytes]:
        """Get file contents from an archive."""
        handler = self.get_archive(archive_id)
        if not handler:
            return None
        return handler.get_file(archive_path)
    
    def collect_run_refs(self) -> List[Dict[str, Any]]:
        """Collect unique run references from all open archives."""
        run_refs: List[Dict[str, Any]] = []
        seen: set = set()
        for archive_id, handler in self.open_archives.items():
            runs = handler.manifest.get("runs", {}).get("children", {})
            if not isinstance(runs, dict):
                continue
            for run_name, run_node in runs.items():
                if not isinstance(run_node, dict):
                    continue
                if not isinstance(run_node.get("children"), dict):
                    continue
                key = (archive_id, run_name)
                if key in seen:
                    continue
                seen.add(key)
                label = f"{self.get_archive_name(archive_id)} | {run_name}"
                run_refs.append({
                    "archive_id": archive_id,
                    "run_name": run_name,
                    "label": label,
                })
        return run_refs
    
    def close_all(self):
        """Close all open archives."""
        self.open_archives.clear()
        self.open_archive_paths.clear()
