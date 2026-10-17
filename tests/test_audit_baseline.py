from __future__ import annotations

import contextlib
import io
import json
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from _audit_files import AuditRun, TemporaryFiles

from agent_core._audit.baseline import STATUS_CHANGED, STATUS_NEW, STATUS_REMOVED, Baseline, CorruptBaseline
from agent_core._audit.cli import CommandLine

TODAY = date(2026, 9, 15)
NOTE = "note.md"


class TestBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.baseline = Baseline(self.files.root / "baseline.json", self.files.root)
        self.note = self.files.written(NOTE, "first\n")

    def test_an_unaccepted_baseline_has_no_date(self) -> None:
        self.assertIsNone(self.baseline.accepted_on())

    def test_a_file_never_audited_is_new(self) -> None:
        self.assertEqual([NOTE], self.baseline.changed([self.note])[STATUS_NEW])

    def test_an_accepted_file_is_neither_new_nor_changed(self) -> None:
        self.baseline.accept([self.note])
        expected = {STATUS_NEW: [], STATUS_CHANGED: [], STATUS_REMOVED: []}
        self.assertEqual(expected, self.baseline.changed([self.note]))

    def test_an_edited_file_is_changed(self) -> None:
        self.baseline.accept([self.note])
        self.note.write_text("second\n", encoding="utf-8")
        self.assertEqual([NOTE], self.baseline.changed([self.note])[STATUS_CHANGED])

    def test_a_deleted_file_is_removed(self) -> None:
        self.baseline.accept([self.note])
        self.assertEqual([NOTE], self.baseline.changed([])[STATUS_REMOVED])

    def test_accepting_records_the_day_it_ran(self) -> None:
        baseline = Baseline(self.files.root / "dated.json", self.files.root, TODAY)
        self.assertEqual(TODAY.isoformat(), baseline.accept([self.note])["accepted"])


class TestABaselineTornMidWrite(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.path = self.files.root / "baseline.json"
        self.note = self.files.written(NOTE, "first\n")
        Baseline(self.path, self.files.root, TODAY).accept([self.note])

    def test_an_accept_torn_mid_write_keeps_the_earlier_baseline(self) -> None:
        original = Path.write_text

        def torn(path: Path, text: str, *args, **kwargs) -> int:
            original(path, text[: len(text) // 2], *args, **kwargs)
            raise OSError("disk full")

        with mock.patch.object(Path, "write_text", torn), self.assertRaises(OSError):
            Baseline(self.path, self.files.root).accept([self.note])
        self.assertEqual(TODAY.isoformat(), Baseline(self.path, self.files.root).accepted_on())

    def test_a_baseline_that_is_not_json_is_reported_as_corrupt(self) -> None:
        self.path.write_text('{"accepted": "2026', encoding="utf-8")
        with self.assertRaises(CorruptBaseline) as raised:
            Baseline(self.path, self.files.root).accepted_on()
        self.assertIn(str(self.path), str(raised.exception))

    def test_a_corrupt_baseline_is_printed_as_an_error_and_exits_one(self) -> None:
        printed = io.StringIO()
        with mock.patch.object(Baseline, "accepted_on", side_effect=CorruptBaseline("the audit baseline is torn")):
            with contextlib.redirect_stdout(printed), self.assertRaises(SystemExit) as stopped:
                CommandLine().run(["--root", str(self.files.root), "changed"])
        self.assertEqual((1, {"error": "the audit baseline is torn"}), (stopped.exception.code,
                                                                        json.loads(printed.getvalue())))


class TestEachDomainKeepsItsOwnBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written("AGENTS.md", "The contract.\n")

    def test_accept_writes_the_baseline_at_audit_baseline_json_under_the_root(self) -> None:
        AuditRun(self.files.root).payload("accept")
        recorded = json.loads((self.files.root / "audit" / "baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(["AGENTS.md"], list(recorded["digests"]))


if __name__ == "__main__":
    unittest.main()
