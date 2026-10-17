from __future__ import annotations

import os
import unittest

from _repository import REPOSITORY_ROOT, VENDORED_CORE, TrackedFiles

CONTRACT_NAMES = ("AGENTS.md", "CLAUDE.md")


class EveryCoreLinkResolvesIntoTheVendoredCore(unittest.TestCase):
    def setUp(self) -> None:
        self.links = TrackedFiles(REPOSITORY_ROOT).links_under(".claude")

    def test_the_domain_links_at_least_one_core_unit(self) -> None:
        self.assertTrue(self.links)

    def test_every_link_is_relative(self) -> None:
        self.assertEqual([], [str(link) for link in self.links if os.path.isabs(os.readlink(link))])

    def test_every_link_resolves_to_an_existing_path_inside_the_vendored_core(self) -> None:
        boundary = VENDORED_CORE.resolve()
        outside = [str(link) for link in self.links
                   if not (link.resolve().exists() and link.resolve().is_relative_to(boundary))]
        self.assertEqual([], outside)


class TheVendoredCoreCarriesNoContract(unittest.TestCase):
    def test_no_contract_file_sits_at_any_depth_of_the_vendored_core(self) -> None:
        found = [str(path) for name in CONTRACT_NAMES for path in VENDORED_CORE.rglob(name)]
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
