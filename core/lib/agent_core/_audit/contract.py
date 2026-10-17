from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from agent_core._audit.scope import ENCODING, Scope
from agent_core._audit.text import CODE_SPAN, MarkdownFile, Table

CONTRACT_FILE = "AGENTS.md"
SKILL_COLUMN = "Skill"
CODE_MARK = "`"


@dataclass(frozen=True)
class ContractTables:
    file: str = CONTRACT_FILE
    section: str = ""
    columns: tuple[str, ...] = (SKILL_COLUMN,)

    def tables(self, root: Path) -> list[Table]:
        return [table for table in MarkdownFile(root / self.file).tables()
                if table.is_under(self.section) and table.holds(self.columns)]


class HookNames(Protocol):
    file: str

    def named(self, root: Path) -> dict[str, int]: ...


@dataclass(frozen=True)
class DictKeys:
    file: str
    variable: str

    def named(self, root: Path) -> dict[str, int]:
        try:
            tree = ast.parse((root / self.file).read_text(encoding=ENCODING))
        except (OSError, SyntaxError, UnicodeDecodeError):
            return {}
        values = [node.value for node in tree.body if isinstance(node, ast.Assign) and self._names_it(node)]
        return {key.value: key.lineno for value in values if isinstance(value, ast.Dict) for key in value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)}

    def _names_it(self, node: ast.Assign) -> bool:
        return any(isinstance(target, ast.Name) and target.id == self.variable for target in node.targets)


@dataclass(frozen=True)
class JsonKeys:
    file: str
    keys: tuple[str, ...]

    def named(self, root: Path) -> dict[str, int]:
        try:
            text = (root / self.file).read_text(encoding=ENCODING)
            value = json.loads(text)
        except (OSError, ValueError):
            return {}
        for key in self.keys:
            value = value.get(key, {}) if isinstance(value, dict) else {}
        lines = text.splitlines()
        return {name: self._line_of(name, lines) for name in value} if isinstance(value, dict) else {}

    @staticmethod
    def _line_of(name: str, lines: list[str]) -> int:
        quoted = json.dumps(name) + ":"
        return next((number for number, line in enumerate(lines, start=1) if quoted in line), 1)


@dataclass(frozen=True)
class HookList:
    file: str
    marker: str
    hooks: HookNames

    def named(self, root: Path, scope: Scope) -> dict[str, int]:
        markdown = MarkdownFile(root / self.file)
        sentences = [sentence for block in markdown.blocks() for sentence in block.sentences()
                     if self.marker in sentence.text]
        return {name: self._line_of(name, markdown.lines, sentence.line) for sentence in sentences
                for name in self._spans(sentence.text) if not scope.names_a_path(name)}

    @staticmethod
    def _spans(text: str) -> list[str]:
        return [span.group(0).strip(CODE_MARK) for span in CODE_SPAN.finditer(text)]

    @staticmethod
    def _line_of(name: str, lines: list[str], start: int) -> int:
        spelled = f"{CODE_MARK}{name}{CODE_MARK}"
        return next((number for number in range(start, len(lines) + 1) if spelled in lines[number - 1]), start)


@dataclass(frozen=True)
class ContractLocations:
    stage_table: ContractTables | None = None
    operation_tables: ContractTables | None = field(default_factory=ContractTables)
    hook_list: HookList | None = None

    def tables(self, root: Path) -> list[Table]:
        located = [where for where in (self.stage_table, self.operation_tables) if where is not None]
        return [table for where in located for table in where.tables(root)]

    def table_file(self) -> str:
        located = self.stage_table or self.operation_tables
        return CONTRACT_FILE if located is None else located.file


def spans_in(cell: str) -> list[str]:
    return [span.group(0).strip(CODE_MARK) for span in CODE_SPAN.finditer(cell)]


WORKER_NAMED = re.compile(r"`([a-z][a-z0-9-]*)`\s+workers?\b|\bworker\s+`([a-z][a-z0-9-]*)`")
