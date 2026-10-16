from __future__ import annotations

import re
import unittest

from _repository import REPOSITORY_ROOT

SKILLS_DIR = REPOSITORY_ROOT / "core" / "skills"
OVERLAY_OF_SKILL = {"clean-code": ".claude/code-overlay.md", "clean-prose": ".claude/glossary.md"}
OVERRIDE_CLAUSE = re.compile(r"If a rule of the (overlay|glossary) contradicts a rule of this file, "
                             r"the (overlay|glossary)'s rule wins\.")
DOMAIN_TERMS = ("vault", "pdf", "zotero", "corpus", "research", "obsidian", "folio", "bibliograph")
WHITESPACE_RUN = re.compile(r"\s+")
WORD = re.compile(r"[a-z]+")


class CleanSkill:
    def __init__(self, name: str) -> None:
        self._text = WHITESPACE_RUN.sub(" ", (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8"))

    def names(self, path: str) -> bool:
        return f"`{path}`" in self._text

    def states_that_the_overlay_wins(self) -> bool:
        return OVERRIDE_CLAUSE.search(self._text) is not None

    def domain_terms(self) -> list[str]:
        words = set(WORD.findall(self._text.lower()))
        return sorted(term for term in DOMAIN_TERMS if any(word.startswith(term) for word in words))


class EachCleanSkillReadsItsDomainOverlay(unittest.TestCase):
    def test_each_skill_names_its_overlay_path(self) -> None:
        unnamed = [name for name, path in OVERLAY_OF_SKILL.items() if not CleanSkill(name).names(path)]
        self.assertEqual([], unnamed)

    def test_each_skill_lets_an_overlay_rule_override_its_own(self) -> None:
        silent = [name for name in OVERLAY_OF_SKILL if not CleanSkill(name).states_that_the_overlay_wins()]
        self.assertEqual([], silent)


class NoCleanSkillNamesADomainTerm(unittest.TestCase):
    def test_no_skill_names_a_term_of_the_research_domain(self) -> None:
        found = {name: CleanSkill(name).domain_terms() for name in OVERLAY_OF_SKILL}
        self.assertEqual({name: [] for name in OVERLAY_OF_SKILL}, found)


if __name__ == "__main__":
    unittest.main()
