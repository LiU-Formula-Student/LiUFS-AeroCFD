from .reporting import NullReporter
from . import FILE_MAPPING, CFDImage
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def _resolve_workers(workers: int | None, task_count: int) -> int:
    if task_count <= 0:
        return 1
    if workers is not None and workers > 0:
        return min(workers, task_count)
    cpu_count = os.cpu_count() or 1
    return min(max(cpu_count, 1), task_count)


def is_image_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def count_image_files(data_dir: str | Path) -> int:
    root = Path(data_dir)
    count = 0
    for entry in root.iterdir():
        if entry.is_file() and is_image_file(entry):
            count += 1
    return count


def find_3d_images(data_dir):
    images = []

    for filename in sorted(os.listdir(data_dir)):
        file_path = Path(data_dir) / filename
        if not file_path.is_file():
            continue
        if not is_image_file(file_path):
            continue
        images.append(str(file_path))

    return images


def _convert_single_image_to_webp(index: int, image_path: str, output_path: Path, quality: int):
    source = Path(image_path)
    if not source.exists() or not source.is_file():
        return index, None, f"Skipping missing file: {source}"

    target = output_path / f"{source.stem}.webp"
    image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    if image is None:
        return index, None, f"Skipping unreadable image: {source.name}"

    success = cv2.imwrite(str(target), image, [cv2.IMWRITE_WEBP_QUALITY, int(quality)])
    if not success:
        return index, None, f"Failed to convert image: {source.name}"

    return index, str(target), None


def convert_images_to_webp(image_paths, output_dir, quality=80, workers=None, reporter=None):
    reporter = reporter or NullReporter()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    worker_count = _resolve_workers(workers, len(image_paths))
    created_with_index = []

    reporter.start_step(
        f"Converting {len(image_paths)} images to WebP (workers={worker_count})",
        image_count=len(image_paths),
        output_dir=str(output_path),
        quality=quality,
        workers=worker_count,
    )

    if worker_count <= 1:
        for index, image_path in enumerate(image_paths):
            _, created_path, warning_message = _convert_single_image_to_webp(
                index,
                image_path,
                output_path,
                int(quality),
            )
            reporter.advance_progress(1)
            if warning_message:
                reporter.warn(warning_message)
                continue
            if created_path is not None:
                created_with_index.append((index, created_path))
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(_convert_single_image_to_webp, index, image_path, output_path, int(quality)): index
                for index, image_path in enumerate(image_paths)
            }

            for future in as_completed(future_map):
                index, created_path, warning_message = future.result()
                reporter.advance_progress(1)
                if warning_message:
                    reporter.warn(warning_message)
                    continue
                if created_path is not None:
                    created_with_index.append((index, created_path))

    created_files = [file_path for _, file_path in sorted(created_with_index, key=lambda item: item[0])]

    reporter.finish_step(
        f"Finished WebP conversion in {output_path}",
        created_count=len(created_files),
    )
    return created_files


def find_cfd_images(data_dir):
    images = []
    for plane, pattern in FILE_MAPPING.items():
        for filename in os.listdir(data_dir):
            source_path = Path(data_dir) / filename
            if not source_path.is_file():
                continue
            match = re.match(pattern, filename, flags=re.IGNORECASE)
            if match:
                index = int(match.group(1))  # Extract the captured number
                images.append(CFDImage(name=filename, path=str(source_path), plane=plane, index=index))
    return images


def _encode_plane_video(plane: str, plane_images, output_dir: str, fps: int, extension: str):
    output_path = os.path.join(output_dir, f"{plane}.{extension}")
    list_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as list_file:
            list_path = list_file.name
            for image in plane_images:
                abs_image_path = os.path.abspath(image.path).replace("'", "'\\''")
                list_file.write(f"file '{abs_image_path}'\n")

        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-r",
            str(fps),
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-vf",
            "format=yuv420p",
            output_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        return {
            "plane": plane,
            "output_path": output_path,
            "image_count": len(plane_images),
            "returncode": result.returncode,
            "stderr": result.stderr.strip() if result.stderr else "",
        }
    finally:
        if list_path is not None and os.path.exists(list_path):
            os.unlink(list_path)


def build_video_from_images(images, output_dir="videos", fps=12, extension="mp4", workers=None, reporter=None):
    reporter = reporter or NullReporter()
    os.makedirs(output_dir, exist_ok=True)

    if shutil.which("ffmpeg") is None:
        reporter.error("Could not create videos: ffmpeg is not installed or not available in PATH.")
        return []

    planes = sorted(set(img.plane for img in images))
    worker_count = _resolve_workers(workers, len(planes))
    created_files = []

    reporter.start_step(
        f"Encoding {len(planes)} plane videos (workers={worker_count})",
        plane_count=len(planes),
        image_count=len(images),
        workers=worker_count,
        output_dir=output_dir,
    )

    plane_batches = {}
    for plane in planes:
        plane_images = sorted([img for img in images if img.plane == plane], key=lambda x: x.index)
        if not plane_images:
            continue
        plane_batches[plane] = plane_images
        reporter.advance(
            f"Building video for plane {plane} with {len(plane_images)} images",
            plane=plane,
            image_count=len(plane_images),
        )

    if worker_count <= 1:
        for plane, plane_images in plane_batches.items():
            result = _encode_plane_video(plane, plane_images, output_dir, int(fps), extension)
            reporter.advance_progress(result["image_count"])
            if result["returncode"] != 0:
                reporter.error(
                    f"Skipping plane {plane}: ffmpeg failed",
                    plane=plane,
                    stderr=result["stderr"],
                )
                continue
            created_files.append(result["output_path"])
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(_encode_plane_video, plane, plane_images, output_dir, int(fps), extension)
                for plane, plane_images in plane_batches.items()
            ]
            for future in as_completed(futures):
                result = future.result()
                reporter.advance_progress(result["image_count"])
                if result["returncode"] != 0:
                    reporter.error(
                        f"Skipping plane {result['plane']}: ffmpeg failed",
                        plane=result["plane"],
                        stderr=result["stderr"],
                    )
                    continue
                created_files.append(result["output_path"])

    created_files = sorted(created_files)

    reporter.finish_step(
        f"Finished encoding videos in {output_dir}",
        created_count=len(created_files),
    )
    return created_files
