from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from agent_core._audit.scope import ENCODING

FRONTMATTER_FENCE = "---"
CODE_FENCES = ("```", "~~~")
HEADING_MARK = "#"
TABLE_MARK = "|"
SKIPPED_LINE_MARKS = ("<!--", "%%")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
NUMBERED_MARK = re.compile(r"^\s*\d+\.$")
CODE_SPAN = re.compile(r"`[^`]*`")
LINK_TARGET = re.compile(r"\]\([^)]*\)")
SENTENCE_END = re.compile(r"[.?!][*_)\"'’”]*(?=\s|$)")
CELL_SEPARATOR = re.compile(r"(?<!\\)\|")
SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
FIELD = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
QUOTES = "\"'"
MASK = "C"
MARKUP = "*_~"
DESCRIPTION_FIELD = "description"
FENCE_LINES = 2
HEADER_LINES = 2
JOINER = "\u2060"


def has_a_letter_or_digit(token: str) -> bool:
    return any(character.isalnum() for character in token)


def masked(text: str) -> str:
    return CODE_SPAN.sub(lambda span: MASK * len(span.group(0)), text)


class FileWords:
    def __init__(self, text: str) -> None:
        self._text = text

    def count(self) -> int:
        tokens = LINK_TARGET.sub("]", self._text).split()
        return sum(1 for token in tokens if has_a_letter_or_digit(token) and not NUMBERED_MARK.match(token))


@dataclass(frozen=True)
class Sentence:
    text: str
    line: int

    @property
    def masked(self) -> str:
        return masked(self.text)

    def bare(self) -> str:
        return self.masked.strip(MARKUP + " ").lstrip(MARKUP)

    def words(self, names: TechnicalNames) -> list[str]:
        merged = names.merged(self.masked)
        return [token.strip(MARKUP) for token in merged.split() if has_a_letter_or_digit(token)]


@dataclass(frozen=True)
class Block:
    kind: str
    lines: tuple[tuple[int, str], ...]

    @property
    def line(self) -> int:
        return self.lines[0][0]

    def sentences(self) -> list[Sentence]:
        text, starts = self._joined()
        found, begin = [], 0
        for end in [match.end() for match in SENTENCE_END.finditer(masked(text))] + [len(text)]:
            piece = text[begin:end]
            if piece.strip():
                found.append(Sentence(piece.strip(), self._line_at(begin + self._lead(piece), starts)))
            begin = end
        return found

    def _joined(self) -> tuple[str, list[tuple[int, int]]]:
        pieces, starts, offset = [], [], 0
        for number, line in self.lines:
            content = LIST_ITEM.sub("", line, count=1) if not pieces else line.strip()
            starts.append((offset, number))
            pieces.append(content.strip())
            offset += len(pieces[-1]) + 1
        return " ".join(pieces), starts

    @staticmethod
    def _lead(piece: str) -> int:
        return len(piece) - len(piece.lstrip())

    @staticmethod
    def _line_at(offset: int, starts: list[tuple[int, int]]) -> int:
        return [number for start, number in starts if start <= offset][-1]


@dataclass(frozen=True)
class TableRow:
    line: int
    cells: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    header: tuple[str, ...]
    rows: tuple[TableRow, ...]
    headings: tuple[str, ...]

    def column(self, name: str) -> int | None:
        return self.header.index(name) if name in self.header else None

    def holds(self, names: tuple[str, ...]) -> bool:
        return all(name in self.header for name in names)

    def is_under(self, section: str) -> bool:
        return not section or section in self.headings

    def cells_of(self, name: str) -> list[tuple[int, str]]:
        column = self.column(name)
        if column is None:
            return []
        return [(row.line, row.cells[column]) for row in self.rows if column < len(row.cells)]


class MarkdownFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    @cached_property
    def lines(self) -> list[str]:
        try:
            return self._path.read_text(encoding=ENCODING).splitlines()
        except (OSError, UnicodeDecodeError):
            return []

    def description(self) -> str:
        return self.frontmatter.get(DESCRIPTION_FIELD, (0, ""))[1]

    @cached_property
    def frontmatter(self) -> dict[str, tuple[int, str]]:
        fields = {}
        for number, line in self._frontmatter_lines():
            match = FIELD.match(line)
            if match:
                fields[match.group(1)] = (number, match.group(2).strip().strip(QUOTES))
        return fields

    def blocks(self) -> list[Block]:
        return BlockReader(self._body()).blocks()

    def tables(self) -> list[Table]:
        return TableReader(self._body()).tables()

    def _frontmatter_lines(self) -> list[tuple[int, str]]:
        if not self.lines or self.lines[0].strip() != FRONTMATTER_FENCE:
            return []
        closing = next((index for index in range(1, len(self.lines))
                        if self.lines[index].strip() == FRONTMATTER_FENCE), None)
        return [] if closing is None else [(index + 1, self.lines[index]) for index in range(1, closing)]

    def _body(self) -> list[tuple[int, str]]:
        numbered = list(enumerate(self.lines, start=1))
        skipped = self._frontmatter_lines()
        return numbered[len(skipped) + FENCE_LINES:] if skipped else numbered


class MarkdownText(MarkdownFile):
    def __init__(self, text: str) -> None:
        super().__init__(Path())
        self._text = text

    @cached_property
    def lines(self) -> list[str]:
        return self._text.splitlines()


class BlockReader:
    def __init__(self, numbered: list[tuple[int, str]]) -> None:
        self._numbered = numbered

    def blocks(self) -> list[Block]:
        blocks, current, fenced = [], [], False
        for number, line in self._numbered:
            stripped = line.strip()
            if stripped.startswith(CODE_FENCES):
                fenced = not fenced
            if fenced or self._ends_a_block(stripped):
                current = self._closed(current, blocks)
                continue
            if LIST_ITEM.match(line):
                current = self._closed(current, blocks)
            current.append((number, line))
        self._closed(current, blocks)
        return blocks

    @staticmethod
    def _ends_a_block(stripped: str) -> bool:
        return (not stripped or stripped.startswith((HEADING_MARK, TABLE_MARK, *SKIPPED_LINE_MARKS))
                or stripped.startswith(CODE_FENCES))

    @staticmethod
    def _closed(current: list[tuple[int, str]], blocks: list[Block]) -> list[tuple[int, str]]:
        if current:
            kind = "item" if LIST_ITEM.match(current[0][1]) else "paragraph"
            blocks.append(Block(kind, tuple(current)))
        return []


class TableReader:
    def __init__(self, numbered: list[tuple[int, str]]) -> None:
        self._numbered = numbered

    def tables(self) -> list[Table]:
        tables, run, trail = [], [], HeadingTrail()
        for number, line in self._numbered:
            stripped = line.strip()
            trail.follow(stripped)
            if stripped.startswith(TABLE_MARK):
                run.append(TableRow(number, self._cells(stripped)))
                continue
            self._kept(run, trail.headings(), tables)
            run = []
        self._kept(run, trail.headings(), tables)
        return tables

    @staticmethod
    def _cells(line: str) -> tuple[str, ...]:
        cells = CELL_SEPARATOR.split(line.strip().strip(TABLE_MARK))
        return tuple(cell.strip() for cell in cells)

    @staticmethod
    def _kept(run: list[TableRow], headings: tuple[str, ...], tables: list[Table]) -> None:
        if len(run) < HEADER_LINES or not all(SEPARATOR_CELL.match(cell) for cell in run[1].cells):
            return
        tables.append(Table(run[0].cells, tuple(run[HEADER_LINES:]), headings))


class HeadingTrail:
    def __init__(self) -> None:
        self._trail: list[tuple[int, str]] = []

    def follow(self, stripped: str) -> None:
        if not stripped.startswith(HEADING_MARK):
            return
        level = len(stripped) - len(stripped.lstrip(HEADING_MARK))
        self._trail = [(depth, text) for depth, text in self._trail if depth < level] + [(level, stripped)]

    def headings(self) -> tuple[str, ...]:
        return tuple(text for _depth, text in self._trail)


class TechnicalNames:
    def __init__(self, names: list[str]) -> None:
        spaced = sorted({name for name in names if " " in name}, key=len, reverse=True)
        self._pattern = re.compile("|".join(rf"\b{re.escape(name)}\b" for name in spaced), re.IGNORECASE) \
            if spaced else None
        self._names = {name.lower() for name in names}

    def merged(self, text: str) -> str:
        if self._pattern is None:
            return text
        return self._pattern.sub(lambda match: match.group(0).replace(" ", JOINER), text)

    def holds(self, word: str) -> bool:
        return word.replace(JOINER, " ").lower() in self._names
