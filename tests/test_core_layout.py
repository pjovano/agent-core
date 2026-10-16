from __future__ import annotations

import unittest

from _repository import REPOSITORY_ROOT

CORE_DIR = REPOSITORY_ROOT / "core"
CORE_DIRECTORIES = ("skills", "agents", "workflows", "audit", "lib", "templates/domain")
CORE_FILES = ("SOUL.md", "domain.py")


class CoreHoldsEveryPartOfItsLayout(unittest.TestCase):
    def test_every_core_directory_exists(self) -> None:
        missing = [part for part in CORE_DIRECTORIES if not (CORE_DIR / part).is_dir()]
        self.assertEqual([], missing)

    def test_every_core_file_exists(self) -> None:
        missing = [part for part in CORE_FILES if not (CORE_DIR / part).is_file()]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
