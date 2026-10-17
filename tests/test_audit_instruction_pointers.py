from __future__ import annotations

import os
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from _audit_files import TemporaryFiles

from agent_core._audit.pointers import FINDING_FUTURE_DATE, FINDING_MISSING_PATH, InstructionPointers, NamedPath
from agent_core._audit.scope import CORE_SCOPE, ControlPlaneFiles, RepositoryPath, Scope

TODAY = date(2026, 9, 15)
FUTURE_DATE_NOTE = "Decided 2027-01-01 to keep it.\n"
PAST_DATE_NOTE = "Decided 2020-01-01 to keep it.\n"
MISSING_PATH_NOTE = "Run `.claude/skills/no-such-skill/SKILL.md` first.\n"
PRESENT_PATH = "skills/present/SKILL.md"
PRESENT_PATH_NOTE = f"Run `{PRESENT_PATH}` first.\n"
CORE_SKILL_FILE = "vendor/agent-core/skills/clean-code/SKILL.md"
CORE_SKILL_LINK = ".claude/skills/clean-code"
CORE_SKILL_TARGET = "../../vendor/agent-core/skills/clean-code"
BROKEN_SKILL_LINK = ".claude/skills/gone"
BROKEN_SKILL_TARGET = "../../vendor/agent-core/skills/gone"
LINKED_PATH_NOTE = f"Read `{CORE_SKILL_LINK}/SKILL.md` first.\n"
BROKEN_LINK_NOTE = f"Read `{BROKEN_SKILL_LINK}/SKILL.md` first.\n"
HOME_NOTE = "notes.md"
SPACED_PREFIX = "shared notes/"
SPACED_NOTE = f"{SPACED_PREFIX}a b.md"


class TestInstructionPointers(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written(PRESENT_PATH, "")

    def _findings(self, name: str, text: str) -> list[str]:
        written = self.files.written(name, text)
        pointers = InstructionPointers([written], ControlPlaneFiles(self.files.root), TODAY)
        return [finding["rule"] for finding in pointers.findings()]

    def test_a_path_that_does_not_exist_is_reported(self) -> None:
        self.assertEqual([FINDING_MISSING_PATH], self._findings("missing.md", MISSING_PATH_NOTE))

    def test_a_path_that_exists_is_not_reported(self) -> None:
        self.assertEqual([], self._findings("present.md", PRESENT_PATH_NOTE))

    def test_a_date_in_the_future_is_reported(self) -> None:
        self.assertEqual([FINDING_FUTURE_DATE], self._findings("future.md", FUTURE_DATE_NOTE))

    def test_a_date_in_the_past_is_not_reported(self) -> None:
        self.assertEqual([], self._findings("past.md", PAST_DATE_NOTE))


class TestInstructionPointersThroughACoreSymlink(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written(CORE_SKILL_FILE, "")
        self.files.linked(CORE_SKILL_LINK, CORE_SKILL_TARGET)
        self.files.linked(BROKEN_SKILL_LINK, BROKEN_SKILL_TARGET)

    def _findings_of(self, path: Path) -> list[dict]:
        return InstructionPointers([path], ControlPlaneFiles(self.files.root), TODAY).findings()

    def test_a_path_through_a_symlink_into_the_vendored_core_is_present(self) -> None:
        self.assertEqual([], self._findings_of(self.files.written("rule.md", LINKED_PATH_NOTE)))

    def test_a_path_through_a_broken_symlink_is_reported(self) -> None:
        expected = [{"rule": FINDING_MISSING_PATH, "file": "rule.md", "line": 1,
                     "detail": f"{BROKEN_SKILL_LINK}/SKILL.md"}]
        self.assertEqual(expected, self._findings_of(self.files.written("rule.md", BROKEN_LINK_NOTE)))

    def test_a_finding_in_a_linked_core_skill_is_labelled_by_its_link_path(self) -> None:
        linked_skill = self.files.root / CORE_SKILL_LINK / "SKILL.md"
        linked_skill.write_text(BROKEN_LINK_NOTE, encoding="utf-8")
        self.assertEqual([f"{CORE_SKILL_LINK}/SKILL.md"],
                         [finding["file"] for finding in self._findings_of(linked_skill)])

    def test_a_linked_core_skill_keeps_the_label_its_baseline_key_carries(self) -> None:
        linked_skill = self.files.root / CORE_SKILL_LINK / "SKILL.md"
        self.assertEqual(f"{CORE_SKILL_LINK}/SKILL.md", RepositoryPath(linked_skill, self.files.root).label())


class SpacedRoot:
    prefix = SPACED_PREFIX

    def __init__(self, base: Path) -> None:
        self._base = base

    def resolved(self, token: str) -> Path:
        return self._base / token


class TestNamedPath(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.plane = ControlPlaneFiles(self.files.root)

    def test_a_home_path_expands(self) -> None:
        self.files.written(HOME_NOTE, "")
        elsewhere = ControlPlaneFiles(self.files.root / "elsewhere")
        with mock.patch.dict(os.environ, {"HOME": str(self.files.root)}):
            self.assertFalse(NamedPath(f"~/{HOME_NOTE}", elsewhere).is_missing())

    def test_a_placeholder_is_not_a_path(self) -> None:
        self.assertFalse(NamedPath("<basename>.md", self.plane).is_missing())

    def test_a_bare_root_file_names_a_path(self) -> None:
        self.assertTrue(NamedPath("CLAUDE.md", self.plane).is_missing())
        self.files.written("CLAUDE.md", "")
        self.assertFalse(NamedPath("CLAUDE.md", self.plane).is_missing())

    def test_the_bare_contract_file_names_a_path(self) -> None:
        self.assertTrue(NamedPath("AGENTS.md", self.plane).is_missing())
        self.files.written("AGENTS.md", "")
        self.assertFalse(NamedPath("AGENTS.md", self.plane).is_missing())

    def test_a_token_outside_every_prefix_names_no_path(self) -> None:
        self.assertFalse(NamedPath("library/paper.pdf", self.plane).is_missing())


class TestADomainNamedRoot(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        scope = Scope(named_roots=(SpacedRoot(self.files.root / "base"),))
        self.plane = ControlPlaneFiles(self.files.root, CORE_SCOPE.extended_by(scope))

    def test_a_path_under_a_domain_root_with_a_space_resolves_under_that_root(self) -> None:
        self.files.written(f"base/{SPACED_NOTE}", "")
        self.assertFalse(NamedPath(SPACED_NOTE, self.plane).is_missing())

    def test_a_missing_path_under_a_domain_root_is_reported(self) -> None:
        self.assertTrue(NamedPath(SPACED_NOTE, self.plane).is_missing())


if __name__ == "__main__":
    unittest.main()
