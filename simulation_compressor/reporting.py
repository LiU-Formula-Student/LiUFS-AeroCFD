from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Console


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


class NullReporter(BaseReporter):
    pass


class RichReporter(BaseReporter):
    def __init__(self, console: Console | None = None, loglevel: LogLevel = LogLevel.INFO) -> None:
        self.console = console or Console()
        self.loglevel = loglevel

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
        else:
            self.console.log(event.message)