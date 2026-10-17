from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

from _repository import REPOSITORY_ROOT

CORE_PACKAGE = "agent_core"
FUTURE = "__future__"
CORE_DIR = REPOSITORY_ROOT / "core"
CODE_FILES = sorted([*(CORE_DIR / "lib").rglob("*.py"), *(CORE_DIR / "skills").glob("*/scripts/*.py"),
                     *(REPOSITORY_ROOT / "bin").glob("*.py")])


def module_level_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [name for node in tree.body for name in imported_names(node)]


def imported_names(node: ast.stmt) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module.split(".")[0]]
    return []


class TheCoresCodeRunsOnABarePython(unittest.TestCase):
    def test_the_core_holds_code_to_check(self) -> None:
        self.assertTrue(CODE_FILES)

    def test_every_module_level_import_is_of_the_standard_library_or_the_core(self) -> None:
        allowed = set(sys.stdlib_module_names) | {CORE_PACKAGE, FUTURE}
        foreign = [f"{path.relative_to(REPOSITORY_ROOT).as_posix()}: {name}" for path in CODE_FILES
                   for name in module_level_imports(path) if name not in allowed]
        self.assertEqual([], foreign)


if __name__ == "__main__":
    unittest.main()
