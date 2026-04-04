"""Pane orchestration logic for ViewerWindow."""

from __future__ import annotations

from numbers import Integral
from pathlib import Path
from typing import Any, Dict, Optional


class PaneOrchestrationController:
    """Handles pane layout, drag/drop loading, context sync, and pane refresh."""

    def __init__(self, window: Any):
        self.window = window

    def set_view_mode(self, mode: str):
        if mode in {"single", "2-pane", "4-pane"}:
            self.window.current_view_mode = mode
            self.window.split_pane_widget.set_layout(mode)
            self.window.pane_run_refs = {i: None for i in range(self.window.split_pane_widget.get_pane_count())}
            self.window.swap_pane_index = 0
            self.setup_pane_signals()
            self.update_all_panes()
        elif mode == "swap":
            if self.window.current_view_mode != "swap":
                self.window.current_view_mode = "swap"
                self.window.split_pane_widget.set_layout("single")
                self.window.pane_run_refs = {0: None}
                self.window.swap_runs = []
                self.window.swap_current_index = 0
                self.setup_pane_signals()
                self.window.split_pane_widget.clear_all()
                self.window.info_label.appendPlainText("✓ Swap mode enabled. Drag runs to load (use ↑↓ arrows to cycle).")
            else:
                self.window.info_label.appendPlainText("✓ Swap mode active (use ↑↓ to cycle runs).")
        else:
            self.window.info_label.appendPlainText(f"⚠ Unknown view mode: {mode}")

    def setup_pane_signals(self):
        for pane in self.window.split_pane_widget.panes.values():
            if getattr(pane, "_run_drop_connected", False):
                continue
            pane.run_dropped.connect(self.window.on_tree_run_dropped)
            pane._run_drop_connected = True

    def on_tree_run_dropped(self, pane_id: int, archive_id: str, run_name: str):
        try:
            if pane_id < 0 or pane_id >= self.window.split_pane_widget.get_pane_count():
                self.window.info_label.appendPlainText(f"⚠ Pane {pane_id} is not available in current view")
                return

            handler = self.window.archives.get_archive(archive_id)
            if handler is None:
                self.window.info_label.appendPlainText(f"⚠ Archive not loaded: {archive_id}")
                return

            if run_name not in handler.get_runs():
                self.window.info_label.appendPlainText(f"⚠ Run not found: {run_name}")
                return

            archive_label = self.window.archives.get_archive_label(archive_id)

            runs = handler.manifest.get("runs", {}).get("children", {})
            run_node = runs.get(run_name, {}) if isinstance(runs, dict) else {}
            children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
            versions = [
                name
                for name, node in (children.items() if isinstance(children, dict) else [])
                if isinstance(node, dict)
            ]

            pane_context = {
                "archive_id": archive_id,
                "run_name": run_name,
                "version": None,
                "group_path": [],
                "category": None,
                "dataset": None,
                "item": None,
            }

            if versions:
                version_name = sorted(versions)[0]
                pane_context["version"] = version_name
                group_path = [run_name, version_name]
                pane_context["group_path"] = group_path
                categories = handler.get_group_categories(group_path)

                if categories:
                    category_name = sorted(categories.keys())[0]
                    pane_context["category"] = category_name
                    datasets = handler.get_category_datasets(group_path, category_name)

                    if datasets:
                        dataset_name = sorted(datasets.keys())[0]
                        pane_context["dataset"] = dataset_name
                        dataset_node = datasets.get(dataset_name, {})
                        items = []
                        if dataset_node.get("type") == "cfd_images":
                            items = sorted((dataset_node.get("videos") or {}).keys())

                        if items:
                            pane_context["item"] = items[0]

            run_ref = {
                "archive_id": archive_id,
                "run_name": run_name,
                "label": f"{archive_label} | {run_name}",
                "context": pane_context,
            }

            # In swap mode, add to swap_runs; otherwise to pane refs
            if self.window.current_view_mode == "swap":
                existing_index = next(
                    (
                        idx
                        for idx, existing in enumerate(self.window.swap_runs)
                        if existing.get("archive_id") == archive_id and existing.get("run_name") == run_name
                    ),
                    None,
                )

                if existing_index is None:
                    self.window.swap_runs.append(run_ref)
                    self.window.swap_current_index = len(self.window.swap_runs) - 1
                    load_message = (
                        f"✓ Added '{run_name}' to swap list "
                        f"({len(self.window.swap_runs)} run(s))"
                    )
                else:
                    self.window.swap_runs[existing_index] = run_ref
                    self.window.swap_current_index = existing_index
                    load_message = (
                        f"✓ '{run_name}' is already in swap list "
                        f"({existing_index + 1}/{len(self.window.swap_runs)})"
                    )

                self.window.update_swap_display()
            else:
                self.window.pane_run_refs[pane_id] = run_ref
                self.update_all_panes()
                load_message = f"✓ Loaded '{run_name}' in pane {pane_id}"
            self.update_slider_maximum()
            self.window.info_label.appendPlainText(load_message)
        except Exception as e:
            self.window.info_label.appendPlainText(f"❌ Error loading run in pane {pane_id}: {str(e)}")

    def clear_current_view(self):
        if self.window.current_view_mode == "swap":
            self.window.swap_runs = []
            self.window.swap_current_index = 0
        self.window.pane_run_refs = {
            i: None for i in range(self.window.split_pane_widget.get_pane_count())
        }
        self.window.split_pane_widget.clear_all()
        self.window.info_label.appendPlainText("✓ Cleared current view")

    def update_all_panes(self):
        if not self.window.split_pane_widget:
            return

        if self.window.current_view_mode == "swap":
            self.window.update_swap_display()
            return

        frame_index = self.window.frame_slider.value()
        for pane_id in range(self.window.split_pane_widget.get_pane_count()):
            pane = self.window.split_pane_widget.get_pane(pane_id)
            if not pane:
                continue

            run_ref = self.window.pane_run_refs.get(pane_id)
            if not run_ref:
                pane.clear()
                continue

            pixmap = self.get_pixmap_for_pane(run_ref, frame_index)
            title = run_ref.get("label", "Run")
            pane.set_content(title, pixmap)

        self.window.sync_detached_windows()

    def get_pixmap_for_pane(self, run_ref: Dict[str, Any], frame_index: int):
        pane_context = run_ref.get("context")
        if pane_context:
            return self.window.get_pane_pixmap_with_context(run_ref, frame_index, pane_context)

        if (
            run_ref.get("archive_id") == self.window.state.current_archive_id
            and run_ref.get("run_name") == self.window.state.current_run_name
        ):
            player = self.window.media.get_video_player(
                self.window.state.current_archive_id, self.window.state.current_run_name
            )
            if player:
                return player.get_frame(frame_index)
            return None

        return self.window.get_compare_run_pixmap(run_ref, frame_index)

    def update_pane_contexts_for_selector_change(self):
        version_name = self.window.version_combo.currentText() if self.window.version_combo else ""
        category_name = self.window.category_combo.currentText() if self.window.category_combo else ""
        dataset_name = self.window.dataset_combo.currentText() if self.window.dataset_combo else ""
        item_name = self.window.item_combo.currentText() if self.window.item_combo else ""

        if not version_name:
            return

        current_view_mode = getattr(self.window, "current_view_mode", "single")
        if current_view_mode == "swap":
            run_ref_entries = list(enumerate(getattr(self.window, "swap_runs", [])))
        else:
            run_ref_entries = list(self.window.pane_run_refs.items())

        for pane_id, run_ref in run_ref_entries:
            if not run_ref:
                continue

            archive_id = run_ref.get("archive_id")
            run_name = run_ref.get("run_name")
            if not archive_id or not run_name:
                continue

            handler = None
            if hasattr(self.window, "archives") and self.window.archives:
                handler = self.window.archives.get_archive(archive_id)
            if handler is None:
                open_archives = getattr(self.window, "open_archives", {})
                handler = open_archives.get(archive_id)
            if handler is None:
                continue

            runs = handler.manifest.get("runs", {}).get("children", {})
            run_node = runs.get(run_name, {}) if isinstance(runs, dict) else {}
            children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
            if version_name not in children:
                continue

            group_path = [run_name, version_name]
            categories = handler.get_group_categories(group_path)
            if category_name and category_name not in categories:
                continue

            selected_category = category_name or (sorted(categories.keys())[0] if categories else None)
            if not selected_category:
                continue

            datasets = handler.get_category_datasets(group_path, selected_category)
            if dataset_name and dataset_name not in datasets:
                continue

            selected_dataset = dataset_name or (sorted(datasets.keys())[0] if datasets else None)
            if not selected_dataset:
                continue

            dataset_node = datasets.get(selected_dataset, {})
            selected_item = item_name

            if dataset_node.get("type") == "cfd_images":
                videos = dataset_node.get("videos") or {}
                if selected_item and selected_item not in videos:
                    continue
                if not selected_item:
                    video_items = sorted(videos.keys())
                    selected_item = video_items[0] if video_items else None
            elif dataset_node.get("type") == "3d_views":
                files = dataset_node.get("files") or []
                file_items = sorted(Path(path).name for path in files if isinstance(path, str))
                if selected_item and selected_item not in file_items:
                    continue
                if not selected_item:
                    selected_item = file_items[0] if file_items else None

            pane_context = run_ref.get("context") or {}
            pane_context.update(
                {
                    "archive_id": archive_id,
                    "run_name": run_name,
                    "version": version_name,
                    "group_path": group_path,
                    "category": selected_category,
                    "dataset": selected_dataset,
                    "item": selected_item,
                }
            )
            run_ref["context"] = pane_context
            if current_view_mode == "swap":
                self.window.swap_runs[pane_id] = run_ref
            else:
                self.window.pane_run_refs[pane_id] = run_ref

    def update_slider_maximum(self):
        if not self.window.split_pane_widget:
            return

        frame_counts = []
        current_view_mode = getattr(self.window, "current_view_mode", "single")
        if current_view_mode == "swap":
            swap_runs = getattr(self.window, "swap_runs", [])
            for run_ref in swap_runs:
                if run_ref and run_ref.get("context"):
                    count = self.window.get_video_frame_count_for_pane(run_ref)
                    if count > 0:
                        frame_counts.append(count)
        else:
            for pane_id in range(self.window.split_pane_widget.get_pane_count()):
                run_ref = self.window.pane_run_refs.get(pane_id)
                if run_ref and run_ref.get("context"):
                    count = self.window.get_video_frame_count_for_pane(run_ref)
                    if count > 0:
                        frame_counts.append(count)

        player = None
        if hasattr(self.window, "media") and hasattr(self.window, "state") and self.window.media and self.window.state:
            player = self.window.media.get_video_player(
                self.window.state.current_archive_id, self.window.state.current_run_name
            )
        elif hasattr(self.window, "video_player"):
            player = self.window.video_player
        if player:
            frame_counts.append(player.get_total_frames())

        if frame_counts:
            max_frames = min(frame_counts)
            raw_current_value = self.window.frame_slider.value()
            current_value = int(raw_current_value) if isinstance(raw_current_value, Integral) else 0
            clamped_value = min(max(current_value, 0), max(max_frames - 1, 0))
            self.window.frame_slider.blockSignals(True)
            self.window.frame_slider.setMaximum(max(max_frames - 1, 0))
            self.window.frame_slider.setValue(clamped_value)
            self.window.frame_slider.blockSignals(False)
            self.window.frame_slider.setEnabled(True)
        else:
            self.window.frame_slider.setMaximum(0)
            self.window.frame_slider.setEnabled(False)
