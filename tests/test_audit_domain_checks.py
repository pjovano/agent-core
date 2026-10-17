from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from _audit_files import AuditRun, TemporaryFiles
from _repository import REPOSITORY_ROOT

from agent_core._audit.checks import CHECKS_PATH, SKIPPED_KEY, DomainChecksFile, DomainChecksMissing
from agent_core._audit.cli import CommandLine

CORE_ROWS = ["files", "code", "pointers"]
DOMAIN_ROW = "counted"
ABSENCE = "no real vault is present"
DOMAIN_ROOT_FILE = "extra.md"
DOMAIN_CHECKS = f'''from __future__ import annotations

from agent_core._audit.checks import DomainChecks, PrimaryOnly
from agent_core._audit.scope import Scope


class Counted:
    name = "{DOMAIN_ROW}"

    def findings(self, audit_set):
        return [{{"instructions": len(audit_set.instructions())}}]


class Pile:
    help = "the pile at the root"

    def __init__(self, name):
        self.name = name

    def report(self, root):
        return {{"root": root.name}}


class Place:
    def __init__(self, present):
        self._present = present

    def is_present(self):
        return self._present

    def absence(self):
        return "{ABSENCE}"


DOMAIN = DomainChecks(scope=Scope(root_files=("{DOMAIN_ROOT_FILE}",)), lint=(Counted(),),
                      reports=(PrimaryOnly(Pile("here"), Place(True)), PrimaryOnly(Pile("away"), Place(False))))
'''
CORE_SKILL = REPOSITORY_ROOT / "core" / "skills" / "control-plane-audit"
LINKED_SCRIPT = ".claude/skills/control-plane-audit/scripts/audit.py"
LINKING_ROOT_FILES = {"instructions": 2, "code": 1, "control_plane": 3}


class TestADomainWithChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written("AGENTS.md", "The contract.\n")
        self.files.written(DOMAIN_ROOT_FILE, "A domain root file.\n")
        self.files.written(str(CHECKS_PATH), DOMAIN_CHECKS)
        self.run_audit = AuditRun(self.files.root)

    def test_the_domain_lint_rows_follow_the_core_rows(self) -> None:
        self.assertEqual([*CORE_ROWS, DOMAIN_ROW], list(self.run_audit.payload("lint")))

    def test_a_domain_lint_check_reads_the_audit_set(self) -> None:
        self.assertEqual([{"instructions": 2}], self.run_audit.payload("lint")[DOMAIN_ROW])

    def test_a_domain_root_file_is_an_instruction_file(self) -> None:
        self.assertEqual(2, self.run_audit.payload("lint")["files"]["instructions"])

    def test_a_domain_report_is_a_subcommand_given_the_root(self) -> None:
        self.assertEqual({"root": self.files.root.name}, self.run_audit.payload("here"))

    def test_a_primary_only_check_reports_itself_skipped_where_its_place_is_absent(self) -> None:
        self.assertEqual({SKIPPED_KEY: ABSENCE}, self.run_audit.payload("away"))


class TestADomainWithoutChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written("AGENTS.md", "The contract.\n")

    def test_lint_prints_the_core_rows_alone(self) -> None:
        self.assertEqual(CORE_ROWS, list(AuditRun(self.files.root).payload("lint")))

    def test_no_arguments_print_help(self) -> None:
        self.assertTrue(AuditRun(self.files.root).printed().startswith("usage: audit.py"))


class TestAChecksFileWithoutItsDomain(unittest.TestCase):
    def test_loading_it_names_the_missing_definition(self) -> None:
        files = TemporaryFiles(self)
        files.written(str(CHECKS_PATH), "VALUE = 1\n")
        with self.assertRaises(DomainChecksMissing):
            DomainChecksFile(files.root).loaded()


class TestTheEntryScriptThroughALink(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written("AGENTS.md", "The contract.\n")
        self.files.linked(".claude/skills/control-plane-audit", str(CORE_SKILL))

    def test_it_audits_the_root_that_links_it_and_not_the_core(self) -> None:
        self.assertEqual(LINKING_ROOT_FILES, self._files_audited_from(self.files.root, LINKED_SCRIPT))

    def test_from_a_subdirectory_it_audits_the_root_that_links_it(self) -> None:
        subdirectory = self.files.root / "lib"
        subdirectory.mkdir()
        script = str(self.files.root / LINKED_SCRIPT)
        self.assertEqual(LINKING_ROOT_FILES, self._files_audited_from(subdirectory, script))

    def test_a_report_runs_from_a_subdirectory(self) -> None:
        self.files.written(str(CHECKS_PATH), DOMAIN_CHECKS)
        completed = self._run_from(self.files.root / "audit", str(self.files.root / LINKED_SCRIPT), "here")
        self.assertEqual({"root": self.files.root.name}, json.loads(completed.stdout))

    def _files_audited_from(self, directory: Path, script: str) -> dict:
        return json.loads(self._run_from(directory, script, "lint").stdout)["files"]

    @staticmethod
    def _run_from(directory: Path, script: str, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, script, *arguments], cwd=directory, check=True, capture_output=True,
                              text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


class TestAScriptNoRootLinks(unittest.TestCase):
    def test_it_prints_an_error_naming_the_root_flag_and_exits_1(self) -> None:
        files = TemporaryFiles(self)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), self.assertRaises(SystemExit) as exit_status:
            CommandLine(files.root / "audit.py").run(["lint"])
        self.assertEqual((1, True), (exit_status.exception.code, "--root" in json.loads(captured.getvalue())["error"]))


if __name__ == "__main__":
    unittest.main()
