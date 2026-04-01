import re
import os

from .reporting import NullReporter, BaseReporter


def find_type_of_directory(dir_path, reporter: BaseReporter | None = None):
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
            reporter.log(f"Directory '{dir_path}' identified as '{dir_type}' with {len(matching)} matching files.")
            return {
                "type": dir_type,
                "count": len(matching),
                "path": str(dir_path)
            }
    reporter.warn(f"Directory '{dir_path}' does not match known types, found {len(files)} files.")
    return {
        "type": "unknown",
        "count": 0,
        "path": str(dir_path)
    }


def build_structure(base_dir, reporter: BaseReporter | None = None):
    reporter = reporter or NullReporter()
    structure = {}
    subfolders = [ f.path for f in os.scandir(base_dir) if f.is_dir() ]
    if not subfolders:
        return find_type_of_directory(base_dir, reporter=reporter)
    for subfolder in subfolders:
        structure[subfolder.split(os.sep)[-1]] = build_structure(subfolder, reporter=reporter)
    return structure
