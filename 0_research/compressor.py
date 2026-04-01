from dataclasses import dataclass
import os
import re
import shutil
import subprocess
import tempfile
import json

DATA_DIR = "/media/gustavjohansson/26922D31922D0741/CFD_Data/baseline/ER26-BL-0001"
#"/LOW_RRH/images/cutplanes/cp"

FILE_MAPPING = {
    'xx': r"X(\d+)X\.png",
    'yy': r"Y(\d+)Y\.png",
    'zz': r"Z(\d+)Z\.png",
}

@dataclass
class CFDImage:
    name: str
    path: str
    plane: str
    index: int
    
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
        print("Could not create videos: ffmpeg is not installed or not available in PATH.")
        return []

    created_files = []
    planes = sorted(set(img.plane for img in images))
    for plane in planes:
        plane_images = sorted([img for img in images if img.plane == plane], key=lambda x: x.index)
        if not plane_images:
            continue

        print(f"Building video for plane {plane} with {len(plane_images)} images")
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
            print(f"Skipping plane {plane}: ffmpeg failed for {output_path}")
            if result.stderr:
                print(result.stderr.strip())
            continue

        created_files.append(output_path)

    return created_files


def find_type_of_directory(dir_path):
    type_mapping = {
        # Match filenames like X10X.png, Y5Y.png, Z120Z.png (case-insensitive via .lower()).
        "cfd_images": r"^([xyz])\d+\1\.png$",
        # Match canonical view names and isometric combinations.
        "3d_views": r"^(?:top|bottom|left|right|front|rear|rear_wing|iso_(?:left|right)_(?:front|rear)_(?:top|bottom))\.png$",
    }

    files = [f for f in os.scandir(dir_path) if f.is_file()]
    lowered_files = [f.name.lower() for f in files]

    for dir_type, pattern in type_mapping.items():
        matching = [f for f in lowered_files if re.match(pattern, f)]
        if matching:
            return {"type": dir_type, "count": len(matching)}

    return {"type": "unknown", "count": 0}
    

def build_structure(base_dir):
    structure = {}
    subfolders = [ f.path for f in os.scandir(base_dir) if f.is_dir() ]
    if not subfolders:
        return find_type_of_directory(base_dir)
    for subfolder in subfolders:
        structure[subfolder.split(os.sep)[-1]] = build_structure(subfolder)
    return structure

def test():
    cfd_images = find_cfd_images(DATA_DIR)
    nr_of_images = len(cfd_images)
    print(f"Found {nr_of_images} CFD images in {DATA_DIR}")
    
    for plane in FILE_MAPPING.keys():
        plane_images = [img for img in cfd_images if img.plane == plane]
        print(f"Plane {plane}: {len(plane_images)} images")

    created_videos = build_video_from_images(cfd_images, output_dir=os.path.join(os.path.dirname(__file__), "videos"), fps=12, extension="mp4")
    if created_videos:
        print("Created video files:")
        for video_path in created_videos:
            print(f"  - {video_path}")
    else:
        print("No videos were created.")


if __name__ == "__main__":
    with open(os.path.join(os.path.dirname(__file__), "output.json"), "w") as f:    
        json.dump(build_structure(DATA_DIR), f, indent=2)