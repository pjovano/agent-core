from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core" / "lib"))
from agent_core._adapters.host.launchd import LaunchdScheduler
from agent_core._ports.host import Job, Scheduler

LABEL = "com.agent-core.remote-control"
KEEP_AWAKE = "caffeinate"
KEEP_AWAKE_WHILE_RUNNING = "-i"
CLAUDE = "claude"
HOMEBREW = "brew"
REMOTE_CONTROL_ARGUMENTS = ("remote-control", "--spawn", "same-dir", "--no-create-session-in-dir")
RESTART_THROTTLE_SECONDS = 30
LAUNCHD_DEFAULT_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
PATH_SEPARATOR = ":"
USAGE_EXIT_CODE = 2
REFUSED_EXIT_CODE = 1

Which = Callable[[str], str | None]


class RemoteControlJob:
    def __init__(self, home: Path, which: Which = shutil.which) -> None:
        self._home = home
        self._which = which

    def job(self) -> Job:
        claude = self._program(CLAUDE)
        command = (self._program(KEEP_AWAKE), KEEP_AWAKE_WHILE_RUNNING, claude, *REMOTE_CONTROL_ARGUMENTS)
        return Job(LABEL, command, keep_alive=True, working_directory=self._home / "Developer" / "agent-core",
                   run_at_load=True, restart_throttle_seconds=RESTART_THROTTLE_SECONDS,
                   environment=(("PATH", self._search_path(claude)),),
                   log=self._home / "Library" / "Logs" / f"{LABEL}.log")

    def unresolved(self) -> list[str]:
        return [program for program in (KEEP_AWAKE, CLAUDE) if self._which(program) is None]

    def _program(self, name: str) -> str:
        return self._which(name) or name

    def _search_path(self, claude: str) -> str:
        homebrew = self._which(HOMEBREW)
        directories = [str(Path(claude).parent)] + ([str(Path(homebrew).parent)] if homebrew else [])
        return PATH_SEPARATOR.join(dict.fromkeys([*directories, *LAUNCHD_DEFAULT_PATH]))


class RemoteControlCli:
    def __init__(self, job: RemoteControlJob, scheduler: Scheduler) -> None:
        self._job = job
        self._scheduler = scheduler

    def run(self, argv: list[str]) -> int:
        parser = self._parser()
        if not argv:
            parser.print_help()
            return USAGE_EXIT_CODE
        arguments = parser.parse_args(argv)
        return arguments.run(arguments)

    def _install(self, arguments: argparse.Namespace) -> int:
        job, unresolved = self._job.job(), self._job.unresolved()
        needed = not self._scheduler.installed(job)
        wanted = arguments.apply and needed
        applied = wanted and not unresolved
        if applied:
            self._scheduler.install(job)
        self._print({"label": job.label, "needed": needed, "installed": applied, "unresolved": unresolved,
                     "definition": self._scheduler.definition(job), "manual": self._scheduler.manual_install(job)})
        return REFUSED_EXIT_CODE if wanted and unresolved else 0

    def _uninstall(self, arguments: argparse.Namespace) -> int:
        job = self._job.job()
        installed = self._scheduler.installed(job)
        if arguments.apply:
            self._scheduler.remove(job)
        self._print({"label": job.label, "installed": installed, "removed": arguments.apply})
        return 0

    def _status(self, _arguments: argparse.Namespace) -> int:
        job = self._job.job()
        self._print({"label": job.label, "installed": self._scheduler.installed(job),
                     "unresolved": self._job.unresolved()})
        return 0

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="remote_control.py")
        commands = parser.add_subparsers()
        for name, run in (("install", self._install), ("uninstall", self._uninstall)):
            command = commands.add_parser(name)
            command.add_argument("--apply", action="store_true")
            command.set_defaults(run=run)
        commands.add_parser("status").set_defaults(run=self._status)
        return parser

    @staticmethod
    def _print(report: dict) -> None:
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(RemoteControlCli(RemoteControlJob(Path.home()), LaunchdScheduler()).run(sys.argv[1:]))
