from __future__ import annotations

import subprocess
from dataclasses import dataclass

from _core_path import CoreModulePath

CoreModulePath.activate()

from agent_core._ports.host import Job, Level, Notice

LOADED = 0
NOT_LOADED = 113
REFUSED = 5
PLIST_SUFFIX = ".plist"


@dataclass(frozen=True)
class FakeNotice:
    message: str


class FakeScheduler:
    def __init__(self) -> None:
        self._installed: set[str] = set()

    def install(self, job: Job) -> None:
        self._installed.add(job.label)

    def installed(self, job: Job) -> bool:
        return job.label in self._installed

    def remove(self, job: Job) -> None:
        self._installed.discard(job.label)

    def definition(self, job: Job) -> str:
        return repr(job)

    def manual_install(self, job: Job) -> str:
        return f"install {job.label}"


class FakeSystemReadings:
    def __init__(self, memory: Level | None = Level.NORMAL, thermal: Level | None = Level.NORMAL,
                 swap_bytes: int | None = 0) -> None:
        self._memory = memory
        self._thermal = thermal
        self._swap_bytes = swap_bytes

    def memory_pressure(self) -> Level | None:
        return self._memory

    def thermal(self) -> Level | None:
        return self._thermal

    def swap_used(self) -> int | None:
        return self._swap_bytes


class RecordingNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, alert: Notice) -> None:
        self.messages.append(alert.message)


class FakeLaunchctl:
    def __init__(self, loaded: tuple[str, ...] = (), bootstrap_refused: bool = False) -> None:
        self.loaded = set(loaded)
        self.calls: list[list[str]] = []
        self._bootstrap_refused = bootstrap_refused
        self._verbs = {"print": self._print, "bootout": self._bootout, "bootstrap": self._bootstrap}

    def run(self, arguments: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(arguments)
        verb, target = arguments[0], arguments[-1]
        return subprocess.CompletedProcess(arguments, self._verbs[verb](target), "", "refused")

    def verbs(self) -> list[str]:
        return [call[0] for call in self.calls]

    def addressed(self) -> list[str]:
        return [argument for call in self.calls for argument in call[1:]]

    def _print(self, service: str) -> int:
        return LOADED if self._label(service) in self.loaded else NOT_LOADED

    def _bootout(self, service: str) -> int:
        label = self._label(service)
        if label not in self.loaded:
            return NOT_LOADED
        self.loaded.discard(label)
        return LOADED

    def _bootstrap(self, plist: str) -> int:
        if self._bootstrap_refused:
            return REFUSED
        self.loaded.add(self._label(plist).removesuffix(PLIST_SUFFIX))
        return LOADED

    @staticmethod
    def _label(target: str) -> str:
        return target.rsplit("/", 1)[-1]


class FixedSource:
    def __init__(self, value: object) -> None:
        self._value = value

    def raw(self) -> object:
        return self._value

    def used_bytes(self) -> object:
        return self._value


class RecordingRunner:
    def __init__(self, failure: Exception | None = None) -> None:
        self.commands: list[list[str]] = []
        self._failure = failure

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess:
        self.commands.append(command)
        if self._failure is not None:
            raise self._failure
        return subprocess.CompletedProcess(command, 0, "", "")
