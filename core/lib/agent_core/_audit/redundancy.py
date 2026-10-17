from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from itertools import combinations
from pathlib import Path

from agent_core._audit.rows import Row
from agent_core._audit.scope import RepositoryPath
from agent_core._audit.text import MarkdownFile, masked

SHINGLE_WORDS = 3
SHORTEST_SENTENCE = 6
DRIFT_OVERLAP = 0.5
COMMON_SHINGLE = 12
PAIR = 2
WORD = re.compile(r"[\w'’-]+")
RULE_DRIFTED = "drifted-duplicate"


@dataclass(frozen=True)
class CopyGroup:
    paths: list[Path]
    crosses_a_boundary: bool = False


@dataclass(frozen=True)
class Copy:
    label: str
    line: int
    words: tuple[str, ...]
    group: CopyGroup

    @cached_property
    def shingles(self) -> frozenset[tuple[str, ...]]:
        return frozenset(tuple(self.words[index:index + SHINGLE_WORDS])
                         for index in range(len(self.words) - SHINGLE_WORDS + 1))

    def drifts_from(self, other: Copy) -> bool:
        if self.label == other.label or self.words == other.words:
            return False
        if self.group.crosses_a_boundary or other.group.crosses_a_boundary:
            return False
        return len(self.shingles & other.shingles) / len(self.shingles | other.shingles) >= DRIFT_OVERLAP


class RedundancyCheck:
    name = "redundancy"

    def __init__(self, groups: list[CopyGroup], root: Path) -> None:
        self._groups = groups
        self._root = root

    def rows(self) -> list[dict]:
        return [self._row(later, earlier) for earlier, later in self._drifted(self._copies())]

    def _copies(self) -> list[Copy]:
        return [copy for group in self._groups for path in sorted(group.paths) for copy in self._of_file(path, group)]

    def _of_file(self, path: Path, group: CopyGroup) -> list[Copy]:
        label = RepositoryPath(path, self._root).label()
        sentences = [sentence for block in MarkdownFile(path).blocks() for sentence in block.sentences()]
        copies = [Copy(label, sentence.line, tuple(WORD.findall(masked(sentence.text).lower())), group)
                  for sentence in sentences]
        return [copy for copy in copies if len(copy.words) >= SHORTEST_SENTENCE]

    @staticmethod
    def _drifted(copies: list[Copy]) -> list[tuple[Copy, Copy]]:
        holders = defaultdict(set)
        for index, copy in enumerate(copies):
            for shingle in copy.shingles:
                holders[shingle].add(index)
        pairs = {pair for indices in holders.values() if len(indices) <= COMMON_SHINGLE
                 for pair in combinations(sorted(indices), PAIR)}
        return [(copies[first], copies[second]) for first, second in sorted(pairs)
                if copies[second].drifts_from(copies[first])]

    @staticmethod
    def _row(later: Copy, earlier: Copy) -> dict:
        return Row(RULE_DRIFTED, later.label, later.line,
                   f"differs from its copy at {earlier.label}:{earlier.line}").as_dict()
