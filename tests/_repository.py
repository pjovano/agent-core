from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SYMLINK_MODE = "120000"


class TrackedLinks:
    def __init__(self, repository_root: Path, directory: str) -> None:
        self._root = repository_root
        self._directory = directory

    def paths(self) -> list[Path]:
        listing = subprocess.run(["git", "ls-files", "--stage", "--", self._directory], cwd=self._root,
                                 capture_output=True, text=True, check=True).stdout
        return [self._root / line.split("\t", 1)[1] for line in listing.splitlines()
                if line.startswith(SYMLINK_MODE)]

    def absolute(self) -> list[str]:
        return [self._label(path) for path in self.paths() if os.path.isabs(os.readlink(path))]

    def outside(self, target_directory: Path) -> list[str]:
        boundary = target_directory.resolve()
        return [self._label(path) for path in self.paths() if not self._lands_inside(path, boundary)]

    def _lands_inside(self, path: Path, boundary: Path) -> bool:
        target = path.resolve()
        return target.exists() and target.is_relative_to(boundary)

    def _label(self, path: Path) -> str:
        return f"{path.relative_to(self._root).as_posix()} -> {os.readlink(path)}"
