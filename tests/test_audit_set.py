from __future__ import annotations

import unittest
from pathlib import Path

from _audit_files import REPOSITORY_FILES, TemporaryFiles

from agent_core._audit.baseline import Baseline
from agent_core._audit.cli import AuditSet
from agent_core._audit.related import RelatedFiles
from agent_core._audit.scope import INSTRUCTION_GROUPS, ControlPlaneFiles

CHANGED_FILES = ("tests/README.md", "pyproject.toml", ".github/workflows/ci.yml", "tests/fixtures/goldens/case.json")


class FakeControlPlane:
    def __init__(self, paths: list[Path]) -> None:
        self._paths = paths

    def all(self) -> list[Path]:
        return self._paths


class AuditedTree:
    def __init__(self, case: unittest.TestCase) -> None:
        self.files = TemporaryFiles(case)
        for names in REPOSITORY_FILES.values():
            self.files.populated(names)
        self.control_plane = ControlPlaneFiles(self.files.root)
        self.baseline_path = self.files.root / "audit" / "baseline.json"

    def accepted(self) -> None:
        Baseline(self.baseline_path, self.files.root).accept(self.control_plane.all())

    def changes(self) -> AuditSet:
        return AuditSet.of_changes(self.control_plane, self.baseline_path)

    def everything(self) -> AuditSet:
        return AuditSet.of_everything(self.control_plane, self.baseline_path)


class TestAChangedFileThatIsNotPython(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = AuditedTree(self)
        self.tree.accepted()

    def test_a_changed_file_that_is_not_python_is_shown(self) -> None:
        for name in CHANGED_FILES:
            self.tree.files.written(name, "edited\n")
        self.assertEqual(sorted(CHANGED_FILES), sorted(self.tree.changes().as_dict()["changed"]))


class TestAuditSet(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = AuditedTree(self)

    def test_everything_is_unaudited_before_any_acceptance(self) -> None:
        expected = sorted(self.tree.files.root / name for group in INSTRUCTION_GROUPS
                          for name in REPOSITORY_FILES[group])
        self.assertEqual(expected, sorted(self.tree.changes().instructions()))

    def test_only_the_files_changed_since_acceptance_are_unaudited(self) -> None:
        self.tree.accepted()
        edited = self.tree.files.written("CLAUDE.md", "edited\n")
        self.assertEqual([edited], self.tree.changes().instructions())

    def test_the_audit_set_of_everything_holds_every_file_after_acceptance(self) -> None:
        self.tree.accepted()
        expected = sorted(self.tree.control_plane.of_groups(INSTRUCTION_GROUPS))
        self.assertEqual(expected, sorted(self.tree.everything().instructions()))

    def test_pipeline_code_leaves_the_tests_out(self) -> None:
        expected = sorted(self.tree.files.root / name for name in REPOSITORY_FILES["code"])
        self.assertEqual(expected, sorted(self.tree.changes().pipeline_code()))

    def test_counts_name_the_three_totals(self) -> None:
        self.assertEqual({"instructions": 8, "code": 7, "control_plane": 19}, self.tree.changes().counts())


class TestRelatedFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.changed = self.files.written("engine.py", "class Engine:\n    pass\n")
        self.caller = self.files.written("skill.md", "The stage runs `engine.py`.\n")
        self.stranger = self.files.written("other.md", "Nothing to do with it.\n")
        self.control_plane = FakeControlPlane([self.changed, self.caller, self.stranger])

    def test_a_file_that_names_a_changed_file_is_related(self) -> None:
        related = RelatedFiles(self.control_plane).of([self.changed])
        self.assertEqual(["skill.md"], [path.name for path in related])

    def test_nothing_is_related_to_an_empty_change_set(self) -> None:
        self.assertEqual([], RelatedFiles(self.control_plane).of([]))


if __name__ == "__main__":
    unittest.main()
