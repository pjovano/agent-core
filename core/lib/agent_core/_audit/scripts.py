from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.scope import ENCODING, RepositoryPath

PARSER_METHOD = "add_parser"
PACKAGE_PREFIX = "_"
PYTHON_SUFFIX = ".py"


@dataclass(frozen=True)
class Subcommand:
    name: str
    file: str
    line: int


@dataclass(frozen=True)
class Vocabulary:
    names: frozenset[str]
    closed: bool
    defined: tuple[Subcommand, ...] = ()


class ScriptVocabularies:
    def __init__(self, code: list[Path], root: Path, known: dict[str, frozenset[str]]) -> None:
        self._code = code
        self._root = root
        self._known = known
        self._parsed = {path: ParserCalls(path, root) for path in code}

    def of_basename(self, basename: str) -> Vocabulary | None:
        scripts = [path for path in self._code if path.name == basename]
        if not scripts:
            return None
        vocabularies = [self.of_script(path) for path in scripts]
        names = frozenset(name for vocabulary in vocabularies for name in vocabulary.names)
        return Vocabulary(names, all(vocabulary.closed for vocabulary in vocabularies))

    def of_script(self, script: Path) -> Vocabulary:
        label = RepositoryPath(script, self._root).label()
        if label in self._known:
            return Vocabulary(self._known[label], closed=True)
        calls = [self._parsed[path] for path in self._family(script)]
        defined = tuple(subcommand for call in calls for subcommand in call.literal)
        closed = bool(defined) and not any(call.dynamic for call in calls)
        return Vocabulary(frozenset(subcommand.name for subcommand in defined), closed, defined)

    def defined_by(self, basename: str) -> list[Subcommand]:
        vocabularies = [self.of_script(path) for path in self._code if path.name == basename]
        if not vocabularies or not all(vocabulary.closed for vocabulary in vocabularies):
            return []
        return [subcommand for vocabulary in vocabularies for subcommand in vocabulary.defined]

    def defined(self) -> list[Subcommand]:
        return [subcommand for calls in self._parsed.values() for subcommand in calls.literal]

    def _family(self, script: Path) -> list[Path]:
        package = script.parent / (PACKAGE_PREFIX + script.stem)
        return [script] + [path for path in self._code if path.parent == package]


class ParserCalls:
    def __init__(self, path: Path, root: Path) -> None:
        self._label = RepositoryPath(path, root).label()
        self.literal: list[Subcommand] = []
        self.dynamic = False
        self._read(path)

    def _read(self, path: Path) -> None:
        try:
            tree = ast.parse(path.read_text(encoding=ENCODING))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            return
        for node in ast.walk(tree):
            if self._is_a_parser_call(node):
                self._record(node)

    @staticmethod
    def _is_a_parser_call(node: ast.AST) -> bool:
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == PARSER_METHOD)

    def _record(self, node: ast.Call) -> None:
        first = node.args[0] if node.args else None
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            self.literal.append(Subcommand(first.value, self._label, node.lineno))
        else:
            self.dynamic = True
