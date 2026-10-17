from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass

from agent_core._audit.history import Git
from agent_core._audit.scope import CONTRACT_GROUP, INSTRUCTION_GROUPS, ControlPlaneFiles, Scope
from agent_core._audit.trailers import GROWING_CLASSES, CommitClass
from agent_core._audit.weight import (
    ALWAYS_LOADED,
    GROUP_NAMES,
    INSTRUCTION_SUFFIX,
    VENDORED_CORE,
    InstructionTexts,
)

SYMLINK_MODE = "120000"
TREE_ENTRY = re.compile(r"^(?P<mode>\d+) (?P<kind>\w+) (?P<sha>[0-9a-f]+)\t(?P<path>.*)$", re.DOTALL)
WORDS_HEADING = re.compile(r"^#+\s*Words added\s*$", re.IGNORECASE)
HEADING = re.compile(r"^#+\s")
STATED_LINE = re.compile(r"^\s*[-*]?\s*`?(?P<file>[^`:\s][^`:]*?)`?\s*:\s*\+(?P<words>\d+)\s*(?:—|–|-)\s*"
                         r"(?P<rule>\S.*)$")
SHORT_SHA = 12


class ScopePatterns:
    def __init__(self, scope: Scope) -> None:
        patterns = scope.group_patterns()
        self._groups = [(group, [self._regex(pattern) for pattern in patterns.get(group, ())])
                        for group in INSTRUCTION_GROUPS]

    def group_of(self, label: str) -> str | None:
        return next((group for group, regexes in self._groups if any(regex.match(label) for regex in regexes)), None)

    @staticmethod
    def _regex(pattern: str) -> re.Pattern:
        escaped = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
        return re.compile(rf"^{escaped}$")


class TreeInstructions:
    def __init__(self, git: Git, scope: Scope) -> None:
        self._git = git
        self._patterns = ScopePatterns(scope)
        self._words: dict[str, InstructionTexts] = {}

    def at(self, revision: str) -> InstructionTexts:
        if revision not in self._words:
            self._words[revision] = self._read(revision)
        return self._words[revision]

    def _read(self, revision: str) -> InstructionTexts:
        files, links = self._entries(revision)
        chosen, seen = {}, set()
        for label, target in self._candidates(files, links):
            group = self._patterns.group_of(label)
            if group and label.endswith(INSTRUCTION_SUFFIX) and target not in seen and \
                    not target.startswith(VENDORED_CORE):
                seen.add(target)
                chosen[label] = (files[target], group)
        texts = self._git.blobs([sha for sha, _group in chosen.values()])
        return InstructionTexts({label: text or "" for label, text in zip(chosen, texts)},
                                frozenset(label for label, (_sha, group) in chosen.items() if group == CONTRACT_GROUP))

    def _entries(self, revision: str) -> tuple[dict[str, str], dict[str, str]]:
        listing = self._git.output("ls-tree", "-r", "-z", "--full-tree", revision)
        files, link_shas = {}, {}
        for entry in listing.split("\0"):
            match = TREE_ENTRY.match(entry)
            if match and match.group("kind") == "blob":
                (link_shas if match.group("mode") == SYMLINK_MODE else files)[match.group("path")] = match.group("sha")
        targets = self._git.blobs(list(link_shas.values()))
        links = {link: posixpath.normpath(posixpath.join(posixpath.dirname(link), (target or "").strip()))
                 for link, target in zip(link_shas, targets)}
        return files, links

    @staticmethod
    def _candidates(files: dict[str, str], links: dict[str, str]) -> list[tuple[str, str]]:
        candidates = [(label, label) for label in files]
        for link, target in links.items():
            if target in files:
                candidates.append((link, target))
            prefix = target + "/"
            candidates += [(link + "/" + label[len(prefix):], label) for label in files if label.startswith(prefix)]
        return sorted(candidates, key=lambda candidate: (candidate[0] != candidate[1], candidate[0]))


@dataclass(frozen=True)
class CommitGrowth:
    sha: str
    subject: str
    kind: str
    growth: dict[str, int]

    def grows(self) -> bool:
        return any(words > 0 for words in self.growth.values())

    def grows_unwarranted(self) -> bool:
        return self.grows() and self.kind not in GROWING_CLASSES

    def as_dict(self) -> dict:
        return {"commit": self.sha, "subject": self.subject, "class": self.kind, **self.growth}


class StatedWords:
    def __init__(self, body: str) -> None:
        self._lines = self._section(body.splitlines())

    @staticmethod
    def _section(lines: list[str]) -> list[str]:
        start = next((index for index, line in enumerate(lines) if WORDS_HEADING.match(line.strip())), None)
        if start is None:
            return []
        rest = lines[start + 1:]
        end = next((index for index, line in enumerate(rest) if HEADING.match(line.strip())), len(rest))
        return rest[:end]

    def stated(self) -> dict[str, int]:
        matches = [STATED_LINE.match(line) for line in self._lines]
        return {match.group("file").strip(): int(match.group("words")) for match in matches if match}


@dataclass(frozen=True)
class PullRequest:
    base: str
    body: str


class WordRatchet:
    def __init__(self, files: ControlPlaneFiles, request: PullRequest) -> None:
        self._git = Git(files.root)
        self._tree = TreeInstructions(self._git, files.scope)
        self._base = request.base
        self._body = request.body

    def verdict(self) -> dict:
        base, head = self._tree.at(self._base).counts(), self._tree.at("HEAD").counts()
        commits = [self._growth(commit) for commit in self._git.commits(f"{self._base}..HEAD")
                   if not commit.is_a_merge]
        grown = {name: head[name] - base[name] for name in GROUP_NAMES}
        failures = [self._unclassed(commit) for commit in commits if commit.grows_unwarranted()]
        if any(words > 0 for words in grown.values()):
            failures += self._unstated(base["files"], head["files"])
        return {"base": self._base, "growth": grown, "always_loaded_first": grown[ALWAYS_LOADED],
                "commits": [commit.as_dict() for commit in commits if commit.grows()], "failures": failures}

    def _growth(self, commit) -> CommitGrowth:
        parent = commit.parents[0] if commit.parents else None
        after = self._tree.at(commit.sha).counts()
        before = self._tree.at(parent).counts() if parent else {name: 0 for name in GROUP_NAMES}
        return CommitGrowth(commit.sha, commit.subject, CommitClass(commit.message).name(),
                            {name: after[name] - before[name] for name in GROUP_NAMES})

    @staticmethod
    def _unclassed(commit: CommitGrowth) -> str:
        return (f"commit {commit.sha[:SHORT_SHA]} ({commit.kind}) grows the instruction text: only a "
                f"Change-class: feature or a Defect-class: commit may grow it")

    def _unstated(self, before: dict[str, int], after: dict[str, int]) -> list[str]:
        stated = StatedWords(self._body).stated()
        grown = {label: words - before.get(label, 0) for label, words in after.items() if words > before.get(label, 0)}
        return [f"{label}: grew by {words} words; the PR body's Words added section states "
                f"{stated[label] if label in stated else 'none'}: state `{label}: +{words} — <the rule they serve>`"
                for label, words in sorted(grown.items()) if stated.get(label) != words]
