from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class Git:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def run(self, *arguments: str) -> str:
        try:
            return self._completed(arguments).stdout.strip()
        except subprocess.CalledProcessError as error:
            raise GitError(f"git {' '.join(arguments)} failed in {self._directory}: {error.stderr.strip()}") from error

    def _completed(self, arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *arguments], cwd=self._directory, capture_output=True, text=True, check=True)
