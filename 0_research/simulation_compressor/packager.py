from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import tempfile
import zipfile

from .encoder import build_video_from_images, find_cfd_images
from .scanner import build_structure


def _is_leaf(node: dict) -> bool:
    return isinstance(node, dict) and "type" in node and "path" in node


def _to_posix(path: Path) -> str:
    return path.as_posix()


def _copy_files(src_dir: Path, dst_dir: Path) -> list[str]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    for item in sorted(src_dir.iterdir()):
        if not item.is_file():
            continue
        target = dst_dir / item.name
        shutil.copy2(item, target)
        copied.append(item.name)

    return copied


def _process_leaf(
    leaf_info: dict,
    package_root: Path,
    manifest_node: dict,
    *,
    fps: int,
    extension: str,
    include_unknown: bool,
) -> None:
    src_dir = Path(leaf_info["path"])
    leaf_type = leaf_info.get("type", "unknown")

    manifest_node["type"] = leaf_type
    manifest_node["source_path"] = str(src_dir)
    manifest_node["source_count"] = leaf_info.get("count", 0)

    if leaf_type == "cfd_images":
        images = find_cfd_images(str(src_dir))
        package_root.mkdir(parents=True, exist_ok=True)

        created_files = build_video_from_images(
            images,
            output_dir=str(package_root),
            fps=fps,
            extension=extension,
        )

        manifest_node["planes"] = sorted({image.plane for image in images})
        manifest_node["videos"] = {
            Path(video_path).stem: _to_posix(Path(video_path).relative_to(package_root.parent.parent))
            for video_path in created_files
        }
        manifest_node["image_count"] = len(images)

        if not created_files:
            manifest_node["warning"] = "No videos created"

    elif leaf_type == "3d_views":
        copied = _copy_files(src_dir, package_root)
        manifest_node["files"] = [
            _to_posix((package_root / name).relative_to(package_root.parent.parent))
            for name in copied
        ]
        manifest_node["file_count"] = len(copied)

    else:
        manifest_node["skipped"] = True
        manifest_node["reason"] = "unknown folder type"
        if include_unknown:
            copied = _copy_files(src_dir, package_root)
            manifest_node["files"] = [
                _to_posix((package_root / name).relative_to(package_root.parent.parent))
                for name in copied
            ]
            manifest_node["copied_unknown_files"] = len(copied)


def _build_manifest_tree(
    structure_node: dict,
    manifest_node: dict,
    package_root: Path,
    *,
    fps: int,
    extension: str,
    include_unknown: bool,
) -> None:
    if _is_leaf(structure_node):
        _process_leaf(
            structure_node,
            package_root,
            manifest_node,
            fps=fps,
            extension=extension,
            include_unknown=include_unknown,
        )
        return

    manifest_node["children"] = {}

    for child_name, child_node in sorted(structure_node.items()):
        child_manifest: dict = {}
        manifest_node["children"][child_name] = child_manifest
        _build_manifest_tree(
            child_node,
            child_manifest,
            package_root / child_name,
            fps=fps,
            extension=extension,
            include_unknown=include_unknown,
        )


def _write_manifest(package_root: Path, manifest: dict) -> None:
    manifest_path = package_root / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)


def _zip_directory(directory: Path, output_file: Path) -> Path:
    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, path.relative_to(directory))
    return output_file


def build_liufs(
    source_dir: str | Path,
    output_file: str | Path | None = None,
    *,
    fps: int = 12,
    extension: str = "mp4",
    include_unknown: bool = False,
) -> Path:
    source_path = Path(source_dir).resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source_path}")

    structure = build_structure(str(source_path))

    if output_file is None:
        output_path = source_path.with_suffix(".liufs")
    else:
        output_path = Path(output_file).resolve()
        if output_path.suffix.lower() != ".liufs":
            output_path = output_path.with_suffix(".liufs")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        package_root = tmp_root / source_path.name
        package_root.mkdir(parents=True, exist_ok=True)

        manifest = {
            "format_version": 1,
            "simulation_name": source_path.name,
            "source_root": str(source_path),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "builder": {
                "fps": fps,
                "video_extension": extension,
                "include_unknown": include_unknown,
            },
            "runs": {},
        }

        runs_root = package_root / "runs"
        runs_root.mkdir(parents=True, exist_ok=True)

        _build_manifest_tree(
            structure,
            manifest["runs"],
            runs_root,
            fps=fps,
            extension=extension,
            include_unknown=include_unknown,
        )

        _write_manifest(package_root, manifest)
        _zip_directory(package_root, output_path)

    return output_path
