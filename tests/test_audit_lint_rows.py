from __future__ import annotations

import json
import unittest

from _audit_files import AuditRun, TemporaryFiles

from agent_core._audit.rows import Fingerprint

CONTRACT = "# Contract\n\nRun the checks after every change.\n\nYou should report each finding.\n"
INSERTED_ABOVE = "# Contract\n\nA new paragraph opens the contract.\n\nRun the checks after every change.\n\n" \
                 "You should report each finding.\n"
ROW_FIELDS = ["rule", "file", "line", "detail", "fingerprint"]
REASON = "the user acknowledged today's rows"


class LintedRoot:
    def __init__(self, case: unittest.TestCase, contract: str = CONTRACT) -> None:
        self.files = TemporaryFiles(case)
        self.files.written("AGENTS.md", contract)
        self.audit = AuditRun(self.files.root)

    def should_rows(self, *arguments: str) -> list[dict]:
        return [row for row in self.audit.payload("lint", *arguments)["prose"] if row["rule"] == "bare-should"]

    def baseline(self) -> dict:
        return json.loads((self.files.root / "audit" / "baseline.json").read_text(encoding="utf-8"))


class TestALintRow(unittest.TestCase):
    def test_a_row_carries_its_rule_file_line_detail_and_fingerprint(self) -> None:
        self.assertEqual(ROW_FIELDS, list(LintedRoot(self).should_rows()[0]))

    def test_a_fingerprint_survives_a_line_inserted_above_its_row(self) -> None:
        before = LintedRoot(self).should_rows()[0]
        after = LintedRoot(self, INSERTED_ABOVE).should_rows()[0]
        self.assertEqual((before["fingerprint"], before["line"] + 2), (after["fingerprint"], after["line"]))

    def test_a_fingerprint_changes_with_its_line(self) -> None:
        self.assertNotEqual(Fingerprint("r", "a.md", "one line").text(), Fingerprint("r", "a.md", "another").text())

    def test_a_fingerprint_ignores_the_spacing_of_its_line(self) -> None:
        self.assertEqual(Fingerprint("r", "a.md", "one  line ").text(), Fingerprint("r", "a.md", "one line").text())

    def test_a_fingerprint_names_its_rule_and_its_file(self) -> None:
        fingerprints = {Fingerprint("r", "a.md", "x").text(), Fingerprint("s", "a.md", "x").text(),
                        Fingerprint("r", "b.md", "x").text()}
        self.assertEqual(3, len(fingerprints))


class TestTheAcknowledgement(unittest.TestCase):
    def setUp(self) -> None:
        self.root = LintedRoot(self)
        self.fingerprint = self.root.should_rows()[0]["fingerprint"]

    def test_acknowledge_writes_each_fingerprint_with_its_reason(self) -> None:
        self.root.audit.payload("acknowledge", "--reason", REASON, self.fingerprint)
        self.assertEqual({self.fingerprint: REASON}, self.root.baseline()["acknowledged"])

    def test_lint_new_drops_an_acknowledged_row(self) -> None:
        self.root.audit.payload("acknowledge", "--reason", REASON, self.fingerprint)
        self.assertEqual([], self.root.should_rows("--new"))

    def test_lint_without_new_keeps_an_acknowledged_row(self) -> None:
        self.root.audit.payload("acknowledge", "--reason", REASON, self.fingerprint)
        self.assertEqual(1, len(self.root.should_rows()))

    def test_dismiss_removes_the_acknowledgement(self) -> None:
        self.root.audit.payload("acknowledge", "--reason", REASON, self.fingerprint)
        self.root.audit.payload("dismiss", self.fingerprint)
        self.assertEqual(({}, 1), (self.root.baseline()["acknowledged"], len(self.root.should_rows("--new"))))

    def test_acknowledge_every_row_leaves_lint_new_without_rows(self) -> None:
        self.root.audit.payload("acknowledge", "--reason", REASON, "--every-row")
        payload = self.root.audit.payload("lint", "--new")
        self.assertEqual([], [row for value in payload.values() if isinstance(value, list) for row in value])

    def test_accept_keeps_the_acknowledgements(self) -> None:
        self.root.audit.payload("acknowledge", "--reason", REASON, self.fingerprint)
        self.root.audit.payload("accept")
        self.assertEqual({self.fingerprint: REASON}, self.root.baseline()["acknowledged"])

    def test_acknowledge_keeps_the_accepted_digests(self) -> None:
        self.root.audit.payload("accept")
        self.root.audit.payload("acknowledge", "--reason", REASON, self.fingerprint)
        self.assertIn("AGENTS.md", self.root.baseline()["digests"])


class TestTheWordCountsInTheBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self.root = LintedRoot(self)
        self.root.audit.payload("accept")

    def test_accept_records_the_word_counts(self) -> None:
        self.assertEqual(self.root.audit.payload("lint")["weight"]["instruction_text"],
                         self.root.baseline()["weight"]["instruction_text"])

    def test_an_acknowledgement_keeps_the_word_counts(self) -> None:
        self.root.audit.payload("acknowledge", "--reason", REASON, "--every-row")
        self.assertIn("weight", self.root.baseline())

    def test_lint_names_the_growth_since_the_accepted_counts(self) -> None:
        self.root.files.written("AGENTS.md", CONTRACT + "\nRun the suite.\n")
        self.assertEqual(3, self.root.audit.payload("lint")["weight"]["growth_since_accept"]["always_loaded"])


class TestTheProseOfOneFile(unittest.TestCase):
    def setUp(self) -> None:
        self.root = LintedRoot(self)
        self.root.files.written(".claude/skills/one/SKILL.md", "# one\n\nThe skill should run.\n")

    def test_prose_names_the_rows_of_the_named_file_alone(self) -> None:
        payload = self.root.audit.payload("prose", "--new", str(self.root.files.root / ".claude/skills/one/SKILL.md"))
        self.assertEqual({".claude/skills/one/SKILL.md"}, {row["file"] for row in payload["prose"]})

    def test_prose_new_drops_the_acknowledged_rows_of_the_file(self) -> None:
        path = str(self.root.files.root / "AGENTS.md")
        fingerprints = [row["fingerprint"] for row in self.root.audit.payload("prose", path)["prose"]]
        self.root.audit.payload("acknowledge", "--reason", REASON, *fingerprints)
        self.assertEqual([], self.root.audit.payload("prose", "--new", path)["prose"])

    def test_prose_of_a_file_outside_the_instruction_text_has_no_rows(self) -> None:
        outside = self.root.files.written("notes/draft.md", "You should not see this.\n")
        self.assertEqual([], self.root.audit.payload("prose", "--new", str(outside))["prose"])


if __name__ == "__main__":
    unittest.main()
