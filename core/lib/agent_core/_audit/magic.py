from __future__ import annotations

import ast
from pathlib import Path

from agent_core._audit.rows import Row
from agent_core._audit.scope import ENCODING, RepositoryPath

OBVIOUS_NUMBERS = (0, 1, -1)
MEASURE_MAGIC_NUMBER = "magic-number"
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
MATCH_GROUP_METHODS = ("group", "start", "end", "span")


class MagicNumbers:
    def __init__(self, paths: list[Path], root: Path) -> None:
        self._paths = paths
        self._root = root

    def findings(self) -> list[dict]:
        return [finding for path in self._paths for finding in FileNumbers(path, self._root).findings()]


class FileNumbers:
    def __init__(self, path: Path, root: Path) -> None:
        self._path = path
        self._label = RepositoryPath(path, root).label()

    def findings(self) -> list[dict]:
        try:
            nodes = list(ast.walk(ast.parse(self._path.read_text(encoding=ENCODING))))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            return []
        exempt = self._exempt(nodes)
        return [Row(MEASURE_MAGIC_NUMBER, self._label, child.lineno, f"{function.name}, {child.value!r}").as_dict()
                for function in nodes if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
                for child in self._own_nodes(function) if self._is_magic(child) and id(child) not in exempt]

    @staticmethod
    def _exempt(nodes: list[ast.AST]) -> set[int]:
        compared = {id(operand) for node in nodes if isinstance(node, ast.Compare)
                    for operand in (node.left, *node.comparators)}
        defaults = {id(default) for node in nodes if isinstance(node, ast.arguments)
                    for default in (*node.defaults, *node.kw_defaults) if default is not None}
        named = {id(keyword.value) for node in nodes if isinstance(node, ast.Call) for keyword in node.keywords}
        indices = {id(argument) for node in nodes if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in MATCH_GROUP_METHODS for argument in node.args}
        return compared | defaults | named | indices

    @staticmethod
    def _own_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
        found, pending = [], list(function.body)
        while pending:
            node = pending.pop()
            found.append(node)
            if not isinstance(node, SCOPES):
                pending.extend(ast.iter_child_nodes(node))
        return found

    @staticmethod
    def _is_magic(node: ast.AST) -> bool:
        return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool) and node.value not in OBVIOUS_NUMBERS)
