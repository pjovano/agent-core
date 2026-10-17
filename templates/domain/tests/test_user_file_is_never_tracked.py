from __future__ import annotations

import unittest

from _repository import REPOSITORY_ROOT, TrackedFiles

USER_FILE_NAME = "USER.md"
IGNORE_LINE = "/USER.md"


class GitTracksNoUserFile(unittest.TestCase):
    def test_no_user_file_is_tracked_at_any_depth(self) -> None:
        self.assertEqual([], TrackedFiles(REPOSITORY_ROOT).named(USER_FILE_NAME))

    def test_gitignore_names_the_root_user_file(self) -> None:
        ignored = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(IGNORE_LINE, ignored)


if __name__ == "__main__":
    unittest.main()
