"""
Manages pane state: layout, content, drag-drop assignments.
"""

from typing import Dict, Any, Optional, List


class PaneReference:
    """Represents a run loaded into a specific pane."""
    
    def __init__(self, pane_id: int, archive_id: str, run_name: str, label: str):
        self.pane_id = pane_id
        self.archive_id = archive_id
        self.run_name = run_name
        self.label = label
        
        # Per-pane selection context (independent of primary selector)
        self.context: Dict[str, Any] = {
            "version": None,
            "group_path": [],
            "category": None,
            "dataset": None,
            "item": None,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "archive_id": self.archive_id,
            "run_name": self.run_name,
            "label": self.label,
            "context": self.context,
        }


class PaneManager:
    """Manages pane layout, content, and drag-drop assignments."""
    
    def __init__(self):
        """Initialize pane manager."""
        self.pane_references: Dict[int, Optional[PaneReference]] = {}
        self.current_layout = "single"
        self.pane_count = 1
    
    def set_layout(self, layout_type: str):
        """
        Change pane layout.
        
        Args:
            layout_type: "single", "2-pane", or "4-pane"
        """
        pane_counts = {"single": 1, "2-pane": 2, "4-pane": 4}
        if layout_type not in pane_counts:
            return
        
        new_count = pane_counts[layout_type]
        self.current_layout = layout_type
        self.pane_count = new_count
        
        # Reset pane references to match new layout
        self.pane_references = {i: None for i in range(new_count)}
    
    def get_pane_count(self) -> int:
        """Get current number of panes."""
        return self.pane_count
    
    def set_pane_reference(
        self, pane_id: int, archive_id: str, run_name: str, label: str
    ) -> Optional[PaneReference]:
        """
        Assign a run to a pane.
        
        Args:
            pane_id: Pane index
            archive_id: Archive ID
            run_name: Run name
            label: Display label
            
        Returns:
            PaneReference or None if pane_id invalid
        """
        if pane_id < 0 or pane_id >= self.pane_count:
            return None
        
        ref = PaneReference(pane_id, archive_id, run_name, label)
        self.pane_references[pane_id] = ref
        return ref
    
    def get_pane_reference(self, pane_id: int) -> Optional[PaneReference]:
        """Get the reference for a pane."""
        return self.pane_references.get(pane_id)
    
    def clear_pane(self, pane_id: int):
        """Clear a pane's content."""
        if pane_id in self.pane_references:
            self.pane_references[pane_id] = None
    
    def clear_all(self):
        """Clear all panes."""
        self.pane_references = {i: None for i in range(self.pane_count)}
    
    def get_loaded_panes(self) -> List[int]:
        """Get list of pane IDs that have content."""
        return [pid for pid, ref in self.pane_references.items() if ref is not None]
    
    def collect_pane_run_refs(self) -> List[Dict[str, Any]]:
        """Collect all unique run references from loaded panes."""
        refs = []
        seen = set()
        for pane_ref in self.pane_references.values():
            if not pane_ref:
                continue
            key = (pane_ref.archive_id, pane_ref.run_name)
            if key in seen:
                continue
            seen.add(key)
            refs.append(pane_ref.to_dict())
        return refs
    
    def update_all_pane_contexts(
        self,
        version: str,
        category: str,
        dataset: str,
        item: str,
        verify_fn=None,
    ):
        """
        Update all pane contexts with new selector values.
        
        Args:
            version: Selected version
            category: Selected category
            dataset: Selected dataset
            item: Selected item
            verify_fn: Optional callback to verify context is valid for a pane
                      Should return True if valid, False otherwise
        """
        for pane_ref in self.pane_references.values():
            if not pane_ref:
                continue
            
            # Verify if provided
            if verify_fn:
                context = {
                    "version": version,
                    "category": category,
                    "dataset": dataset,
                    "item": item,
                }
                if not verify_fn(pane_ref.archive_id, pane_ref.run_name, context):
                    continue
            
            # Update the context
            pane_ref.context["version"] = version
            pane_ref.context["category"] = category
            pane_ref.context["dataset"] = dataset
            pane_ref.context["item"] = item
