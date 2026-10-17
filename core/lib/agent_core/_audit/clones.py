from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.rows import Row
from agent_core._audit.scope import ENCODING, RepositoryPath
from agent_core._audit.special import ModuleValues

LIBRARY_DIRECTORY = "lib"
SHORTEST_CLONE = 3
RESTATED_VALUES = 2
RULE_CLONE = "clone-of-helper"
RULE_RESTATED = "restates-helper-constants"
PLACEHOLDER = "_"


@dataclass(frozen=True)
class Function:
    label: str
    name: str
    line: int
    shape: int | None
    statements: int
    literals: frozenset[str]


class FunctionsOf:
    def __init__(self, path: Path, root: Path) -> None:
        self._path = path
        self._label = RepositoryPath(path, root).label()

    def source(self) -> str:
        try:
            return self._path.read_text(encoding=ENCODING)
        except (OSError, UnicodeDecodeError):
            return ""

    def functions(self) -> list[Function]:
        try:
            tree = ast.parse(self.source())
        except (SyntaxError, ValueError):
            return []
        return [self._function(node) for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Function:
        nodes = [child for statement in node.body for child in ast.walk(statement)]
        literals = frozenset(child.value for child in nodes
                             if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value)
        shape = hash(tuple(self._token(child) for child in nodes)) if len(node.body) >= SHORTEST_CLONE else None
        return Function(self._label, node.name, node.lineno, shape, len(node.body), literals)

    @staticmethod
    def _token(node: ast.AST) -> str:
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Attribute):
            return f"{PLACEHOLDER}.{node.attr}"
        return type(node).__name__


class CloneCheck:
    def __init__(self, pipeline: list[Path], root: Path) -> None:
        self._root = root
        self._library = [path for path in pipeline if self._in_library(path)]
        self._callers = [path for path in pipeline if not self._in_library(path)]

    def _in_library(self, path: Path) -> bool:
        return RepositoryPath(path, self._root).label().split("/")[0] == LIBRARY_DIRECTORY

    def rows(self) -> list[dict]:
        helpers = defaultdict(list)
        for path in self._library:
            for function in FunctionsOf(path, self._root).functions():
                helpers[function.shape].append(function)
        helpers.pop(None, None)
        values = self._library_values()
        callers = [function for path in self._callers for function in FunctionsOf(path, self._root).functions()]
        return [row for function in callers for row in self._of(function, helpers.get(function.shape, []), values)]

    def _library_values(self) -> dict[str, dict[str, str]]:
        values = {}
        for path in self._library:
            constants = ModuleValues(FunctionsOf(path, self._root).source()).constants()
            values[RepositoryPath(path, self._root).label()] = {
                value: name for name, (_line, value) in constants.items() if isinstance(value, str) and value}
        return values

    def _of(self, function: Function, helpers: list[Function], values: dict[str, dict[str, str]]) -> list[dict]:
        rows = [Row(RULE_CLONE, function.label, function.line, f"{function.name} repeats {helper.label}:"
                    f"{helper.name}; call the helper").as_dict()
                for helper in helpers if function.shape is not None]
        for module, constants in values.items():
            restated = sorted(constants[value] for value in function.literals if value in constants)
            if len(restated) >= RESTATED_VALUES:
                rows.append(Row(RULE_RESTATED, function.label, function.line,
                                f"{function.name} restates {', '.join(restated)} of {module}; call its "
                                f"helper").as_dict())
        return rows
