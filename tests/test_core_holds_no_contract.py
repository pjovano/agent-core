from __future__ import annotations

import unittest

from _repository import REPOSITORY_ROOT

CORE_DIR = REPOSITORY_ROOT / "core"
CONTRACT_NAMES = ("AGENTS.md", "CLAUDE.md")


class CoreHoldsNoContract(unittest.TestCase):
    def test_core_exists(self) -> None:
        self.assertTrue(CORE_DIR.is_dir())

    def test_no_contract_file_sits_at_any_depth_of_core(self) -> None:
        found = sorted(path.relative_to(REPOSITORY_ROOT).as_posix()
                       for name in CONTRACT_NAMES for path in CORE_DIR.rglob(name))
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
