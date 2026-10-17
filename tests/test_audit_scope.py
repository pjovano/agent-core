from __future__ import annotations

import unittest

from _audit_files import REPOSITORY_FILES, TemporaryFiles

from agent_core._audit.scope import CORE_SCOPE, INSTRUCTION_GROUPS, ControlPlaneFiles, Scope

STRAY_FILES = ("README.md", ".claude/skills/one/notes.txt", "lib/data.json", "upgrade/PLAN.md",
               "audit/baseline.json")
OVERLAY_FILES = (".claude/code-overlay.md", ".claude/glossary.md")
UPGRADE_DIRECTORY = "upgrade/"
DOMAIN_ROOT_FILE = "requirements.txt"
DOMAIN_CODE = ".claude/skills/one/server.py"


class TestControlPlaneFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        for names in REPOSITORY_FILES.values():
            self.files.populated(names)
        self.files.populated(STRAY_FILES)
        self.control_plane = ControlPlaneFiles(self.files.root)

    def test_every_repository_file_lands_in_its_group(self) -> None:
        expected = {group: sorted(self.files.root / name for name in names)
                    for group, names in REPOSITORY_FILES.items()}
        self.assertEqual(expected, self.control_plane.by_group())

    def test_a_file_outside_the_patterns_is_in_no_group(self) -> None:
        strays = {self.files.root / name for name in STRAY_FILES}
        self.assertEqual(set(), strays & set(self.control_plane.all()))

    def test_the_code_overlay_and_the_domain_glossary_are_instruction_files(self) -> None:
        overlays = {self.files.root / name for name in OVERLAY_FILES}
        self.assertEqual(overlays, overlays & set(self.control_plane.of_groups(INSTRUCTION_GROUPS)))


class TestTheCoreScope(unittest.TestCase):
    def test_no_scope_pattern_names_a_path_under_upgrade(self) -> None:
        patterns = [pattern for group in CORE_SCOPE.group_patterns().values() for pattern in group]
        self.assertEqual([], [pattern for pattern in patterns if pattern.startswith(UPGRADE_DIRECTORY)])


class TestADomainScope(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.populated((DOMAIN_ROOT_FILE, DOMAIN_CODE))
        addition = Scope(root_files=(DOMAIN_ROOT_FILE,), patterns={"code": (".claude/skills/*/server.py",)})
        self.control_plane = ControlPlaneFiles(self.files.root, CORE_SCOPE.extended_by(addition))

    def test_a_domain_root_file_is_a_contract_file(self) -> None:
        self.assertEqual([self.files.root / DOMAIN_ROOT_FILE], self.control_plane.by_group()["contract"])

    def test_a_domain_pattern_adds_to_its_group(self) -> None:
        self.assertEqual([self.files.root / DOMAIN_CODE], self.control_plane.by_group()["code"])

    def test_a_domain_scope_keeps_the_core_groups_in_their_order(self) -> None:
        self.assertEqual(tuple(CORE_SCOPE.group_patterns()), self.control_plane.groups())


if __name__ == "__main__":
    unittest.main()
