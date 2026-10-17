from __future__ import annotations

import re
import time
from pathlib import Path

from agent_core._audit.history import Git, GitUnavailable
from agent_core._audit.rows import Row
from agent_core._audit.scope import RepositoryPath
from agent_core._audit.text import MarkdownFile, masked

TIME_WORDS = re.compile(r"\b(?:currently|now|still|empty)\b", re.IGNORECASE)
NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
                "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
                "twenty")
COUNTED_UNITS = re.compile(rf"\b(\d+|{'|'.join(NUMBER_WORDS)})\s+(skills|workers)\b", re.IGNORECASE)
UNIT_PATTERNS = {"skills": ".claude/skills/*/SKILL.md", "workers": ".claude/agents/*.md"}
STALE_AFTER_DAYS = 30
SECONDS_PER_DAY = 86400
RULE_TIME_WORD = "time-word"
RULE_COUNT = "count-differs"


class StalenessCheck:
    name = "staleness"

    def __init__(self, instructions: list[Path], contract: list[Path], root: Path) -> None:
        self._instructions = [path for path in instructions if path.suffix == ".md"]
        self._contract = [path for path in contract if path.suffix == ".md"]
        self._root = root
        self._now = time.time()

    def rows(self) -> list[dict]:
        return self._time_words() + self._counts()

    def _time_words(self) -> list[dict]:
        git = Git(self._root)
        if not git.is_a_repository():
            return []
        return [row for path in self._instructions for row in self._aged(path, git)]

    def _aged(self, path: Path, git: Git) -> list[dict]:
        lines = MarkdownFile(path).lines
        hits = [(number, match.group(0)) for number, line in enumerate(lines, start=1)
                for match in TIME_WORDS.finditer(masked(line))]
        if not hits:
            return []
        try:
            times = git.line_times(path)
        except GitUnavailable:
            return []
        label = RepositoryPath(path, self._root).label()
        return [Row(RULE_TIME_WORD, label, number, f"{word}: unchanged for {self._age(times[number - 1])} days")
                .as_dict() for number, word in hits if number <= len(times) and self._is_stale(times[number - 1])]

    def _age(self, written: int) -> int:
        return int((self._now - written) / SECONDS_PER_DAY)

    def _is_stale(self, written: int) -> bool:
        return self._age(written) >= STALE_AFTER_DAYS

    def _counts(self) -> list[dict]:
        on_disk = {unit: len(list(self._root.glob(pattern))) for unit, pattern in UNIT_PATTERNS.items()}
        rows = []
        for path in self._contract:
            label = RepositoryPath(path, self._root).label()
            for number, line in enumerate(MarkdownFile(path).lines, start=1):
                rows += [Row(RULE_COUNT, label, number, f"{match.group(0)}; the control plane holds "
                             f"{on_disk[match.group(2).lower()]}").as_dict()
                         for match in COUNTED_UNITS.finditer(masked(line))
                         if self._value(match.group(1)) != on_disk[match.group(2).lower()]]
        return rows

    @staticmethod
    def _value(numeral: str) -> int:
        return int(numeral) if numeral.isdigit() else NUMBER_WORDS.index(numeral.lower())
