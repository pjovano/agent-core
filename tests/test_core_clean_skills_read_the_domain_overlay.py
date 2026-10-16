from __future__ import annotations

import re
import unittest

from _repository import REPOSITORY_ROOT

SKILLS_DIR = REPOSITORY_ROOT / "core" / "skills"
OVERLAY_OF_SKILL = {"clean-code": ".claude/code-overlay.md", "clean-prose": ".claude/glossary.md"}
OVERRIDE_CLAUSE = re.compile(r"If a rule of the (code overlay|glossary) contradicts a rule of this file, "
                             r"the (code overlay|glossary)'s rule wins\.")
DOMAIN_TERMS = ("vault", "pdf", "zotero", "corpus", "research", "obsidian", "folio", "bibliograph")
WHITESPACE_RUN = re.compile(r"\s+")
WORD = re.compile(r"[a-z]+")
VOCABULARY_ROW = re.compile(r"^\| ([^|]+?) \|", re.MULTILINE)
TERMS_THE_SKILLS_NAME = ("domain", "code overlay", "glossary", "domain content")


class CleanSkill:
    def __init__(self, name: str) -> None:
        self._raw = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        self._text = WHITESPACE_RUN.sub(" ", self._raw)

    def names(self, path: str) -> bool:
        return f"`{path}`" in self._text

    def states_that_the_overlay_wins(self) -> bool:
        return OVERRIDE_CLAUSE.search(self._text) is not None

    def vocabulary_terms(self) -> set[str]:
        return set(VOCABULARY_ROW.findall(self._raw))

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


class TheVocabularyDefinesEveryTermTheCleanSkillsName(unittest.TestCase):
    def test_the_vocabulary_has_a_row_for_the_domain_its_overlays_and_its_content(self) -> None:
        undefined = sorted(set(TERMS_THE_SKILLS_NAME) - CleanSkill("clean-prose").vocabulary_terms())
        self.assertEqual([], undefined)


class NoCleanSkillNamesADomainTerm(unittest.TestCase):
    def test_no_skill_names_a_term_of_the_research_domain(self) -> None:
        found = {name: CleanSkill(name).domain_terms() for name in OVERLAY_OF_SKILL}
        self.assertEqual({name: [] for name in OVERLAY_OF_SKILL}, found)


if __name__ == "__main__":
    unittest.main()
