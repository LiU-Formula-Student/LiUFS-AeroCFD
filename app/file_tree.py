"""File tree widget for displaying high-level simulation navigation."""

from typing import Dict, Any, List
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView
from PySide6.QtCore import Qt


class FileTreeWidget(QTreeWidget):
    """Tree widget showing simulation runs and image groups as leaf nodes."""
    
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
            run_item = QTreeWidgetItem([run_name])
            run_item.setData(0, Qt.ItemDataRole.UserRole, [])
            root.addChild(run_item)

            run_children = run_data.get("children", {}) if isinstance(run_data, dict) else {}
            for group_name, group_data in run_children.items():
                group_item = QTreeWidgetItem([group_name])
                group_item.setData(0, Qt.ItemDataRole.UserRole, [run_name, group_name])
                run_item.addChild(group_item)
        
        self.expandAll()
    
    def get_selected_manifest_path(self) -> List[str]:
        """Get selected manifest path stored on the tree item."""
        current = self.currentItem()
        if not current:
            return []

        path = current.data(0, Qt.ItemDataRole.UserRole)
        return path if isinstance(path, list) else []
