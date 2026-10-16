from __future__ import annotations

import unittest

from _repository import REPOSITORY_ROOT, TrackedLinks

CLAUDE_LINKS = TrackedLinks(REPOSITORY_ROOT, ".claude")
CORE_DIR = REPOSITORY_ROOT / "core"


class EveryLinkUnderClaudeResolvesIntoCore(unittest.TestCase):
    def test_the_root_links_at_least_one_core_unit(self) -> None:
        self.assertTrue(CLAUDE_LINKS.paths())

    def test_every_link_is_relative(self) -> None:
        self.assertEqual([], CLAUDE_LINKS.absolute())

    def test_every_link_resolves_to_an_existing_path_inside_core(self) -> None:
        self.assertEqual([], CLAUDE_LINKS.outside(CORE_DIR))


if __name__ == "__main__":
    unittest.main()
