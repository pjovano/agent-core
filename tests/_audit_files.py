from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from _core_path import CoreModulePath

CoreModulePath.activate()

from agent_core._audit.cli import CommandLine

REPOSITORY_FILES = {
    "contract": ("AGENTS.md", "CLAUDE.md", ".claude/settings.json"),
    "skills": (".claude/skills/one/SKILL.md", ".claude/skills/one/reference/table.md", ".claude/code-overlay.md",
               ".claude/glossary.md"),
    "workers": (".claude/agents/worker.md",),
    "code": ("lib/core.py", "lib/_core/notes.py", ".claude/skills/one/scripts/run.py",
             ".claude/skills/one/scripts/_run/core.py", "audit/checks.py"),
    "tests": ("tests/test_one.py", "tests/ports/test_two_contract.py", "tests/README.md",
              "tests/fixtures/goldens/case.json"),
    "configuration": ("pyproject.toml", ".github/workflows/ci.yml"),
}


class TemporaryFiles:
    def __init__(self, case: unittest.TestCase) -> None:
        self._directory = tempfile.TemporaryDirectory()
        case.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def written(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def populated(self, names: tuple[str, ...]) -> list[Path]:
        return [self.written(name, "") for name in names]

    def linked(self, name: str, target: str) -> None:
        link = self.root / name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)


class AuditRun:
    def __init__(self, root: Path) -> None:
        self._root = root

    def printed(self, *arguments: str) -> str:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            CommandLine().run(["--root", str(self._root), *arguments])
        return captured.getvalue()

    def payload(self, *arguments: str) -> dict:
        return json.loads(self.printed(*arguments))
