from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
VENDORED_CORE = REPOSITORY_ROOT / "vendor" / "agent-core"
SYMLINK_MODE = "120000"


def isolated_environment() -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return {**inherited, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class TrackedFiles:
    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root

    def named(self, file_name: str) -> list[str]:
        return sorted(path for path in self._listing("-z").split("\0") if Path(path).name == file_name)

    def links_under(self, directory: str) -> list[Path]:
        lines = self._listing("--stage", "--", directory).splitlines()
        return [self._root / line.split("\t", 1)[1] for line in lines if line.startswith(SYMLINK_MODE)]

    def _listing(self, *arguments: str) -> str:
        return subprocess.run(["git", "ls-files", *arguments], cwd=self._root, capture_output=True, text=True,
                              check=True, env=isolated_environment()).stdout
