from __future__ import annotations

import unittest

from _repository import REPOSITORY_ROOT

IMPORT_LINES = ["@AGENTS.md", "@vendor/agent-core/SOUL.md", "@USER.md"]


class ClaudeMdImportsTheContractTheSoulAndTheUserFile(unittest.TestCase):
    def test_claude_md_holds_the_three_import_lines_in_order(self) -> None:
        lines = (REPOSITORY_ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(IMPORT_LINES, lines)

    def test_every_imported_file_but_the_user_file_exists(self) -> None:
        missing = [line for line in IMPORT_LINES[:-1] if not (REPOSITORY_ROOT / line.removeprefix("@")).is_file()]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
