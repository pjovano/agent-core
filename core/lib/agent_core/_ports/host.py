from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class Level(enum.Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    SERIOUS = "serious"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Job:
    label: str
    command: tuple[str, ...]
    interval_seconds: int | None = None
    keep_alive: bool = False
    working_directory: Path | None = None
    run_at_load: bool = False
    restart_throttle_seconds: int | None = None
    environment: tuple[tuple[str, str], ...] = ()
    log: Path | None = None
    background: bool = False


@dataclass(frozen=True)
class NoticeHeading:
    title: str
    reminder_list: str


class Notice(Protocol):
    @property
    def message(self) -> str: ...


class Scheduler(Protocol):
    def install(self, job: Job) -> None: ...

    def installed(self, job: Job) -> bool: ...

    def remove(self, job: Job) -> None: ...

    def definition(self, job: Job) -> str: ...

    def manual_install(self, job: Job) -> str: ...


class Notifier(Protocol):
    def notify(self, alert: Notice) -> None: ...


class SystemReadings(Protocol):
    def memory_pressure(self) -> Level | None: ...

    def thermal(self) -> Level | None: ...

    def swap_used(self) -> int | None: ...
