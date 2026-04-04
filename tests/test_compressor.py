from __future__ import annotations

import json
import zipfile
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aerocfd_cli import CFDImage, FILE_MAPPING
from aerocfd_cli import __main__ as cli
from aerocfd_cli.encoder import (
    build_video_from_images,
    count_image_files,
    find_3d_images,
    find_cfd_images,
    is_image_file,
)
from aerocfd_cli.packager import DuplicateRunError, append_run_to_liufs, build_liufs
from aerocfd_cli.reporting import BaseReporter, ProgressEvent
from aerocfd_cli.scanner import build_structure


class RecordingReporter(BaseReporter):
    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def emit(self, event: ProgressEvent) -> None:
        self.events.append(event)


def _write_file(path: Path, content: str = "data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_public_imports_are_available() -> None:
    assert FILE_MAPPING["XX"] == r"X(\d+)X\.png"
    assert CFDImage(name="X1X.png", path="/tmp/X1X.png", plane="XX", index=1)


def test_cli_uses_aerocfd_prog() -> None:
    parser = cli.create_parser()
    assert parser.prog == "aerocfd"


def test_scanner_classifies_leaf_directories(tmp_path: Path) -> None:
    cfd_dir = tmp_path / "cfd"
    views_dir = tmp_path / "views"
    unknown_dir = tmp_path / "unknown"

    _write_file(cfd_dir / "X1X.png")
    _write_file(cfd_dir / "x2x.PNG")
    _write_file(views_dir / "top.png")
    _write_file(views_dir / "front.PNG")
    _write_file(views_dir / "notes.txt")
    _write_file(unknown_dir / "notes.txt")

    cfd_structure = build_structure(str(cfd_dir))
    views_structure = build_structure(str(views_dir))
    unknown_structure = build_structure(str(unknown_dir))

    assert cfd_structure == {"type": "cfd_images", "count": 2, "path": str(cfd_dir)}
    assert views_structure == {"type": "3d_views", "count": 2, "path": str(views_dir)}
    assert unknown_structure == {"type": "unknown", "count": 0, "path": str(unknown_dir)}


def test_encoder_helpers_find_expected_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_dir = tmp_path / "images"
    nested_dir = image_dir / "nested"
    _write_file(image_dir / "top.png")
    _write_file(image_dir / "front.jpg")
    _write_file(image_dir / "notes.txt")
    nested_dir.mkdir(parents=True)

    assert is_image_file(image_dir / "top.png")
    assert is_image_file("/tmp/example.webp")
    assert not is_image_file(image_dir / "notes.txt")
    assert count_image_files(image_dir) == 2
    assert find_3d_images(str(image_dir)) == [str(image_dir / "front.jpg"), str(image_dir / "top.png")]

    cfd_dir = tmp_path / "cfd"
    _write_file(cfd_dir / "X1X.png")
    _write_file(cfd_dir / "y2y.PNG")
    _write_file(cfd_dir / "Z10Z.png")
    _write_file(cfd_dir / "ignore.txt")

    cfd_images = find_cfd_images(str(cfd_dir))
    assert [(image.plane, image.index, Path(image.path).name) for image in cfd_images] == [
        ("XX", 1, "X1X.png"),
        ("YY", 2, "y2y.PNG"),
        ("ZZ", 10, "Z10Z.png"),
    ]

    # Avoid depending on a real ffmpeg binary in the test environment.
    monkeypatch.setattr("aerocfd_cli.encoder.shutil.which", lambda _: None)
    reporter = RecordingReporter()
    assert build_video_from_images(cfd_images, output_dir=tmp_path / "videos", reporter=reporter) == []
    assert any(event.kind == "error" for event in reporter.events)


def test_build_liufs_creates_manifest_and_counts_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    cfd_dir = source / "run1" / "cfd"
    views_dir = source / "run1" / "views"
    unknown_dir = source / "run1" / "unknown"

    _write_file(cfd_dir / "X1X.png")
    _write_file(cfd_dir / "X2X.png")
    _write_file(views_dir / "top.png")
    _write_file(views_dir / "front.png")
    _write_file(unknown_dir / "keep.png")
    _write_file(unknown_dir / "notes.txt")

    def fake_build_video_from_images(images, output_dir, reporter=None, **_kwargs):
        output_path = Path(output_dir) / "XX.mp4"
        output_path.write_text("video", encoding="utf-8")
        if reporter is not None:
            reporter.advance_progress(len(images))
        return [str(output_path)]

    def fake_convert_images_to_webp(image_paths, output_dir, reporter=None, **_kwargs):
        created_files = []
        for image_path in image_paths:
            output_path = Path(output_dir) / f"{Path(image_path).stem}.webp"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("webp", encoding="utf-8")
            created_files.append(str(output_path))
            if reporter is not None:
                reporter.advance_progress(1)
        return created_files

    monkeypatch.setattr("aerocfd_cli.packager.build_video_from_images", fake_build_video_from_images)
    monkeypatch.setattr("aerocfd_cli.packager.convert_images_to_webp", fake_convert_images_to_webp)

    output_file = tmp_path / "out.liufs"
    reporter = RecordingReporter()
    result = build_liufs(
        source_dir=source,
        output_file=output_file,
        include_unknown=True,
        reporter=reporter,
    )

    assert result == output_file.resolve()
    assert result.exists()

    progress_totals = [event for event in reporter.events if event.kind == "progress_total"]
    assert progress_totals
    assert progress_totals[0].data is not None
    assert progress_totals[0].data["total"] == 5

    with zipfile.ZipFile(result) as archive:
        manifest = json.loads(archive.read("manifest.json"))

    run1 = manifest["runs"]["children"]["run1"]["children"]
    assert run1["cfd"]["image_count"] == 2
    assert run1["views"]["file_count"] == 2
    assert run1["unknown"]["copied_unknown_files"] == 2
    assert run1["unknown"]["unknown_image_attempts"] == 1


def test_append_run_to_liufs_adds_a_new_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_source = tmp_path / "base"
    existing_run = base_source / "run_a"
    _write_file(existing_run / "cfd" / "X1X.png")
    _write_file(existing_run / "views" / "top.png")

    new_run = tmp_path / "new_run"
    _write_file(new_run / "cfd" / "X1X.png")
    _write_file(new_run / "cfd" / "X2X.png")
    _write_file(new_run / "views" / "front.png")

    def fake_build_video_from_images(images, output_dir, reporter=None, **_kwargs):
        output_path = Path(output_dir) / "XX.mp4"
        output_path.write_text("video", encoding="utf-8")
        if reporter is not None:
            reporter.advance_progress(len(images))
        return [str(output_path)]

    def fake_convert_images_to_webp(image_paths, output_dir, reporter=None, **_kwargs):
        created_files = []
        for image_path in image_paths:
            output_path = Path(output_dir) / f"{Path(image_path).stem}.webp"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("webp", encoding="utf-8")
            created_files.append(str(output_path))
            if reporter is not None:
                reporter.advance_progress(1)
        return created_files

    monkeypatch.setattr("aerocfd_cli.packager.build_video_from_images", fake_build_video_from_images)
    monkeypatch.setattr("aerocfd_cli.packager.convert_images_to_webp", fake_convert_images_to_webp)

    archive_path = build_liufs(base_source, output_file=tmp_path / "base.liufs")
    result = append_run_to_liufs(new_run, archive_path)

    assert result == archive_path.resolve()

    with zipfile.ZipFile(result) as archive:
        manifest = json.loads(archive.read("manifest.json"))

    runs = manifest["runs"]["children"]
    assert sorted(runs.keys()) == ["new_run", "run_a"]
    assert runs["new_run"]["children"]["cfd"]["image_count"] == 2
    assert runs["new_run"]["children"]["views"]["file_count"] == 1


def test_append_run_to_liufs_detects_duplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "base"
    existing_run = source / "run_a"
    _write_file(existing_run / "cfd" / "X1X.png")

    def fake_build_video_from_images(images, output_dir, reporter=None, **_kwargs):
        output_path = Path(output_dir) / "XX.mp4"
        output_path.write_text("video", encoding="utf-8")
        return [str(output_path)]

    monkeypatch.setattr("aerocfd_cli.packager.build_video_from_images", fake_build_video_from_images)
    monkeypatch.setattr("aerocfd_cli.packager.convert_images_to_webp", lambda *args, **kwargs: [])

    archive_path = build_liufs(source, output_file=tmp_path / "base.liufs")

    duplicate_source = tmp_path / "duplicate_source"
    _write_file(duplicate_source / "cfd" / "X1X.png")

    with pytest.raises(DuplicateRunError):
        append_run_to_liufs(duplicate_source, archive_path, run_name="run_a")

    renamed = append_run_to_liufs(duplicate_source, archive_path, run_name="run_a_copy")
    assert renamed.exists()


def test_cli_can_append_to_existing_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive_path = tmp_path / "existing.liufs"
    archive_path.write_bytes(b"placeholder")
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    calls: list[dict] = []

    def fake_append_run_to_liufs(**kwargs):
        calls.append(kwargs)
        return archive_path

    monkeypatch.setattr(cli, "append_run_to_liufs", fake_append_run_to_liufs)
    monkeypatch.setattr(cli, "build_liufs", lambda **_kwargs: archive_path)

    exit_code = cli.main([str(source_dir), "--append-to", str(archive_path)])

    assert exit_code == 0
    assert calls[0]["archive_file"] == archive_path

