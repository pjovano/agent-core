from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.history import BASELINE_LABEL, RECORD_SEPARATOR, Git, GitUnavailable
from agent_core._audit.rows import Row
from agent_core._audit.scope import ENCODING, RepositoryPath
from agent_core._audit.trailers import CommitClass

CONSTANT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
INPUT_VALUE = re.compile(r"\d|/|\w\.\w")
COMPARISONS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)
COLLECTIONS = (ast.Tuple, ast.List, ast.Set)
GROWN_IN_COMMITS = 2
COMMIT_LINE = 1
RULE_LITERAL = "literal-comparison"
RULE_CONSTANT = "constant-changed"
RULE_ENUMERATION = "enumeration-grew"
RULE_TRAILER = "commit-without-trailer"


def git_label(path: Path, root: Path) -> str:
    resolved, resolved_root = path.resolve(), root.resolve()
    if resolved.is_relative_to(resolved_root):
        return resolved.relative_to(resolved_root).as_posix()
    return RepositoryPath(path, root).label()


def source_of(path: Path) -> str | None:
    try:
        return path.read_text(encoding=ENCODING)
    except (OSError, UnicodeDecodeError):
        return None


class ModuleValues:
    def __init__(self, source: str | None) -> None:
        self.tree = self._parsed(source)

    @staticmethod
    def _parsed(source: str | None) -> ast.Module | None:
        if source is None:
            return None
        try:
            return ast.parse(source)
        except (SyntaxError, ValueError):
            return None

    def constants(self) -> dict[str, tuple[int, object]]:
        return {name: (node.lineno, value) for name, node in self._assignments()
                if (value := self._literal(node.value)) is not None}

    def enumerations(self) -> dict[str, tuple[int, int]]:
        sizes = {}
        for name, node in self._assignments():
            if isinstance(node.value, COLLECTIONS):
                sizes[name] = (node.lineno, len(node.value.elts))
            elif isinstance(node.value, ast.Dict):
                sizes[name] = (node.lineno, len(node.value.keys))
        return sizes

    def _assignments(self) -> list[tuple[str, ast.Assign]]:
        if self.tree is None:
            return []
        return [(node.targets[0].id, node) for node in self.tree.body if isinstance(node, ast.Assign)
                and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and CONSTANT_NAME.match(node.targets[0].id)]

    @staticmethod
    def _literal(value: ast.expr) -> object | None:
        if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
            inner = ModuleValues._literal(value.operand)
            return None if inner is None else -inner
        if isinstance(value, ast.Constant) and isinstance(value.value, (int, float, str)) \
                and not isinstance(value.value, bool):
            return value.value
        return None


@dataclass(frozen=True)
class CodeFiles:
    pipeline: list[Path]
    tests: list[Path]
    root: Path


class SpecialCheck:
    name = "special"

    def __init__(self, code: CodeFiles) -> None:
        self._code = code
        self._git = Git(code.root)

    def rows(self) -> list[dict]:
        rows = [row for path in self._code.pipeline for row in LiteralComparisons(path, self._code.root).rows()]
        if not self._git.is_a_repository():
            return rows
        try:
            return rows + self._history_rows()
        except GitUnavailable:
            return rows

    def _history_rows(self) -> list[dict]:
        baseline = self._git.last_change_of(BASELINE_LABEL)
        rows = CommitTrailers(self._git).rows()
        if baseline is None:
            return rows
        return ChangedConstants(self._code, baseline).rows() + GrownEnumerations(self._code, baseline).rows() + rows


class LiteralComparisons:
    def __init__(self, path: Path, root: Path) -> None:
        self._path = path
        self._label = RepositoryPath(path, root).label()

    def rows(self) -> list[dict]:
        tree = ModuleValues(source_of(self._path)).tree
        if tree is None:
            return []
        return [Row(RULE_LITERAL, self._label, node.lineno, f"compares with {value!r}").as_dict()
                for node in ast.walk(tree) if isinstance(node, ast.Compare)
                and any(isinstance(operator, COMPARISONS) for operator in node.ops)
                for value in self._input_values(node)]

    @staticmethod
    def _input_values(node: ast.Compare) -> list[str]:
        operands = [node.left, *node.comparators]
        literals = [element for operand in operands
                    for element in (operand.elts if isinstance(operand, COLLECTIONS) else [operand])]
        return [literal.value for literal in literals if isinstance(literal, ast.Constant)
                and isinstance(literal.value, str) and INPUT_VALUE.search(literal.value)]


class ChangedConstants:
    def __init__(self, code: CodeFiles, baseline: str) -> None:
        self._pipeline = code.pipeline
        self._tests = code.tests
        self._root = code.root
        self._baseline = baseline

    def rows(self) -> list[dict]:
        labels = [git_label(path, self._root) for path in self._pipeline]
        earlier = Git(self._root).blobs([f"{self._baseline}:{label}" for label in labels])
        test_text = "\n".join(source_of(path) or "" for path in self._tests)
        return [row for path, before in zip(self._pipeline, earlier)
                for row in self._of_file(path, before, test_text) if before is not None]

    def _of_file(self, path: Path, before: str, test_text: str) -> list[dict]:
        old = ModuleValues(before).constants()
        new = ModuleValues(source_of(path)).constants()
        label = RepositoryPath(path, self._root).label()
        return [Row(RULE_CONSTANT, label, line, f"{name}: {old[name][1]!r} → {value!r}; "
                    f"{self._pinning(name, test_text)}").as_dict()
                for name, (line, value) in new.items() if name in old and old[name][1] != value]

    @staticmethod
    def _pinning(name: str, test_text: str) -> str:
        return "a test names it" if re.search(rf"\b{name}\b", test_text) else "no test names it"


class GrownEnumerations:
    def __init__(self, code: CodeFiles, baseline: str) -> None:
        self._pipeline = {git_label(path, code.root): path for path in code.pipeline}
        self._root = code.root
        self._baseline = baseline
        self._git = Git(code.root)

    def rows(self) -> list[dict]:
        touched = self._touched()
        rows = []
        for label, commits in touched.items():
            rows += self._of_file(label, commits)
        return rows

    def _touched(self) -> dict[str, list[str]]:
        log = self._git.output("log", "--reverse", "--no-merges", f"--format={RECORD_SEPARATOR}%H",
                               "--name-only", f"{self._baseline}..HEAD")
        touched = defaultdict(list)
        for record in log.split(RECORD_SEPARATOR):
            lines = [line.strip() for line in record.splitlines() if line.strip()]
            for label in lines[1:]:
                if label in self._pipeline:
                    touched[label].append(lines[0])
        return touched

    def _of_file(self, label: str, commits: list[str]) -> list[dict]:
        versions = self._git.blobs([f"{revision}:{label}" for revision in [self._baseline, *commits]])
        sizes = [ModuleValues(version).enumerations() for version in versions]
        grown = defaultdict(int)
        for before, after in zip(sizes, sizes[1:]):
            for name, (_line, size) in after.items():
                if name in before and size > before[name][1]:
                    grown[name] += 1
        current = ModuleValues(source_of(self._pipeline[label])).enumerations()
        path_label = RepositoryPath(self._pipeline[label], self._root).label()
        return [Row(RULE_ENUMERATION, path_label, current[name][0], f"{name} grew in {count} commits since the "
                    f"baseline").as_dict() for name, count in grown.items()
                if count >= GROWN_IN_COMMITS and name in current]


class CommitTrailers:
    def __init__(self, git: Git) -> None:
        self._git = git

    def rows(self) -> list[dict]:
        return [Row(RULE_TRAILER, commit.sha, COMMIT_LINE, commit.subject).as_dict()
                for commit in self._git.commits()
                if not commit.is_a_merge and not CommitClass(commit.message).carries_a_trailer()]
