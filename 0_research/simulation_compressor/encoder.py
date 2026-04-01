from .reporting import NullReporter
from . import FILE_MAPPING, CFDImage
import re
import os
import shutil
import subprocess
import tempfile


def find_cfd_images(data_dir):
    images = []
    for plane, pattern in FILE_MAPPING.items():
        for filename in os.listdir(data_dir):
            match = re.match(pattern, filename)
            if match:
                index = int(match.group(1))  # Extract the captured number
                images.append(CFDImage(name=filename, path=os.path.join(data_dir, filename), plane=plane, index=index))
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
