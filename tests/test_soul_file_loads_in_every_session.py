from __future__ import annotations

import re
import unittest

from _repository import REPOSITORY_ROOT

SOUL_FILE = REPOSITORY_ROOT / "core" / "SOUL.md"
CLAUDE_FILE = REPOSITORY_ROOT / "CLAUDE.md"
MAX_SOUL_LINES = 60
DISPATCHER_IMPORTS = ["@AGENTS.md", "@core/SOUL.md"]
USER_FILE_NAME = "USER.md"
DOMAIN_TERMS = ("vault", "pdf", "zotero", "corpus", "research", "obsidian", "folio", "bibliograph")
WORD = re.compile(r"[a-z]+")


class TheSoulFileStaysGenericAndWithinItsCap(unittest.TestCase):
    def test_the_soul_file_holds_at_most_sixty_lines(self) -> None:
        self.assertLessEqual(len(SOUL_FILE.read_text(encoding="utf-8").splitlines()), MAX_SOUL_LINES)

    def test_the_soul_file_names_no_term_of_the_research_domain(self) -> None:
        words = set(WORD.findall(SOUL_FILE.read_text(encoding="utf-8").lower()))
        self.assertEqual([], sorted(term for term in DOMAIN_TERMS if any(word.startswith(term) for word in words)))


class TheDispatcherImportsTheSoulFileAndNoUserFile(unittest.TestCase):
    def test_claude_md_imports_the_contract_then_the_soul_file(self) -> None:
        self.assertEqual(DISPATCHER_IMPORTS, CLAUDE_FILE.read_text(encoding="utf-8").splitlines())

    def test_claude_md_names_no_user_file(self) -> None:
        self.assertNotIn(USER_FILE_NAME, CLAUDE_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
