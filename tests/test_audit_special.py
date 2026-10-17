from __future__ import annotations

import unittest

from _audit_files import AuditRun
from _git_files import DEFECT, FEATURE, REFACTOR, GitFiles, message

from agent_core._audit.special import RULE_CONSTANT, RULE_ENUMERATION, RULE_LITERAL, RULE_TRAILER

CONTRACT = {"AGENTS.md": "# Contract\n"}
BASELINE = {"audit/baseline.json": "{}\n"}
LIMITS = "MAX_NAME_LENGTH = 80\nKINDS = (\"book\", \"article\")\n"
PINNING_TEST = "from limits import MAX_NAME_LENGTH\n\n\ndef test_the_limit():\n    assert MAX_NAME_LENGTH\n"
LITERAL = "def skipped(path):\n    return path.name == \"annual-report-2024.md\"\n"
TYPED = "def is_note(path):\n    return path.suffix == \".md\" or path.stem == \"index\"\n"


class SpecialRepository:
    def __init__(self, case: unittest.TestCase) -> None:
        self.git = GitFiles(case)
        self.git.committed(message("Add the contract", FEATURE), CONTRACT)

    def rows(self) -> list[dict]:
        return AuditRun(self.git.root).payload("lint")["special"]

    def rules(self) -> list[str]:
        return [row["rule"] for row in self.rows()]


class TestSignSixCommitTrailers(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SpecialRepository(self)

    def test_a_commit_with_neither_trailer_is_a_row_naming_the_commit(self) -> None:
        sha = self.repository.git.committed("Reword the contract", {"AGENTS.md": "# The contract\n"})
        self.assertEqual([(RULE_TRAILER, sha)], [(row["rule"], row["file"]) for row in self.repository.rows()])

    def test_a_defect_class_trailer_passes(self) -> None:
        self.repository.git.committed(message("Fix the contract", DEFECT), {"AGENTS.md": "# Fixed\n"})
        self.assertEqual([], self.repository.rules())

    def test_a_refactor_change_class_trailer_passes(self) -> None:
        self.repository.git.committed(message("Move the contract", REFACTOR), {"AGENTS.md": "# Moved\n"})
        self.assertEqual([], self.repository.rules())

    def test_a_change_class_without_its_kind_and_what_is_a_row(self) -> None:
        self.repository.git.committed(message("Change it", "Change-class: tweak"), {"AGENTS.md": "# Tweaked\n"})
        self.assertEqual([RULE_TRAILER], self.repository.rules())

    def test_a_trailer_followed_by_a_co_author_paragraph_passes(self) -> None:
        text = f"Fix the contract\n\n{DEFECT}\n\nCo-Authored-By: someone <someone@example.invalid>\n"
        self.repository.git.committed(text, {"AGENTS.md": "# Fixed\n"})
        self.assertEqual([], self.repository.rules())

    def test_a_merge_commit_is_exempt(self) -> None:
        git = self.repository.git
        git.git("switch", "--quiet", "-c", "side")
        git.committed(message("Add a side note", FEATURE), {"side.md": "side\n"})
        git.git("switch", "--quiet", "main")
        git.committed(message("Add a main note", FEATURE), {"main.md": "main\n"})
        git.merged("side", "Merge branch side")
        self.assertEqual([], self.repository.rules())


class TestSignThreeLiteralComparisons(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SpecialRepository(self)

    def test_a_comparison_with_one_inputs_name_is_a_row(self) -> None:
        self.repository.git.committed(message("Skip a report", FEATURE), {"lib/skip.py": LITERAL})
        self.assertEqual([RULE_LITERAL], self.repository.rules())

    def test_a_comparison_with_a_suffix_or_a_plain_word_is_no_row(self) -> None:
        self.repository.git.committed(message("Read notes", FEATURE), {"lib/notes.py": TYPED})
        self.assertEqual([], self.repository.rules())


class TestSignFourChangedConstants(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SpecialRepository(self)
        self.repository.git.committed(message("Accept the audit", FEATURE), {**BASELINE, "lib/limits.py": LIMITS})

    def _changed(self, extra: dict[str, str]) -> list[dict]:
        files = {"lib/limits.py": LIMITS.replace("80", "96"), **extra}
        self.repository.git.committed(message("Raise the limit", FEATURE), files)
        return [row for row in self.repository.rows() if row["rule"] == RULE_CONSTANT]

    def test_a_constant_changed_since_the_baseline_is_a_row(self) -> None:
        self.assertEqual(["MAX_NAME_LENGTH: 80 → 96; no test names it"], [row["detail"] for row in self._changed({})])

    def test_the_row_says_when_a_test_names_the_constant(self) -> None:
        rows = self._changed({"tests/test_limits.py": PINNING_TEST})
        self.assertEqual(["MAX_NAME_LENGTH: 80 → 96; a test names it"], [row["detail"] for row in rows])

    def test_a_constant_unchanged_since_the_baseline_is_no_row(self) -> None:
        self.assertEqual([], [rule for rule in self.repository.rules() if rule == RULE_CONSTANT])


class TestSignFiveGrownEnumerations(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SpecialRepository(self)
        self.repository.git.committed(message("Accept the audit", FEATURE), {**BASELINE, "lib/limits.py": LIMITS})

    def _grown(self, kinds: list[str]) -> None:
        text = LIMITS.replace("(\"book\", \"article\")", "(" + ", ".join(f"\"{kind}\"" for kind in kinds) + ")")
        self.repository.git.committed(message(f"Add {kinds[-1]}", FEATURE), {"lib/limits.py": text})

    def test_an_enumeration_grown_in_two_commits_is_a_row(self) -> None:
        self._grown(["book", "article", "thesis"])
        self._grown(["book", "article", "thesis", "talk"])
        self.assertEqual([RULE_ENUMERATION], [rule for rule in self.repository.rules() if rule == RULE_ENUMERATION])

    def test_an_enumeration_grown_in_one_commit_is_no_row(self) -> None:
        self._grown(["book", "article", "thesis", "talk"])
        self.assertEqual([], [rule for rule in self.repository.rules() if rule == RULE_ENUMERATION])


if __name__ == "__main__":
    unittest.main()
