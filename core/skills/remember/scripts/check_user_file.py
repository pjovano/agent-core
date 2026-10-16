from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

MAX_LINES = 150
SECTION_MARK = "## "
RECENT_HEADING = "## Recent"
DATED_ENTRY = re.compile(r"^- (\d{4}-\d{2}-\d{2})(?!\d)")
CONTINUATION_INDENT = (" ", "\t")
ENCODING = "utf-8"
EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
USAGE = "usage: check_user_file.py <path of USER.md>"


@dataclass(frozen=True)
class Finding:
    line: int
    reason: str


class UserFile:
    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()

    def line_count(self) -> int:
        return len(self._lines)

    def findings(self) -> list[Finding]:
        return self._past_cap() + self._undated_entries()

    def _past_cap(self) -> list[Finding]:
        if self.line_count() <= MAX_LINES:
            return []
        return [Finding(self.line_count(), f"the file holds {self.line_count()} lines, past its cap of {MAX_LINES}")]

    def _undated_entries(self) -> list[Finding]:
        return [Finding(number, f"the recent entry does not open with a date: {line.strip()}")
                for number, line in self._recent_entries() if not RecentEntry(line).is_dated()]

    def _recent_entries(self) -> list[tuple[int, str]]:
        entries, inside_recent = [], False
        for number, line in enumerate(self._lines, start=1):
            if line.startswith(SECTION_MARK):
                inside_recent = line.strip() == RECENT_HEADING
            elif inside_recent and RecentEntry(line).opens_an_entry():
                entries.append((number, line))
        return entries


class RecentEntry:
    def __init__(self, line: str) -> None:
        self._line = line

    def opens_an_entry(self) -> bool:
        return bool(self._line.strip()) and not self._line.startswith(CONTINUATION_INDENT)

    def is_dated(self) -> bool:
        match = DATED_ENTRY.match(self._line)
        return match is not None and self._is_calendar_date(match.group(1))

    @staticmethod
    def _is_calendar_date(stamp: str) -> bool:
        try:
            date.fromisoformat(stamp)
        except ValueError:
            return False
        return True


class CheckCommand:
    def __init__(self, arguments: list[str]) -> None:
        self._arguments = arguments

    def run(self) -> int:
        if len(self._arguments) != 1:
            print(USAGE, file=sys.stderr)
            return EXIT_USAGE
        return self._checked(Path(self._arguments[0]))

    def _checked(self, path: Path) -> int:
        try:
            user_file = UserFile(path.read_text(encoding=ENCODING))
        except OSError as error:
            print(f"{path}: cannot be read: {error.strerror}", file=sys.stderr)
            return EXIT_FAILED
        return self._reported(path, user_file)

    @staticmethod
    def _reported(path: Path, user_file: UserFile) -> int:
        findings = user_file.findings()
        for finding in findings:
            print(f"{path}:{finding.line}: {finding.reason}")
        if findings:
            return EXIT_FAILED
        print(f"{path}: passes, {user_file.line_count()} lines")
        return EXIT_PASSED


if __name__ == "__main__":
    sys.exit(CheckCommand(sys.argv[1:]).run())
