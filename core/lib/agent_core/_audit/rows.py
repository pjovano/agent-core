from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.scope import ENCODING

FINGERPRINT_LENGTH = 16
FINGERPRINT_KEY = "fingerprint"
RULE_KEY = "rule"
FORMER_RULE_KEYS = ("finding", "measure")
FIELD_SEPARATOR = "\n"


@dataclass(frozen=True)
class Row:
    rule: str
    file: str
    line: int
    detail: str

    def as_dict(self) -> dict:
        return {"rule": self.rule, "file": self.file, "line": self.line, "detail": self.detail}


class Fingerprint:
    def __init__(self, rule: str, file: str, text: str) -> None:
        self._fields = (rule, file, " ".join(text.split()))

    def text(self) -> str:
        digest = hashlib.sha256(FIELD_SEPARATOR.join(self._fields).encode(ENCODING)).hexdigest()
        return digest[:FINGERPRINT_LENGTH]


class Fingerprints:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._lines: dict[str, list[str]] = {}

    def stamped(self, rows: list) -> list:
        return [self._stamped(row) if self._is_a_row(row) else row for row in rows]

    @staticmethod
    def _is_a_row(row: object) -> bool:
        return isinstance(row, dict) and "file" in row and "line" in row

    def _stamped(self, row: dict) -> dict:
        rule = next((str(row[key]) for key in (RULE_KEY, *FORMER_RULE_KEYS) if key in row), "")
        detail = str(row.get("detail", ""))
        ordered = {"rule": rule, "file": row["file"], "line": row["line"], "detail": detail}
        extra = {key: value for key, value in row.items() if key not in (*ordered, *FORMER_RULE_KEYS)}
        fingerprint = Fingerprint(rule, str(row["file"]), self._text_of(row, detail)).text()
        return {**ordered, **extra, FINGERPRINT_KEY: fingerprint}

    def _text_of(self, row: dict, detail: str) -> str:
        lines = self._file_lines(str(row["file"]))
        number = row["line"]
        if lines is None or not isinstance(number, int) or not 1 <= number <= len(lines):
            return detail
        return lines[number - 1]

    def _file_lines(self, label: str) -> list[str] | None:
        if label not in self._lines:
            path = self._root / label
            try:
                self._lines[label] = path.read_text(encoding=ENCODING).splitlines() if path.is_file() else None
            except (OSError, UnicodeDecodeError, ValueError):
                self._lines[label] = None
        return self._lines[label]


class Acknowledged:
    def __init__(self, fingerprints: dict[str, str]) -> None:
        self._fingerprints = fingerprints

    def unacknowledged(self, rows: list) -> list:
        return [row for row in rows if not (isinstance(row, dict) and row.get(FINGERPRINT_KEY) in self._fingerprints)]
