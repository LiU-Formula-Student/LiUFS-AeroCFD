from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import tempfile
import zipfile

from .encoder import (
    build_video_from_images,
    find_cfd_images,
    find_3d_images,
    convert_images_to_webp,
    count_image_files,
    is_image_file,
)
from .scanner import build_structure
from .reporting import BaseReporter, NullReporter


class DuplicateRunError(ValueError):
    """Raised when an archive already contains a run with the requested name."""

    def __init__(self, run_name: str, existing_runs: list[str]):
        self.run_name = run_name
        self.existing_runs = existing_runs
        super().__init__(f"A run with this name already exists: {run_name}")

def _is_leaf(node: dict) -> bool:
    return isinstance(node, dict) and "type" in node and "path" in node


def _to_posix(path: Path) -> str:
    return path.as_posix()


def _coerce_liufs_output_path(output_file: str | Path | None, default_path: Path) -> Path:
    if output_file is None:
        return default_path if default_path.suffix.lower() == ".liufs" else default_path.with_suffix(".liufs")

    output_path = Path(output_file).resolve()
    if output_path.suffix.lower() != ".liufs":
        output_path = output_path.with_suffix(".liufs")
    return output_path


def _read_manifest_from_archive(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path, "r") as archive:
        if "manifest.json" not in archive.namelist():
            raise ValueError("manifest.json not found at root of .liufs file")

        with archive.open("manifest.json") as handle:
            manifest = json.load(handle)

    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must contain a JSON object")

    return manifest


def _find_package_root(extracted_root: Path, manifest: dict, archive_path: Path) -> Path:
    # Check if manifest.json is at the root level — if so, this is the package root
    if (extracted_root / "manifest.json").exists():
        return extracted_root

    # Otherwise look for a subdirectory matching the simulation name
    simulation_name = manifest.get("simulation_name")
    if isinstance(simulation_name, str) and simulation_name:
        candidate = extracted_root / simulation_name
        if candidate.is_dir():
            return candidate

    # As a fallback, use the only subdirectory if there's exactly one
    directories = [path for path in extracted_root.iterdir() if path.is_dir()]
    if len(directories) == 1:
        return directories[0]

    raise ValueError(f"Could not locate extracted package root for archive: {archive_path}")


def _write_archive(package_root: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.parent / f".{output_path.name}.tmp"
    if temporary_output.exists():
        temporary_output.unlink()

    _zip_directory(package_root, temporary_output)
    temporary_output.replace(output_path)
    return output_path


def _copy_files(src_dir: Path, dst_dir: Path, reporter: BaseReporter | None = None) -> tuple[list[str], int]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    image_attempts = 0

    for item in sorted(src_dir.iterdir()):
        if not item.is_file():
            continue
        if is_image_file(item):
            image_attempts += 1
            if reporter is not None:
                reporter.advance_progress(1)
        target = dst_dir / item.name
        shutil.copy2(item, target)
        copied.append(item.name)

    return copied, image_attempts


def _count_total_images(structure_node: dict, *, include_unknown: bool) -> int:
    if _is_leaf(structure_node):
        leaf_type = structure_node.get("type", "unknown")
        leaf_path = Path(structure_node["path"])
        if leaf_type == "cfd_images":
            return len(find_cfd_images(str(leaf_path)))
        if leaf_type == "3d_views":
            return len(find_3d_images(str(leaf_path)))
        if leaf_type == "unknown" and include_unknown:
            return count_image_files(leaf_path)
        return 0

    total = 0
    for child in structure_node.values():
        total += _count_total_images(child, include_unknown=include_unknown)
    return total


def _resolve_workers(workers: int | None, task_count: int) -> int:
    if task_count <= 0:
        return 1
    if workers is not None and workers > 0:
        return min(workers, task_count)
    cpu_count = os.cpu_count() or 1
    return min(max(cpu_count, 1), task_count)


def _process_leaf(
    leaf_info: dict,
    package_root: Path,
    manifest_node: dict,
    *,
    fps: int,
    extension: str,
    webp_quality: int,
    workers: int | None,
    include_unknown: bool,
    reporter: BaseReporter,
) -> None:
    src_dir = Path(leaf_info["path"])
    leaf_type = leaf_info.get("type", "unknown")

    manifest_node["type"] = leaf_type
    manifest_node["source_path"] = str(src_dir)
    manifest_node["source_count"] = leaf_info.get("count", 0)
    reporter.advance(f"Processing {leaf_type}: {src_dir.name}")
    if leaf_type == "cfd_images":
        images = find_cfd_images(str(src_dir))
        package_root.mkdir(parents=True, exist_ok=True)

        created_files = build_video_from_images(
            images,
            output_dir=str(package_root),
            fps=fps,
            extension=extension,
            workers=workers,
            reporter=reporter,
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
        image_paths = find_3d_images(str(src_dir))
        converted_files = convert_images_to_webp(
            image_paths,
            output_dir=str(package_root),
            quality=webp_quality,
            workers=workers,
            reporter=reporter,
        )
        manifest_node["files"] = [
            _to_posix(Path(file_path).relative_to(package_root.parent.parent))
            for file_path in converted_files
        ]
        manifest_node["file_count"] = len(converted_files)

    else:
        manifest_node["skipped"] = True
        manifest_node["reason"] = "unknown folder type"
        if include_unknown:
            copied, image_attempts = _copy_files(src_dir, package_root, reporter=reporter)
            manifest_node["files"] = [
                _to_posix((package_root / name).relative_to(package_root.parent.parent))
                for name in copied
            ]
            manifest_node["copied_unknown_files"] = len(copied)
            manifest_node["unknown_image_attempts"] = image_attempts


def _build_manifest_tree(
    structure_node: dict,
    manifest_node: dict,
    package_root: Path,
    *,
    fps: int,
    extension: str,
    webp_quality: int,
    workers: int | None,
    include_unknown: bool,
    reporter: BaseReporter,
) -> None:
    leaf_jobs: list[tuple[dict, Path, dict]] = []

    def collect(node: dict, node_manifest: dict, node_root: Path) -> None:
        if _is_leaf(node):
            leaf_jobs.append((node, node_root, node_manifest))
            return

        node_manifest["children"] = {}
        for child_name, child_node in sorted(node.items()):
            child_manifest: dict = {}
            node_manifest["children"][child_name] = child_manifest
            collect(child_node, child_manifest, node_root / child_name)

    collect(structure_node, manifest_node, package_root)

    package_workers = _resolve_workers(workers, len(leaf_jobs))
    effective_workers = workers if workers is not None and workers > 0 else (os.cpu_count() or 1)
    media_workers = max(1, min(3, effective_workers // max(package_workers, 1)))

    if package_workers <= 1:
        for leaf_info, leaf_root, leaf_manifest in leaf_jobs:
            _process_leaf(
                leaf_info,
                leaf_root,
                leaf_manifest,
                fps=fps,
                extension=extension,
                webp_quality=webp_quality,
                workers=media_workers,
                include_unknown=include_unknown,
                reporter=reporter,
            )
        return

    reporter.advance(
        f"Processing {len(leaf_jobs)} leaf directories in parallel with {package_workers} workers",
        leaf_count=len(leaf_jobs),
        worker_count=package_workers,
    )

    with ThreadPoolExecutor(max_workers=package_workers) as executor:
        futures = [
            executor.submit(
                _process_leaf,
                leaf_info,
                leaf_root,
                leaf_manifest,
                fps=fps,
                extension=extension,
                webp_quality=webp_quality,
                workers=media_workers,
                include_unknown=include_unknown,
                reporter=reporter,
            )
            for leaf_info, leaf_root, leaf_manifest in leaf_jobs
        ]

        for future in as_completed(futures):
            future.result()


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
    webp_quality: int = 80,
    workers: int | None = None,
    include_unknown: bool = False,
    reporter: BaseReporter | None = None,
) -> Path:
    reporter = reporter or NullReporter()
    source_path = Path(source_dir).resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source_path}")

    reporter.start_step(f"Scanning simulation directory: {source_path}")
    structure = build_structure(str(source_path), reporter=reporter)
    reporter.finish_step("Directory scan complete")
    total_images = _count_total_images(structure, include_unknown=include_unknown)
    reporter.set_total(total_images, description="Processing CFD and 3D images")

    output_path = _coerce_liufs_output_path(output_file, source_path.with_suffix(".liufs"))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    reporter.start_step("Building package contents")
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
                "webp_quality": webp_quality,
                "workers": workers,
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
            webp_quality=webp_quality,
            workers=workers,
            include_unknown=include_unknown,
            reporter=reporter
        )
        reporter.complete_progress("Image processing complete")
        reporter.finish_step("Package contents built")

        reporter.start_step("Writing manifest.json")
        _write_manifest(package_root, manifest)
        reporter.start_step(f"Creating archive: {output_path.name}")
        _zip_directory(package_root, output_path)
        reporter.finish_step(f"Archive created: {output_path}")

    return output_path


def append_run_to_liufs(
    source_dir: str | Path,
    archive_file: str | Path,
    output_file: str | Path | None = None,
    *,
    run_name: str | None = None,
    fps: int = 12,
    extension: str = "mp4",
    webp_quality: int = 80,
    workers: int | None = None,
    include_unknown: bool = False,
    reporter: BaseReporter | None = None,
) -> Path:
    reporter = reporter or NullReporter()
    source_path = Path(source_dir).resolve()
    if not source_path.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source_path}")

    archive_path = Path(archive_file).resolve()
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive does not exist: {archive_path}")

    if archive_path.suffix.lower() != ".liufs":
        raise ValueError(f"Archive must have .liufs extension, got: {archive_path.suffix}")

    target_run_name = (run_name or source_path.name).strip()
    if not target_run_name:
        raise ValueError("Run name cannot be empty")

    output_path = _coerce_liufs_output_path(output_file, archive_path)
    manifest = _read_manifest_from_archive(archive_path)

    runs_node = manifest.setdefault("runs", {})
    if not isinstance(runs_node, dict):
        raise ValueError("manifest.json has an invalid 'runs' section")

    run_children = runs_node.setdefault("children", {})
    if not isinstance(run_children, dict):
        raise ValueError("manifest.json has an invalid 'runs.children' section")

    if target_run_name in run_children:
        raise DuplicateRunError(target_run_name, sorted(run_children.keys()))

    reporter.start_step(f"Scanning simulation directory: {source_path}")
    structure = build_structure(str(source_path), reporter=reporter)
    reporter.finish_step("Directory scan complete")

    total_images = _count_total_images(structure, include_unknown=include_unknown)
    reporter.set_total(total_images, description="Processing CFD and 3D images")

    reporter.start_step("Building package contents")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(tmp_root)

        package_root = _find_package_root(tmp_root, manifest, archive_path)
        run_root = package_root / "runs" / target_run_name
        run_root.mkdir(parents=True, exist_ok=True)

        run_manifest: dict = {}
        run_children[target_run_name] = run_manifest

        _build_manifest_tree(
            structure,
            run_manifest,
            run_root,
            fps=fps,
            extension=extension,
            webp_quality=webp_quality,
            workers=workers,
            include_unknown=include_unknown,
            reporter=reporter,
        )
        reporter.complete_progress("Image processing complete")
        reporter.finish_step("Package contents built")

        reporter.start_step("Writing manifest.json")
        manifest["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        _write_manifest(package_root, manifest)
        reporter.start_step(f"Creating archive: {output_path.name}")
        _write_archive(package_root, output_path)
        reporter.finish_step(f"Archive created: {output_path}")

    return output_path
