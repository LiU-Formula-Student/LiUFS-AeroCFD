from __future__ import annotations

import argparse
from pathlib import Path
import sys
from rich.console import Console

from .reporting import LogLevel, RichReporter
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
        "--workers",
        type=int,
        default=None,
        help="Number of worker threads for WebP and per-plane video processing. Default: auto.",
    )
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="Copy files from directories with unknown type into the archive.",
    )
    parser.add_argument(
        "--log-level",
        choices=("info", "warning", "error"),
        default="info",
        help="Minimum log level to print for event logs. Default: info.",
    )
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--quiet",
        action="store_true",
        help="Disable all terminal output, including progress and errors.",
    )
    output_mode.add_argument(
        "--progress-only",
        action="store_true",
        help="Show only progress/ETA bar and suppress event log lines.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    def fail_validation(message: str) -> int:
        if not args.quiet:
            print(f"aerocfd: error: {message}", file=sys.stderr)
        return 2

    source = Path(args.source).expanduser()
    output = Path(args.output).expanduser() if args.output else None
    append_to = Path(args.append_to).expanduser() if args.append_to else None

    if append_to and not append_to.exists():
        return fail_validation(f"Target archive does not exist: {append_to}")


    if not source.exists():
        return fail_validation(f"Source path does not exist: {source}")

    if not source.is_dir():
        return fail_validation(f"Source path is not a directory: {source}")

    if args.fps <= 0:
        return fail_validation("--fps must be greater than 0")

    if args.webp_quality < 0 or args.webp_quality > 100:
        return fail_validation("--webp-quality must be between 0 and 100")

    if args.workers is not None and args.workers <= 0:
        return fail_validation("--workers must be greater than 0")

    reporter = None
    if args.log_level == "warning":
        loglevel = LogLevel.WARNING
    elif args.log_level == "error":
        loglevel = LogLevel.ERROR
    else:
        loglevel = LogLevel.INFO

    show_logs = not args.progress_only and not args.quiet
    show_progress = not args.quiet

    try:
        console = Console(quiet=args.quiet)
        reporter = RichReporter(
            console,
            loglevel=loglevel,
            show_logs=show_logs,
            show_progress=show_progress,
        )
        if append_to:
            result = append_run_to_liufs(
                source_dir=source,
                archive_file=append_to,
                output_file=output,
                run_name=args.run_name,
                fps=args.fps,
                extension=args.extension,
                webp_quality=args.webp_quality,
                workers=args.workers,
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
                workers=args.workers,
                include_unknown=args.include_unknown,
                reporter=reporter,
            )
    except DuplicateRunError as exc:
        if not args.quiet:
            print(f"Failed to extend .liufs archive: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        action = "extend" if append_to else "build"
        if not args.quiet:
            print(f"Failed to {action} .liufs archive: {exc}", file=sys.stderr)
        return 1
    finally:
        if reporter is not None:
            reporter.close()

    if not args.quiet:
        print(f"Created archive: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())