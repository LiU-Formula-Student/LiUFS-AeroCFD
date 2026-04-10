from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console
    from rich.progress import Progress


@dataclass
class ProgressEvent:
    kind: str
    message: str
    data: dict[str, Any] | None = None


class LogLevel(Enum):
    INFO = 1
    WARNING = 2
    ERROR = 3


class BaseReporter:
    def emit(self, event: ProgressEvent) -> None:
        pass

    def close(self) -> None:
        pass

    def log(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="log", message=message, data=data or None))

    def warn(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="warn", message=message, data=data or None))

    def error(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="error", message=message, data=data or None))

    def start_step(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="start_step", message=message, data=data or None))

    def finish_step(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="finish_step", message=message, data=data or None))

    def advance(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="advance", message=message, data=data or None))

    def set_total(self, total: int, description: str = "Processing images", **data: Any) -> None:
        payload = {"total": max(0, int(total)), "description": description}
        payload.update(data)
        self.emit(ProgressEvent(kind="progress_total", message=description, data=payload))

    def advance_progress(self, amount: int = 1, message: str | None = None, **data: Any) -> None:
        payload = {"amount": max(0, int(amount))}
        payload.update(data)
        self.emit(ProgressEvent(kind="progress_advance", message=message or "", data=payload))

    def complete_progress(self, message: str = "Image processing complete", **data: Any) -> None:
        self.emit(ProgressEvent(kind="progress_complete", message=message, data=data or None))


class NullReporter(BaseReporter):
    pass


class RichReporter(BaseReporter):
    def __init__(self, console: Console | None = None, loglevel: LogLevel = LogLevel.INFO) -> None:
        if console is None:
            try:
                from rich.console import Console as RichConsole
            except ModuleNotFoundError as exc:
                raise ModuleNotFoundError(
                    "RichReporter requires the optional dependency 'rich'. Install with: pip install \"aerocfd[cli]\""
                ) from exc
            self.console = RichConsole()
        else:
            self.console = console
        self.loglevel = loglevel
        self._progress: Progress | None = None
        self._task_id: int | None = None
        self._task_total = 0
        self._completed_attempts = 0

    def _ensure_progress(self) -> Progress:
        if self._progress is None:
            from rich.progress import (
                BarColumn,
                Progress,
                SpinnerColumn,
                TaskProgressColumn,
                TextColumn,
                TimeRemainingColumn,
            )
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(bar_width=None),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=self.console,
                transient=False,
            )
            self._progress.start()
        return self._progress

    def close(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task_id = None
            self._task_total = 0

    def emit(self, event: ProgressEvent) -> None:
        if event.kind == "log" and self.loglevel.value <= LogLevel.INFO.value:
            self.console.log(event.message)
        elif event.kind == "warn" and self.loglevel.value <= LogLevel.WARNING.value:
            self.console.log(f"[bold yellow]{event.message}[/]")
        elif event.kind == "error" and self.loglevel.value <= LogLevel.ERROR.value:
            self.console.log(f"[bold red]{event.message}[/]")
        elif event.kind == "start_step":
            self.console.log(f"[bold dark_orange]{event.message}[/]")
        elif event.kind == "finish_step":
            self.console.log(f"[bold green]{event.message}[/]")
        elif event.kind == "advance":
            self.console.log(event.message)
        elif event.kind == "progress_total":
            data = event.data or {}
            total = max(0, int(data.get("total", 0)))
            description = str(data.get("description") or event.message or "Processing images")
            self._completed_attempts = 0
            self._task_total = total

            if total > 0:
                progress = self._ensure_progress()
                if self._task_id is None:
                    self._task_id = progress.add_task(description, total=total, completed=0)
                else:
                    progress.update(self._task_id, description=description, total=total, completed=0)
            else:
                if self._progress is not None:
                    self._progress.stop()
                    self._progress = None
                self._task_id = None
            if total == 0 and self.loglevel.value <= LogLevel.INFO.value:
                self.console.log("No image files found to process.")
        elif event.kind == "progress_advance":
            if self._progress is None or self._task_id is None:
                return
            data = event.data or {}
            amount = max(0, int(data.get("amount", 1)))
            self._completed_attempts += amount
            next_completed = min(self._completed_attempts, max(self._task_total, 1))
            self._progress.update(self._task_id, completed=next_completed)
            if event.message and self.loglevel.value <= LogLevel.INFO.value:
                self.console.log(event.message)
        elif event.kind == "progress_complete":
            if self._progress is not None and self._task_id is not None:
                self._progress.update(self._task_id, completed=max(self._task_total, 1))
                self._progress.refresh()
            if event.message and self.loglevel.value <= LogLevel.INFO.value:
                self.console.log(f"[bold green]{event.message}[/]")
        else:
            self.console.log(event.message)
