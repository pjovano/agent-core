from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.text import CODE_SPAN, MarkdownFile, Table, TechnicalNames

GLOSSARY_PATH = Path(".claude") / "glossary.md"
CORE_VOCABULARY_PATH = Path(".claude") / "skills" / "clean-prose" / "SKILL.md"
TERM_COLUMN = "Term"
SYNONYM_COLUMNS = ("Banned synonyms", "Not")
SENSE = re.compile(r"\s*\((?:for (?:the |a |an )?(?P<sense>[^)]+)|(?P<alone>alone))\)\s*$")
EMPTY_CELL = "—"
SYNONYM_SEPARATOR = ","
CODE_MARK = "`"
SENSE_WORD = re.compile(r"[a-z]{4,}")
DETERMINERS = "a|an|the|each|every|this|that|these|those|its|their|one|no|any|another|our|your"


@dataclass(frozen=True)
class Synonym:
    word: str
    term: str
    sense: str | None
    alone: bool

    def pattern(self) -> re.Pattern:
        return re.compile(rf"(?<![\w-])(?:{DETERMINERS})\s+(?P<word>{re.escape(self.word)})(?![\w-])", re.IGNORECASE)

    def sense_is_in(self, lowered: str) -> bool:
        if self.sense is None:
            return True
        return any(word in lowered for word in SENSE_WORD.findall(self.sense.lower()))

    def detail(self) -> str:
        if self.sense is not None:
            return f"{self.word}: write {self.term}; low confidence: banned only for the {self.sense}"
        return f"{self.word}: write {self.term}"


class Glossary:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._domain = MarkdownFile(root / GLOSSARY_PATH)
        self._core = MarkdownFile(root / CORE_VOCABULARY_PATH)

    @property
    def path(self) -> Path:
        return self._root / GLOSSARY_PATH

    def technical_names(self) -> TechnicalNames:
        tables = self._term_tables(self._domain) + self._term_tables(self._core)
        return TechnicalNames([self._term(row.cells[table.column(TERM_COLUMN)])
                               for table in tables for row in table.rows])

    def synonyms(self) -> list[Synonym]:
        return [synonym for table in self._synonym_tables() for row in table.rows
                for synonym in self._of_row(row.cells, table)]

    def table_lines(self) -> set[int]:
        return {row.line for table in self._domain.tables() for row in table.rows}

    @staticmethod
    def _term_tables(markdown: MarkdownFile) -> list[Table]:
        return [table for table in markdown.tables() if table.column(TERM_COLUMN) == 0]

    def _synonym_tables(self) -> list[Table]:
        return [table for table in self._term_tables(self._domain) if self._synonym_column(table) is not None]

    @staticmethod
    def _synonym_column(table: Table) -> int | None:
        return next((table.column(name) for name in SYNONYM_COLUMNS if table.column(name) is not None), None)

    def _of_row(self, cells: tuple[str, ...], table: Table) -> list[Synonym]:
        column = self._synonym_column(table)
        if column >= len(cells) or cells[column] in ("", EMPTY_CELL):
            return []
        term = self._term(cells[0])
        return [self._synonym(entry.strip(), term) for entry in cells[column].split(SYNONYM_SEPARATOR)
                if entry.strip()]

    @staticmethod
    def _synonym(entry: str, term: str) -> Synonym:
        qualifier = SENSE.search(entry)
        word = entry[:qualifier.start()].strip() if qualifier else entry
        sense = qualifier.group("sense") if qualifier else None
        return Synonym(word.strip(CODE_MARK), term, sense, bool(qualifier and qualifier.group("alone")))

    @staticmethod
    def _term(cell: str) -> str:
        return CODE_SPAN.sub(lambda span: span.group(0).strip(CODE_MARK), cell).strip()
