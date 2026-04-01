from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import Console


@dataclass
class ProgressEvent:
    kind: str
    message: str
    data: dict[str, Any] | None = None


class BaseReporter:
    def emit(self, event: ProgressEvent) -> None:
        pass

    def log(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="log", message=message, data=data or None))

    def start_step(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="start_step", message=message, data=data or None))

    def finish_step(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="finish_step", message=message, data=data or None))

    def advance(self, message: str, **data: Any) -> None:
        self.emit(ProgressEvent(kind="advance", message=message, data=data or None))


class NullReporter(BaseReporter):
    pass


class RichReporter(BaseReporter):
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def emit(self, event: ProgressEvent) -> None:
        if event.kind == "start_step":
            self.console.log(f"[bold dark_orange]{event.message}[/]")
        elif event.kind == "finish_step":
            self.console.log(f"[bold green]{event.message}[/]")
        elif event.kind == "advance":
            self.console.log(event.message)
        else:
            self.console.log(event.message)