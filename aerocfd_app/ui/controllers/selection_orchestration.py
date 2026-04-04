"""Selection and media-loading orchestration logic for ViewerWindow."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SelectionOrchestrationController:
    """Handles selection combos and selected media loading workflow."""

    def __init__(self, window: Any):
        self.window = window

    def load_run_node(self, run_name: str):
        archive_id = self.window.state.current_archive_id
        if not archive_id:
            return

        try:
            handler = self.window.archives.get_archive(archive_id)
            if not handler:
                return

            runs = handler.manifest.get("runs", {}).get("children", {})
            run_node = runs.get(run_name, {}) if isinstance(runs, dict) else {}
            children = run_node.get("children", {}) if isinstance(run_node, dict) else {}
            versions = [
                name
                for name, node in (children.items() if isinstance(children, dict) else [])
                if isinstance(node, dict)
            ]

            if not versions:
                self.window.reset_option_controls()
                self.window.info_label.clear()
                self.window.info_label.appendPlainText("No versions found for this run")
                self.window.frame_slider.setMaximum(0)
                return

            self.window.state.set_run(run_name)
            self.window.state.set_available_versions(versions)

            self.window.version_combo.blockSignals(True)
            self.window.version_combo.clear()
            for version_name in self.window.state.current_versions:
                self.window.version_combo.addItem(version_name)
            self.window.version_combo.blockSignals(False)
            self.window.version_combo.setEnabled(True)

            self.populate_categories_for_version()
        except Exception as e:
            self.window.info_label.clear()
            self.window.info_label.appendPlainText(f"❌ Error: {str(e)}")

    def populate_categories_for_version(self):
        archive_id = self.window.state.current_archive_id
        run_name = self.window.state.current_run_name
        if not archive_id or not run_name:
            return

        handler = self.window.archives.get_archive(archive_id)
        if not handler:
            return

        version_name = self.window.version_combo.currentText()
        if not version_name:
            return

        group_path = [run_name, version_name]
        self.window.state.set_version(version_name)
        self.window.state.set_group_path(group_path)

        categories = handler.get_group_categories(group_path)
        if not categories:
            self.window.state.set_available_categories({})
            self.window.category_combo.blockSignals(True)
            self.window.category_combo.clear()
            self.window.category_combo.blockSignals(False)
            self.window.category_combo.setEnabled(False)
            self.window.dataset_combo.clear()
            self.window.dataset_combo.setEnabled(False)
            self.window.item_combo.clear()
            self.window.item_combo.setEnabled(False)
            self.window.info_label.clear()
            self.window.info_label.appendPlainText("No categories found for selected version")
            return

        self.window.state.set_available_categories(categories)

        self.window.category_combo.blockSignals(True)
        self.window.category_combo.clear()
        for category_name in sorted(categories.keys()):
            self.window.category_combo.addItem(category_name)
        self.window.category_combo.blockSignals(False)
        self.window.category_combo.setEnabled(True)

        self.populate_datasets_for_category()

    def populate_datasets_for_category(self):
        archive_id = self.window.state.current_archive_id
        if not archive_id:
            return

        handler = self.window.archives.get_archive(archive_id)
        if not handler:
            return

        category_name = self.window.category_combo.currentText()
        if not category_name:
            return

        datasets = handler.get_category_datasets(self.window.state.current_group_path, category_name)
        self.window.state.set_available_datasets(datasets)

        self.window.dataset_combo.blockSignals(True)
        self.window.dataset_combo.clear()
        for dataset_name in sorted(datasets.keys()):
            self.window.dataset_combo.addItem(dataset_name)
        self.window.dataset_combo.blockSignals(False)
        self.window.dataset_combo.setEnabled(bool(datasets))

        self.populate_items_for_dataset()

    def populate_items_for_dataset(self):
        previous_item = self.window.item_combo.currentText()
        dataset_name = self.window.dataset_combo.currentText()
        dataset_node = self.window.state.current_datasets.get(dataset_name, {})

        items: list[str] = []
        if dataset_node.get("type") == "cfd_images":
            items = sorted((dataset_node.get("videos") or {}).keys())
        elif dataset_node.get("type") == "3d_views":
            files = dataset_node.get("files") or []
            items = sorted(Path(path).name for path in files if isinstance(path, str))

        self.window.item_combo.blockSignals(True)
        self.window.item_combo.clear()
        for item in items:
            self.window.item_combo.addItem(item)

        if items:
            if previous_item and previous_item in items:
                self.window.item_combo.setCurrentText(previous_item)
            else:
                self.window.item_combo.setCurrentIndex(0)

        self.window.item_combo.blockSignals(False)
        self.window.item_combo.setEnabled(bool(items))

        if items:
            self.window.info_label.clear()
            self.window.info_label.appendPlainText("Select a plane to load media, or drag a run into any pane.")

    def on_version_changed(self, _index: int):
        self.populate_categories_for_version()
        self.window.update_pane_contexts_for_selector_change()
        self.window.update_all_panes()
        self.window.update_slider_maximum()

    def on_category_changed(self, _index: int):
        self.populate_datasets_for_category()
        self.window.update_pane_contexts_for_selector_change()
        self.window.update_all_panes()
        self.window.update_slider_maximum()

    def on_dataset_changed(self, _index: int):
        self.populate_items_for_dataset()
        self.window.update_pane_contexts_for_selector_change()
        self.window.update_all_panes()
        self.window.update_slider_maximum()

    def on_item_changed(self, _index: int):
        self.load_selected_media()
        self.window.update_pane_contexts_for_selector_change()
        self.window.update_all_panes()
        self.window.update_slider_maximum()

    def load_selected_media(self):
        archive_id = self.window.state.current_archive_id
        run_name = self.window.state.current_run_name
        if not archive_id or not run_name:
            return

        category_name = self.window.category_combo.currentText()
        dataset_name = self.window.dataset_combo.currentText()
        item_name = self.window.item_combo.currentText()
        if not category_name or not dataset_name or not item_name:
            return

        dataset_node = self.window.state.current_datasets.get(dataset_name)
        if not dataset_node:
            return

        try:
            handler = self.window.archives.get_archive(archive_id)
            if not handler:
                return

            data_type = dataset_node.get("type")

            if data_type == "cfd_images":
                rel_video_path = (dataset_node.get("videos") or {}).get(item_name)
                if not isinstance(rel_video_path, str):
                    self.window.info_label.clear()
                    self.window.info_label.appendPlainText("⚠ Warning: Video path not found in manifest")
                    return

                archive_path = handler.resolve_archive_path(self.window.state.current_group_path, rel_video_path)
                player = self.window.media.get_video_player(archive_id, archive_path)
                if not player:
                    self.window.info_label.clear()
                    self.window.info_label.appendPlainText("❌ Error: Cannot load video")
                    return

                self.window.state.set_media_type("video")
                self.window.state.set_video_path(archive_path)
                frame_count = player.get_total_frames()
                self.window.frame_slider.setMaximum(max(frame_count - 1, 0))
                self.window.frame_slider.setValue(0)
                self.window.frame_slider.setEnabled(frame_count > 0)

                self.window.display_frame(0)
                self.window.update_all_panes()
                self.window.update_slider_maximum()
                self.window.info_label.clear()
                self.window.info_label.appendPlainText(
                    f"✓ Loaded: {category_name}/{dataset_name}/{item_name}\n"
                    f"  Frames: {frame_count} | FPS: {player.fps:.2f}"
                )

            elif data_type == "3d_views":
                files = dataset_node.get("files") or []
                matching = [path for path in files if isinstance(path, str) and Path(path).name == item_name]
                if not matching:
                    self.window.info_label.clear()
                    self.window.info_label.appendPlainText("⚠ Warning: Image path not found in manifest")
                    return

                archive_path = handler.resolve_archive_path(self.window.state.current_group_path, matching[0])
                pixmap = self.window.media.load_static_image(archive_id, archive_path)
                if not pixmap:
                    self.window.info_label.clear()
                    self.window.info_label.appendPlainText("❌ Error: Cannot read image file")
                    return

                self.window.state.set_media_type("image")
                self.window.frame_slider.setMaximum(0)
                self.window.frame_slider.setEnabled(False)

                pane = self.window.split_pane_widget.get_pane(0)
                if pane:
                    pane.set_content(f"{category_name}/{dataset_name}/{item_name}", pixmap)
                self.window.info_label.clear()
                self.window.info_label.appendPlainText(
                    f"✓ Loaded: {category_name}/{dataset_name}/{item_name}\n"
                    f"  Size: {pixmap.width()}x{pixmap.height()} px"
                )
            else:
                self.window.info_label.clear()
                self.window.info_label.appendPlainText(f"⚠ Warning: Unknown media type '{data_type}'")
        except Exception as e:
            self.window.info_label.clear()
            self.window.info_label.appendPlainText(f"❌ Error: {str(e)}")
