"""
Handler for .liufs file operations.
Provides lightweight file reading with only top-level manifest.json extraction.
"""

import json
import posixpath
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List


class LiufsFileHandler:
    """Handles reading and parsing .liufs files."""
    
    def __init__(self, file_path: str):
        """
        Initialize handler for a .liufs file.
        
        Args:
            file_path: Path to the .liufs file
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is not a valid .liufs file
        """
        self.file_path = Path(file_path)
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not self.file_path.suffix.lower() == '.liufs':
            raise ValueError(f"File must have .liufs extension, got: {self.file_path.suffix}")
        
        self._manifest = None
        self._validate_and_load_manifest()
    
    def _validate_and_load_manifest(self):
        """
        Validate that manifest.json exists at root and load it.
        
        Raises:
            ValueError: If manifest.json is not found or invalid
        """
        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                if 'manifest.json' not in zf.namelist():
                    raise ValueError("manifest.json not found at root of .liufs file")
                
                with zf.open('manifest.json') as f:
                    self._manifest = json.load(f)
        except zipfile.BadZipFile:
            raise ValueError(f"File is not a valid ZIP archive: {self.file_path}")
        except json.JSONDecodeError:
            raise ValueError("manifest.json is not valid JSON")
    
    @property
    def manifest(self) -> Dict[str, Any]:
        """Get the parsed manifest dictionary."""
        return self._manifest
    
    def get_runs(self) -> list[str]:
        """Get list of run names from manifest."""
        if not self._manifest or 'runs' not in self._manifest:
            return []
        
        runs = self._manifest['runs'].get('children', {})
        return list(runs.keys())
    
    def get_simulation_name(self) -> str:
        """Get the simulation name from manifest."""
        return self._manifest.get('simulation_name', 'Unknown')
    
    def get_file(self, path_in_archive: str) -> Optional[bytes]:
        """
        Extract and return a file from the archive.
        
        Args:
            path_in_archive: Path to file within the archive
            
        Returns:
            File contents as bytes, or None if file not found
        """
        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                if path_in_archive in zf.namelist():
                    return zf.read(path_in_archive)
        except zipfile.BadZipFile:
            return None
        
        return None
    
    def list_files(self, folder_path: str = '') -> list[str]:
        """
        List files in a folder within the archive.
        
        Args:
            folder_path: Path to folder within archive (without trailing slash)
            
        Returns:
            List of file names in the folder
        """
        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                prefix = (folder_path + '/') if folder_path else ''
                files = [
                    name for name in zf.namelist()
                    if name.startswith(prefix) and name != prefix
                ]
                return files
        except zipfile.BadZipFile:
            return []

    def get_group_node(self, group_path: List[str]) -> Optional[Dict[str, Any]]:
        """Return manifest node for [run, image_group] path."""
        if len(group_path) != 2:
            return None

        runs = self._manifest.get("runs", {}).get("children", {})
        run_node = runs.get(group_path[0], {}) if isinstance(runs, dict) else {}
        run_children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
        group_node = run_children.get(group_path[1]) if isinstance(run_children, dict) else None
        return group_node if isinstance(group_node, dict) else None

    def get_group_categories(self, group_path: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get category nodes under a selected [run, image_group]."""
        group_node = self.get_group_node(group_path)
        if not group_node:
            return {}

        children = group_node.get("children", {})
        if not isinstance(children, dict):
            return {}

        return {name: node for name, node in children.items() if isinstance(node, dict)}

    def get_category_datasets(self, group_path: List[str], category_name: str) -> Dict[str, Dict[str, Any]]:
        """Get dataset leaves under a category (for example cp/cptot under cutplanes)."""
        categories = self.get_group_categories(group_path)
        category_node = categories.get(category_name, {})
        children = category_node.get("children", {}) if isinstance(category_node, dict) else {}
        if not isinstance(children, dict):
            return {}
        return {name: node for name, node in children.items() if isinstance(node, dict)}

    def resolve_archive_path(self, group_path: List[str], relative_or_full_path: str) -> str:
        """
        Resolve file path in archive.

        Manifest stores files relative to runs/<run>/<group>. If already absolute inside archive,
        keep it as-is.
        """
        normalized = relative_or_full_path.replace("\\", "/")
        if normalized.startswith("runs/"):
            return normalized

        if len(group_path) == 2:
            return posixpath.normpath(f"runs/{group_path[0]}/{group_path[1]}/{normalized}")

        return normalized

    def get_node_by_path(self, path_parts: List[str]) -> Optional[Dict[str, Any]]:
        """Resolve a manifest node using [run, image_group, category] style path parts."""
        if not path_parts:
            return None

        node = self._manifest.get("runs", {}).get("children", {})
        for part in path_parts:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
            if isinstance(node, dict) and "children" in node:
                node = node["children"]

        if isinstance(node, dict):
            return {"children": node}
        return None

    def get_cutplane_quantities(self, path_parts: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get cutplane quantity leaves (cp/cptot/hel/lic variants) for a selected cutplanes node."""
        node = self.get_node_by_path(path_parts)
        if not node:
            return {}

        children = node.get("children", {})
        quantities: Dict[str, Dict[str, Any]] = {}
        for name, child in children.items():
            if not isinstance(child, dict):
                continue
            if child.get("type") == "cfd_images" and isinstance(child.get("videos"), dict):
                quantities[name] = child
        return quantities

    def get_plane_video_path(self, quantity_node: Dict[str, Any], plane_name: str) -> Optional[str]:
        """Get relative archive path to a plane video for a given quantity node."""
        videos = quantity_node.get("videos", {}) if isinstance(quantity_node, dict) else {}
        value = videos.get(plane_name)
        return value if isinstance(value, str) else None
