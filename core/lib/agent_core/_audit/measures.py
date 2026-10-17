from __future__ import annotations

import ast
from pathlib import Path

from agent_core._audit.rows import Row
from agent_core._audit.scope import ENCODING, RepositoryPath

MAX_FUNCTION_LINES = 20
MAX_FILE_LINES = 500
MEASURE_LONG_FUNCTION = "function-over-20-lines"
MEASURE_LONG_FILE = "file-over-500-lines"
MEASURE_DOCSTRING = "docstring"
MEASURE_COMMENT = "comment"
MODULE_NAME = "module"
_COMMENT_MARK = "#"


class CodeMeasures:
    def __init__(self, paths: list[Path], root: Path) -> None:
        self._paths = paths
        self._root = root

    def findings(self) -> list[dict]:
        return [finding for path in self._paths for finding in FileMeasures(path, self._root).findings()]


class FileMeasures:
    def __init__(self, path: Path, root: Path) -> None:
        self._path = path
        self._root = root
        self._source = path.read_text(encoding=ENCODING)

    def findings(self) -> list[dict]:
        return self._file_length() + self._definition_findings() + self._comments()

    def _file_length(self) -> list[dict]:
        lines = len(self._source.splitlines())
        if lines <= MAX_FILE_LINES:
            return []
        return [self._finding(1, MEASURE_LONG_FILE, f"{lines} lines")]

    def _definition_findings(self) -> list[dict]:
        tree = ast.parse(self._source)
        return [finding for node in ast.walk(tree) for finding in self._of_node(node)]

    def _of_node(self, node: ast.AST) -> list[dict]:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._of_function(node)
        if isinstance(node, (ast.Module, ast.ClassDef)) and ast.get_docstring(node):
            return [self._finding(getattr(node, "lineno", 1), MEASURE_DOCSTRING, self._name_of(node))]
        return []

    def _of_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
        findings = []
        length = node.end_lineno - node.lineno + 1
        if length > MAX_FUNCTION_LINES:
            findings.append(self._finding(node.lineno, MEASURE_LONG_FUNCTION, f"{node.name}, {length} lines"))
        if ast.get_docstring(node):
            findings.append(self._finding(node.lineno, MEASURE_DOCSTRING, node.name))
        return findings

    def _comments(self) -> list[dict]:
        numbered = enumerate(self._source.splitlines(), start=1)
        return [self._finding(number, MEASURE_COMMENT, line.strip())
                for number, line in numbered if line.lstrip().startswith(_COMMENT_MARK)]

    def _finding(self, line: int, measure: str, detail: str) -> dict:
        return Row(measure, RepositoryPath(self._path, self._root).label(), line, detail).as_dict()

    @staticmethod
    def _name_of(node: ast.AST) -> str:
        return getattr(node, "name", MODULE_NAME)

