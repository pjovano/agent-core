from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from _audit_files import AuditRun, TemporaryFiles
from _repository import REPOSITORY_ROOT

from agent_core._audit.pointers import FINDING_MISSING_PATH
from agent_core._audit.scope import CORE_SCOPE, HomeRoot

CORE_DIR = REPOSITORY_ROOT / "core"
VENDORED_CORE = "vendor/agent-core"
LINKED_KINDS = ("skills", "agents")
FILES_THE_CORE_READS_FROM_A_DOMAIN = CORE_SCOPE.root_files + (".claude/code-overlay.md", ".claude/glossary.md")


class MinimalDomain:
    def __init__(self, files: TemporaryFiles) -> None:
        self._files = files

    def built(self) -> Path:
        shutil.copytree(CORE_DIR, self._files.root / VENDORED_CORE, symlinks=True)
        for kind in LINKED_KINDS:
            self._link_every_unit(kind)
        self._files.populated(FILES_THE_CORE_READS_FROM_A_DOMAIN)
        return self._files.root

    def _link_every_unit(self, kind: str) -> None:
        for unit in sorted((CORE_DIR / kind).iterdir()):
            if self._is_core_unit(unit):
                self._files.linked(f".claude/{kind}/{unit.name}", f"../../{VENDORED_CORE}/{kind}/{unit.name}")

    @staticmethod
    def _is_core_unit(unit: Path) -> bool:
        return unit.is_dir() or unit.suffix == ".md"


class EveryPathACoreUnitNamesResolvesInADomain(unittest.TestCase):
    def setUp(self) -> None:
        self.domain = MinimalDomain(TemporaryFiles(self)).built()

    def test_no_linked_core_unit_names_a_path_only_agent_core_holds(self) -> None:
        pointers = AuditRun(self.domain).payload("lint")["pointers"]
        self.assertEqual([], [finding for finding in pointers if self._names_a_repository_path(finding)])

    @staticmethod
    def _names_a_repository_path(finding: dict) -> bool:
        is_missing_path = finding["rule"] == FINDING_MISSING_PATH
        return is_missing_path and not finding["detail"].startswith(HomeRoot.prefix)


if __name__ == "__main__":
    unittest.main()
