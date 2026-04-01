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


def build_video_from_images(images, output_dir="videos", fps=12, extension="mp4"):
    os.makedirs(output_dir, exist_ok=True)

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("Could not create videos: ffmpeg is not installed or not available in PATH.")

    created_files = []
    planes = sorted(set(img.plane for img in images))
    for plane in planes:
        plane_images = sorted([img for img in images if img.plane == plane], key=lambda x: x.index)
        if not plane_images:
            continue

        output_path = os.path.join(output_dir, f"{plane}.{extension}")

        # ffmpeg concat demuxer input list.
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
            raise RuntimeError(f"Failed to create video for plane {plane}: {result.stderr.strip()}")

        created_files.append(output_path)

    return created_files
