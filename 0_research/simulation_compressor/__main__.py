from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from .packager import build_liufs


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liufs-compressor",
        description="Build a .liufs archive from a CFD simulation directory.",
    )
    parser.add_argument(
        "source",
        help="Path to the simulation directory to package.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output .liufs file path. Defaults to <source>.liufs.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=12,
        help="Frames per second for generated videos. Default: 12.",
    )
    parser.add_argument(
        "--extension",
        default="mp4",
        help="Video file extension to use inside the archive. Default: mp4.",
    )
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="Copy files from directories with unknown type into the archive.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser()
    if args.output:
        output = Path(args.output).expanduser() 
    else:
        output = args.source.split(os.sep)[-1] + ".liufs" if os.sep in str(source) else source.with_suffix(".liufs")


    if not source.exists():
        parser.error(f"Source path does not exist: {source}")

    if not source.is_dir():
        parser.error(f"Source path is not a directory: {source}")

    if args.fps <= 0:
        parser.error("--fps must be greater than 0")

    try:
        result = build_liufs(
            source_dir=source,
            output_file=output,
            fps=args.fps,
            extension=args.extension,
            include_unknown=args.include_unknown,
        )
    except Exception as exc:
        print(f"Failed to build .liufs archive: {exc}", file=sys.stderr)
        return 1

    print(f"Created archive: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())