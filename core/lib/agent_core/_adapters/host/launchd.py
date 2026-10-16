from __future__ import annotations

import os
import plistlib
import subprocess
from collections.abc import Callable
from pathlib import Path

from agent_core._ports.host import Job

LAUNCHCTL_TIMEOUT_SECONDS = 10
BACKGROUND_NICE = 10
PLIST_SUFFIX = ".plist"
DEFAULT_PLIST_DIRECTORY = Path.home() / "Library" / "LaunchAgents"

Runner = Callable[[list[str]], subprocess.CompletedProcess]


class LaunchdRefusal(RuntimeError):
    pass


def run_launchctl(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *arguments], capture_output=True, text=True,
                          timeout=LAUNCHCTL_TIMEOUT_SECONDS)


class LaunchdPlist:
    def __init__(self, job: Job) -> None:
        self._job = job

    def contents(self) -> bytes:
        return plistlib.dumps({**self._identity(), **self._schedule(), **self._place(), **self._priority(),
                               **self._log()})

    def _identity(self) -> dict:
        return {"Label": self._job.label, "ProgramArguments": list(self._job.command)}

    def _schedule(self) -> dict:
        job = self._job
        keys = {"StartInterval": job.interval_seconds, "KeepAlive": job.keep_alive or None,
                "RunAtLoad": job.run_at_load or None, "ThrottleInterval": job.restart_throttle_seconds}
        return {key: value for key, value in keys.items() if value is not None}

    def _place(self) -> dict:
        place = {}
        if self._job.working_directory is not None:
            place["WorkingDirectory"] = str(self._job.working_directory)
        if self._job.environment:
            place["EnvironmentVariables"] = dict(self._job.environment)
        return place

    def _priority(self) -> dict:
        if not self._job.background:
            return {}
        return {"ProcessType": "Background", "LowPriorityIO": True, "Nice": BACKGROUND_NICE}

    def _log(self) -> dict:
        if self._job.log is None:
            return {}
        return {"StandardOutPath": str(self._job.log), "StandardErrorPath": str(self._job.log)}


class LaunchAgentFile:
    def __init__(self, directory: Path, job: Job) -> None:
        self._job = job
        self._path = directory / f"{job.label}{PLIST_SUFFIX}"

    @property
    def path(self) -> Path:
        return self._path

    def contents(self) -> bytes:
        return LaunchdPlist(self._job).contents()

    def is_current(self) -> bool:
        try:
            return self._path.read_bytes() == self.contents()
        except OSError:
            return False

    def write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._job.log is not None:
            self._job.log.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(self.contents())

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)


class Launchctl:
    def __init__(self, run: Runner = run_launchctl) -> None:
        self._run = run
        self._domain = f"gui/{os.getuid()}"

    def is_loaded(self, label: str) -> bool:
        return self._run(["print", self._service(label)]).returncode == 0

    def bootout(self, label: str) -> None:
        self._run(["bootout", self._service(label)])

    def bootstrap(self, plist: Path) -> None:
        completed = self._run(["bootstrap", self._domain, str(plist)])
        if completed.returncode != 0:
            raise LaunchdRefusal(f"launchctl bootstrap {plist} failed: {completed.stderr.strip()}")

    def _service(self, label: str) -> str:
        return f"{self._domain}/{label}"


class LaunchdScheduler:
    def __init__(self, plist_directory: Path = DEFAULT_PLIST_DIRECTORY, launchctl: Launchctl | None = None) -> None:
        self._plist_directory = plist_directory
        self._launchctl = launchctl or Launchctl()

    def install(self, job: Job) -> None:
        agent = self._agent(job)
        if not agent.is_current():
            agent.write()
            self._launchctl.bootout(job.label)
        if not self._launchctl.is_loaded(job.label):
            self._launchctl.bootstrap(agent.path)

    def installed(self, job: Job) -> bool:
        return self._agent(job).is_current() and self._launchctl.is_loaded(job.label)

    def remove(self, job: Job) -> None:
        self._launchctl.bootout(job.label)
        self._agent(job).delete()

    def location(self, job: Job) -> str:
        return str(self._agent(job).path)

    def definition(self, job: Job) -> str:
        return self._agent(job).contents().decode()

    def manual_install(self, job: Job) -> str:
        return f"launchctl bootstrap gui/$(id -u) '{self._agent(job).path}'"

    def _agent(self, job: Job) -> LaunchAgentFile:
        return LaunchAgentFile(self._plist_directory, job)
