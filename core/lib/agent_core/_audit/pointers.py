from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from agent_core._audit.scope import ENCODING, ControlPlaneFiles, RepositoryPath

BACKTICKED = re.compile(r"`([^`\n]+)`")
DATED = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
FINDING_MISSING_PATH = "path-does-not-exist"
FINDING_FUTURE_DATE = "date-in-the-future"


class InstructionPointers:
    def __init__(self, paths: list[Path], files: ControlPlaneFiles, today: date | None = None) -> None:
        self._paths = paths
        self._files = files
        self._today = date.today() if today is None else today

    def findings(self) -> list[dict]:
        return [finding for path in self._paths
                for finding in FilePointers(path, self._files, self._today).findings()]


class FilePointers:
    def __init__(self, path: Path, files: ControlPlaneFiles, today: date) -> None:
        self._path = path
        self._files = files
        self._today = today

    def findings(self) -> list[dict]:
        numbered = list(enumerate(self._path.read_text(encoding=ENCODING).splitlines(), start=1))
        return self._missing_paths(numbered) + self._future_dates(numbered)

    def _missing_paths(self, numbered: list[tuple[int, str]]) -> list[dict]:
        return [self._finding(number, FINDING_MISSING_PATH, token)
                for number, line in numbered for token in BACKTICKED.findall(line)
                if NamedPath(token, self._files).is_missing()]

    def _future_dates(self, numbered: list[tuple[int, str]]) -> list[dict]:
        return [self._finding(number, FINDING_FUTURE_DATE, match.group(0))
                for number, line in numbered for match in DATED.finditer(line)
                if self._is_future(match.group(0))]

    def _is_future(self, stamp: str) -> bool:
        try:
            return date.fromisoformat(stamp) > self._today
        except ValueError:
            return False

    def _finding(self, line: int, finding: str, detail: str) -> dict:
        return {"file": RepositoryPath(self._path, self._files.root).label(), "line": line, "finding": finding,
                "detail": detail}


class NamedPath:
    def __init__(self, token: str, files: ControlPlaneFiles) -> None:
        self._scope = files.scope
        self._root = files.root
        self._token = self._scope.first_field(token.strip())

    def is_missing(self) -> bool:
        return self._scope.names_a_path(self._token) and not self._scope.located(self._token, self._root).exists()
