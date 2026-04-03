"""File tree widget for displaying high-level simulation navigation."""

from typing import Dict, Any, List
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView
from PySide6.QtCore import Qt


class FileTreeWidget(QTreeWidget):
    """Tree widget showing simulation runs grouped by archive."""
    
    def __init__(self):
        """Initialize the file tree widget."""
        super().__init__()
        self.setColumnCount(1)
        self.setHeaderLabel("Structure")
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformRowHeights(True)
    
    def populate_from_manifest(self, manifest: Dict[str, Any]):
        """
        Populate tree from manifest data.
        
        Args:
            manifest: Manifest dictionary from .liufs file
        """
        self.clear()
        
        simulation_name = manifest.get('simulation_name', 'Simulation')
        root = QTreeWidgetItem([simulation_name])
        self.addTopLevelItem(root)
        
        runs = manifest.get("runs", {}).get("children", {})
        for run_name, run_data in runs.items():
            if not isinstance(run_data, dict):
                continue

            run_children = run_data.get("children")
            if not isinstance(run_children, dict):
                continue

            run_item = QTreeWidgetItem([run_name])
            run_item.setData(0, Qt.ItemDataRole.UserRole, [run_name])
            root.addChild(run_item)
        
        self.expandAll()

    def populate_from_archives(self, archives: List[Dict[str, Any]]):
        """Populate tree from multiple open archives.

        Expected archive item shape:
        {
            "archive_id": str,
            "label": str,
            "manifest": dict,
        }
        """
        self.clear()

        root = QTreeWidgetItem(["Open .liufs Files"])
        self.addTopLevelItem(root)

        for archive in archives:
            archive_id = archive.get("archive_id")
            label = archive.get("label", "Archive")
            manifest = archive.get("manifest", {})
            if not isinstance(archive_id, str) or not isinstance(manifest, dict):
                continue

            archive_item = QTreeWidgetItem([label])
            archive_item.setData(0, Qt.ItemDataRole.UserRole, {"archive_id": archive_id, "path": []})
            root.addChild(archive_item)

            runs = manifest.get("runs", {}).get("children", {})
            if not isinstance(runs, dict):
                continue

            for run_name, run_data in runs.items():
                if not isinstance(run_data, dict):
                    continue

                run_children = run_data.get("children")
                if not isinstance(run_children, dict):
                    continue

                run_item = QTreeWidgetItem([run_name])
                run_item.setData(0, Qt.ItemDataRole.UserRole, {"archive_id": archive_id, "path": [run_name]})
                archive_item.addChild(run_item)

        self.expandAll()
    
    def get_selected_manifest_path(self) -> List[str]:
        """Get selected manifest path stored on the tree item."""
        current = self.currentItem()
        if not current:
            return []

        path = current.data(0, Qt.ItemDataRole.UserRole)
        return path if isinstance(path, list) else []

    def get_selected_reference(self) -> Dict[str, Any]:
        """Get selected archive/path reference from the tree item.

        Returns a dictionary with keys:
        - archive_id: str
        - path: list[str]
        """
        current = self.currentItem()
        if not current:
            return {}

        data = current.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            archive_id = data.get("archive_id")
            path = data.get("path")
            if isinstance(archive_id, str) and isinstance(path, list):
                return {"archive_id": archive_id, "path": path}

        if isinstance(data, list):
            return {"archive_id": "default", "path": data}

        return {}
