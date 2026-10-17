from __future__ import annotations

import unittest

from _audit_files import AuditRun, TemporaryFiles

from agent_core._audit.text import FileWords

CONTRACT = "# Contract\n\nRun the checks after every change.\n"
SKILL = "---\nname: one\ndescription: \"One skill does one thing.\"\n---\n\n# one\n\nRun `one.py` once.\n"
WORKER = "---\nname: helper\ndescription: \"Helper reads.\"\n---\n\n# helper\n\nRead the file.\n"


class WeighedRoot:
    def __init__(self, case: unittest.TestCase) -> None:
        self.files = TemporaryFiles(case)
        self.files.written("AGENTS.md", CONTRACT)
        self.files.written(".claude/skills/one/SKILL.md", SKILL)
        self.files.written(".claude/agents/helper.md", WORKER)

    def weight(self) -> dict:
        return AuditRun(self.files.root).payload("lint")["weight"]


class TestTheWordCount(unittest.TestCase):
    def test_a_word_holds_a_letter_or_a_digit(self) -> None:
        self.assertEqual(4, FileWords("Run the checks — **now** | |").count())

    def test_a_list_mark_and_a_link_target_are_no_words(self) -> None:
        self.assertEqual(3, FileWords("1. Read [the guide](https://example.invalid/a/b).").count())

    def test_a_code_span_counts_every_word_it_holds(self) -> None:
        self.assertEqual(4, FileWords("Run `audit.py lint --new`.").count())


class TestTheWeightRow(unittest.TestCase):
    def setUp(self) -> None:
        self.weight = WeighedRoot(self).weight()

    def test_each_instruction_file_is_counted(self) -> None:
        expected = {"AGENTS.md": 7, ".claude/skills/one/SKILL.md": 12, ".claude/agents/helper.md": 9}
        self.assertEqual(expected, self.weight["files"])

    def test_the_instruction_text_is_every_file_together(self) -> None:
        self.assertEqual(28, self.weight["instruction_text"])

    def test_the_always_loaded_text_is_the_contract_and_every_description(self) -> None:
        self.assertEqual(7 + 5 + 2, self.weight["always_loaded"])

    def test_the_rest_is_the_instruction_text_outside_the_always_loaded_text(self) -> None:
        self.assertEqual(28 - 14, self.weight["rest"])

    def test_the_growth_is_absent_before_any_accept(self) -> None:
        self.assertIsNone(self.weight["growth_since_accept"])


class TestTheVendoredCore(unittest.TestCase):
    def test_a_skill_linked_into_the_vendored_core_is_weighed_in_the_core_alone(self) -> None:
        root = WeighedRoot(self)
        root.files.written("vendor/agent-core/skills/two/SKILL.md", SKILL)
        root.files.linked(".claude/skills/two", "../../vendor/agent-core/skills/two")
        self.assertNotIn(".claude/skills/two/SKILL.md", root.weight()["files"])


if __name__ == "__main__":
    unittest.main()
