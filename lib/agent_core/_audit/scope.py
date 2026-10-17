from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

ENCODING = "utf-8"
CONTRACT_GROUP = "contract"
INSTRUCTION_GROUPS = (CONTRACT_GROUP, "skills", "workers")
CODE_GROUPS = ("code", "tests")
PIPELINE_GROUPS = ("code",)
PLACEHOLDER_MARKS = ("<", ">", "*", "?", "|")
FIELD_SEPARATOR = " "


class NamedRoot(Protocol):
    prefix: str

    def resolved(self, token: str) -> Path: ...


class HomeRoot:
    prefix = "~/"

    def resolved(self, token: str) -> Path:
        return Path(token).expanduser()


@dataclass(frozen=True)
class Scope:
    root_files: tuple[str, ...] = ()
    patterns: dict[str, tuple[str, ...]] = field(default_factory=dict)
    path_prefixes: tuple[str, ...] = ()
    named_roots: tuple[NamedRoot, ...] = ()

    def extended_by(self, addition: Scope) -> Scope:
        return Scope(self.root_files + addition.root_files, self._patterns_with(addition),
                     self.path_prefixes + addition.path_prefixes, self.named_roots + addition.named_roots)

    def group_patterns(self) -> dict[str, tuple[str, ...]]:
        return {**self.patterns, CONTRACT_GROUP: self.root_files + self.patterns.get(CONTRACT_GROUP, ())}

    def names_a_path(self, token: str) -> bool:
        if any(mark in token for mark in PLACEHOLDER_MARKS):
            return False
        return token in self.root_files or token.startswith(self._every_prefix())

    def first_field(self, token: str) -> str:
        spaced = tuple(prefix for prefix in self._every_prefix() if FIELD_SEPARATOR in prefix)
        return token if token.startswith(spaced) else token.split(FIELD_SEPARATOR)[0]

    def located(self, token: str, root: Path) -> Path:
        named = next((named for named in self.named_roots if token.startswith(named.prefix)), None)
        return root / token if named is None else named.resolved(token)

    def _every_prefix(self) -> tuple[str, ...]:
        return self.path_prefixes + tuple(named.prefix for named in self.named_roots)

    def _patterns_with(self, addition: Scope) -> dict[str, tuple[str, ...]]:
        groups = dict(self.patterns)
        for group, patterns in addition.patterns.items():
            groups[group] = groups.get(group, ()) + patterns
        return groups


CORE_SCOPE = Scope(
    root_files=("AGENTS.md", "CLAUDE.md"),
    patterns={
        CONTRACT_GROUP: (".claude/settings.json",),
        "skills": (".claude/skills/*/SKILL.md", ".claude/skills/*/reference/*", ".claude/code-overlay.md",
                   ".claude/glossary.md"),
        "workers": (".claude/agents/*.md",),
        "code": ("lib/*.py", "lib/_*/*.py", ".claude/skills/*/scripts/*.py", ".claude/skills/*/scripts/_*/*.py",
                 "audit/*.py"),
        "tests": ("tests/*.py", "tests/*/*.py", "tests/README.md", "tests/fixtures/**/*"),
        "configuration": ("pyproject.toml", ".github/workflows/*"),
    },
    path_prefixes=(".claude/", "lib/", "tests/", "skills/", "agents/"),
    named_roots=(HomeRoot(),),
)


class ControlPlaneFiles:
    def __init__(self, root: Path, scope: Scope = CORE_SCOPE) -> None:
        self._root = root
        self._scope = scope

    @property
    def root(self) -> Path:
        return self._root

    @property
    def scope(self) -> Scope:
        return self._scope

    def groups(self) -> tuple[str, ...]:
        return tuple(self._scope.group_patterns())

    def by_group(self) -> dict[str, list[Path]]:
        return {group: self._matching(patterns) for group, patterns in self._scope.group_patterns().items()}

    def of_groups(self, groups: tuple[str, ...]) -> list[Path]:
        grouped = self.by_group()
        return [path for group in groups for path in grouped[group]]

    def all(self) -> list[Path]:
        return self.of_groups(self.groups())

    def _matching(self, patterns: tuple[str, ...]) -> list[Path]:
        found = {path for pattern in patterns for path in self._root.glob(pattern) if path.is_file()}
        return sorted(found)


class RepositoryPath:
    def __init__(self, path: Path, root: Path) -> None:
        self._path = path
        self._root = root

    def label(self) -> str:
        lexical_path = self._lexical(self._path)
        resolved_root = self._root.resolve()
        candidates = ((lexical_path, self._lexical(self._root)), (lexical_path, resolved_root),
                      (self._path.resolve(), resolved_root))
        for path, root in candidates:
            if path.is_relative_to(root):
                return path.relative_to(root).as_posix()
        return self._path.as_posix()

    @staticmethod
    def _lexical(path: Path) -> Path:
        return Path(os.path.abspath(path))
