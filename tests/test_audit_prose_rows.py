from __future__ import annotations

import unittest

from _audit_files import AuditRun, TemporaryFiles
from _git_files import FEATURE, GitFiles, message

GLOSSARY = """# Glossary

| Term | Means | Not |
| --- | --- | --- |
| record | one fact the user gives | entry, item |
| record name | the filename of a record | slug |
| reading list | a list of works to read | bibliography (for the document) |
"""
SKILL_PATH = ".claude/skills/one/SKILL.md"
LONG_COMMAND = ("Run the checks from the root of the repository after every change to the code, the skills, the "
                "workers, or the contract itself.")
LONG_DEFINITION = ("The ledger is the directory that holds every record the user gives, each kept as one file under "
                   "its record name, beside the index.")
A_YEAR_AGO = "2025-10-01T00:00:00Z"
SEVEN_SENTENCES = " ".join(f"The record holds part {number}." for number in range(7))


class ProseRoot:
    def __init__(self, case: unittest.TestCase) -> None:
        self.files = TemporaryFiles(case)
        self.files.written("AGENTS.md", "# Contract\n")
        self.files.written(".claude/glossary.md", GLOSSARY)

    def rules(self, text: str) -> list[str]:
        self.files.written(SKILL_PATH, f"---\nname: one\ndescription: \"One.\"\n---\n\n# one\n\n{text}\n")
        rows = AuditRun(self.files.root).payload("lint")["prose"]
        return [row["rule"] for row in rows if row["file"] == SKILL_PATH]


class TestTheWordRules(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ProseRoot(self)

    def test_a_banned_force_word_is_a_row(self) -> None:
        self.assertEqual(["banned-force-word"], self.root.rules("Try to file the record."))

    def test_a_banned_force_word_quoted_in_italics_is_no_row(self) -> None:
        self.assertEqual([], self.root.rules("The words *try to* state no force."))

    def test_a_bare_should_is_a_row(self) -> None:
        self.assertEqual(["bare-should"], self.root.rules("You should file the record."))

    def test_the_force_word_should_in_capitals_is_no_row(self) -> None:
        self.assertEqual([], self.root.rules("You SHOULD file the record first."))

    def test_a_banned_synonym_after_a_determiner_is_a_row(self) -> None:
        self.assertEqual(["banned-synonym"], self.root.rules("File each entry the user gives."))

    def test_a_banned_synonym_inside_a_technical_name_is_no_row(self) -> None:
        self.assertEqual([], self.root.rules("Write the record name of the record."))

    def test_a_synonym_banned_for_one_sense_needs_that_sense_in_the_line(self) -> None:
        self.assertEqual([], self.root.rules("File the work on the bibliography."))

    def test_a_synonym_banned_for_one_sense_in_that_sense_is_a_row(self) -> None:
        self.assertEqual(["banned-synonym"], self.root.rules("Deliver the bibliography as a document."))

    def test_agent_alone_is_a_row(self) -> None:
        self.assertEqual(["agent-alone"], self.root.rules("The agent files the record."))

    def test_agent_inside_a_name_is_no_row(self) -> None:
        self.assertEqual([], self.root.rules("Run `agent` once. The agent-core repository holds the core."))


class TestTheSteRules(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ProseRoot(self)

    def test_a_command_over_twenty_words_is_a_row(self) -> None:
        self.assertEqual(["long-sentence"], self.root.rules(LONG_COMMAND))

    def test_a_definition_of_twenty_three_words_is_no_row(self) -> None:
        self.assertEqual([], self.root.rules(LONG_DEFINITION))

    def test_a_clause_with_two_instructions_is_a_row(self) -> None:
        self.assertEqual(["one-instruction"], self.root.rules("Check each record name, MUST quote each rule."))

    def test_two_main_clauses_with_one_instruction_each_are_no_row(self) -> None:
        self.assertEqual([], self.root.rules("Check each record name, and quote each rule."))

    def test_a_passive_verb_in_a_command_is_a_row(self) -> None:
        self.assertEqual(["passive-voice"], self.root.rules("If the record is filed, report its name."))

    def test_a_noun_cluster_of_four_nouns_is_a_row(self) -> None:
        self.assertEqual(["noun-cluster"], self.root.rules("Check the ledger index file header once."))

    def test_a_paragraph_of_seven_sentences_is_a_row(self) -> None:
        self.assertEqual(["long-paragraph"], self.root.rules(SEVEN_SENTENCES))

    def test_a_recast_rationale_tail_is_no_row(self) -> None:
        rationale = "**Read the skill before you file a record,** so that each step you take is one the skill states."
        self.assertEqual([], self.root.rules(rationale))


class TestRedundancy(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written("AGENTS.md", "# Contract\n\n**A record title holds at most twelve words.**\n")

    def _rows(self, name: str, text: str) -> list[tuple[str, str]]:
        self.files.written(name, f"# copy\n\n{text}\n")
        return [(row["rule"], row["file"]) for row in AuditRun(self.files.root).payload("lint")["redundancy"]]

    def test_a_copy_that_drifted_is_a_row_on_the_later_file(self) -> None:
        rows = self._rows(SKILL_PATH, "**A record title holds at most ten words.**")
        self.assertEqual([("drifted-duplicate", SKILL_PATH)], rows)

    def test_an_exact_copy_is_no_row(self) -> None:
        self.assertEqual([], self._rows(SKILL_PATH, "**A record title holds at most twelve words.**"))

    def test_a_copy_restated_for_a_worker_is_no_row(self) -> None:
        self.assertEqual([], self._rows(".claude/agents/filer.md", "**A record title holds at most ten words.**"))


class TestStaleness(unittest.TestCase):
    def setUp(self) -> None:
        self.git = GitFiles(self)

    def _rows(self, text: str, date: str | None = None) -> list[str]:
        if date is None:
            self.git.committed(message("Add the contract", FEATURE), {"AGENTS.md": text})
        else:
            self.git.committed_on(date, message("Add the contract", FEATURE), {"AGENTS.md": text})
        return [row["rule"] for row in AuditRun(self.git.root).payload("lint")["staleness"]]

    def test_a_time_word_on_a_line_unchanged_for_a_month_is_a_row(self) -> None:
        self.assertEqual(["time-word"], self._rows("# Contract\n\nThe ledger currently holds a record.\n", A_YEAR_AGO))

    def test_a_time_word_on_a_fresh_line_is_no_row(self) -> None:
        self.assertEqual([], self._rows("# Contract\n\nThe ledger is still open.\n"))

    def test_a_count_of_skills_the_plane_does_not_hold_is_a_row(self) -> None:
        self.git.written(".claude/skills/one/SKILL.md", "# one\n")
        self.assertEqual(["count-differs"], self._rows("# Contract\n\nIt holds two skills.\n"))

    def test_a_count_of_skills_the_plane_holds_is_no_row(self) -> None:
        self.git.written(".claude/skills/one/SKILL.md", "# one\n")
        self.assertEqual([], self._rows("# Contract\n\nIt holds one skills file.\n"))


if __name__ == "__main__":
    unittest.main()
