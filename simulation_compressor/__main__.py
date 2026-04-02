from __future__ import annotations

import argparse
from pathlib import Path
import sys
from rich.console import Console

from .reporting import RichReporter
from .packager import DuplicateRunError, append_run_to_liufs, build_liufs


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aerocfd",
        description="Build or extend a .liufs archive from a CFD simulation directory.",
    )
    parser.add_argument(
        "source",
        help="Path to the simulation directory to package.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output .liufs file path. Defaults to <source>.liufs, or overwrites --append-to when used.",
    )
    parser.add_argument(
        "--append-to",
        help="Existing .liufs archive to extend with the source directory as a new run.",
    )
    parser.add_argument(
        "--run-name",
        help="Override the run name used when appending to an existing .liufs archive.",
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
        "--webp-quality",
        type=int,
        default=80,
        help="WebP quality for 3d view image compression (0-100). Default: 80.",
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
    output = Path(args.output).expanduser() if args.output else None
    append_to = Path(args.append_to).expanduser() if args.append_to else None

    if append_to and not append_to.exists():
        parser.error(f"Target archive does not exist: {append_to}")


    if not source.exists():
        parser.error(f"Source path does not exist: {source}")

    if not source.is_dir():
        parser.error(f"Source path is not a directory: {source}")

    if args.fps <= 0:
        parser.error("--fps must be greater than 0")

    if args.webp_quality < 0 or args.webp_quality > 100:
        parser.error("--webp-quality must be between 0 and 100")

    reporter = None
    try:
        console = Console()
        reporter = RichReporter(console)
        if append_to:
            result = append_run_to_liufs(
                source_dir=source,
                archive_file=append_to,
                output_file=output,
                run_name=args.run_name,
                fps=args.fps,
                extension=args.extension,
                webp_quality=args.webp_quality,
                include_unknown=args.include_unknown,
                reporter=reporter,
            )
        else:
            result = build_liufs(
                source_dir=source,
                output_file=output,
                fps=args.fps,
                extension=args.extension,
                webp_quality=args.webp_quality,
                include_unknown=args.include_unknown,
                reporter=reporter,
            )
    except DuplicateRunError as exc:
        print(f"Failed to extend .liufs archive: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        action = "extend" if append_to else "build"
        print(f"Failed to {action} .liufs archive: {exc}", file=sys.stderr)
        return 1
    finally:
        if reporter is not None:
            reporter.close()

    print(f"Created archive: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())