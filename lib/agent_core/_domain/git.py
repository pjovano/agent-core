from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class Git:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def run(self, *arguments: str) -> str:
        completed = self._completed(arguments)
        if completed.returncode != 0:
            raise GitError(f"git {' '.join(arguments)} failed in {self._directory}: {completed.stderr.strip()}")
        return completed.stdout.strip()

    def succeeds(self, *arguments: str) -> bool:
        return self._completed(arguments).returncode == 0

    def _completed(self, arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *arguments], cwd=self._directory, capture_output=True, text=True)
