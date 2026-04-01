from .reporting import NullReporter
from . import FILE_MAPPING, CFDImage
import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


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


def convert_images_to_webp(image_paths, output_dir, quality=80, reporter=None):
    reporter = reporter or NullReporter()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    created_files = []

    reporter.start_step(
        f"Converting {len(image_paths)} images to WebP",
        image_count=len(image_paths),
        output_dir=str(output_path),
        quality=quality,
    )

    for image_path in image_paths:
        source = Path(image_path)
        reporter.advance_progress(1)
        if not source.exists() or not source.is_file():
            reporter.warn(f"Skipping missing file: {source}")
            continue

        reporter.advance(f"Converting {source.name} to WebP")
        target = output_path / f"{source.stem}.webp"

        image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
        if image is None:
            reporter.warn(f"Skipping unreadable image: {source.name}")
            continue

        success = cv2.imwrite(str(target), image, [cv2.IMWRITE_WEBP_QUALITY, int(quality)])
        if not success:
            reporter.warn(f"Failed to convert image: {source.name}")
            continue

        created_files.append(str(target))

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


def build_video_from_images(images, output_dir="videos", fps=12, extension="mp4", reporter=None):
    reporter = reporter or NullReporter()
    os.makedirs(output_dir, exist_ok=True)

    if shutil.which("ffmpeg") is None:
        reporter.error("Could not create videos: ffmpeg is not installed or not available in PATH.")
        return []

    created_files = []
    planes = sorted(set(img.plane for img in images))

    reporter.start_step(
        f"Encoding {len(planes)} plane videos",
        plane_count=len(planes),
        image_count=len(images),
        output_dir=output_dir,
    )

    for plane in planes:
        plane_images = sorted([img for img in images if img.plane == plane], key=lambda x: x.index)
        if not plane_images:
            continue

        reporter.advance(
            f"Building video for plane {plane} with {len(plane_images)} images",
            plane=plane,
            image_count=len(plane_images),
        )

        output_path = os.path.join(output_dir, f"{plane}.{extension}")

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
        os.unlink(list_path)
        reporter.advance_progress(len(plane_images))

        if result.returncode != 0:
            reporter.error(
                f"Skipping plane {plane}: ffmpeg failed",
                plane=plane,
                stderr=result.stderr.strip() if result.stderr else "",
            )
            continue

        created_files.append(output_path)

    reporter.finish_step(
        f"Finished encoding videos in {output_dir}",
        created_count=len(created_files),
    )
    return created_files
