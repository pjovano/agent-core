from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from _repository import REPOSITORY_ROOT

USER_FILE_NAME = "USER.md"
IGNORE_LINE = "/USER.md"
NESTED_USER_FILE = "notes/USER.md"


def isolated_environment() -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return {**inherited, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class TrackedUserFiles:
    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root

    def paths(self) -> list[str]:
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=self._root, capture_output=True, text=True,
                                 check=True, env=isolated_environment()).stdout
        return sorted(path for path in listing.split("\0") if Path(path).name == USER_FILE_NAME)


class GitTracksNoUserFile(unittest.TestCase):
    def test_no_user_file_is_tracked_at_any_depth(self) -> None:
        self.assertEqual([], TrackedUserFiles(REPOSITORY_ROOT).paths())

    def test_gitignore_names_the_root_user_file(self) -> None:
        ignored = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(IGNORE_LINE, ignored)


class TheCheckReportsAUserFileAddedByForce(unittest.TestCase):
    def test_a_nested_user_file_added_by_force_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            self._git(root, "init", "--quiet")
            (root / NESTED_USER_FILE).parent.mkdir()
            (root / NESTED_USER_FILE).write_text("# User\n", encoding="utf-8")
            self._git(root, "add", "--force", NESTED_USER_FILE)
            self.assertEqual([NESTED_USER_FILE], TrackedUserFiles(root).paths())

    @staticmethod
    def _git(root: Path, *arguments: str) -> None:
        subprocess.run(["git", *arguments], cwd=root, capture_output=True, check=True, env=isolated_environment())


if __name__ == "__main__":
    unittest.main()
