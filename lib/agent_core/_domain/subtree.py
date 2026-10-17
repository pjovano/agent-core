from __future__ import annotations

from dataclasses import dataclass

from agent_core._domain.git import Git

CORE_BRANCH = "core"
DEFAULT_CORE_URL = "https://github.com/pjovano/agent-core.git"
PARAGRAPH_BREAK = "\n\n"
MAINLINE_PARENT = "HEAD^1"
SQUASH_PARENT = "HEAD^2"


@dataclass(frozen=True)
class CoreSource:
    url: str = DEFAULT_CORE_URL
    branch: str = CORE_BRANCH


@dataclass(frozen=True)
class CommitMessages:
    merge: str
    squash_trailer: str


class SquashedSubtree:
    def __init__(self, git: Git, prefix: str) -> None:
        self._git = git
        self._prefix = prefix

    def add(self, source: CoreSource, messages: CommitMessages) -> None:
        self._git.run("subtree", "add", "--prefix", self._prefix, "--squash", "--message", messages.merge,
                      source.url, source.branch)
        self._give_the_squash_commit(messages.squash_trailer)

    def _give_the_squash_commit(self, trailer: str) -> None:
        squash = self._rewritten(SQUASH_PARENT, self._message_of(SQUASH_PARENT) + PARAGRAPH_BREAK + trailer)
        merge = self._git.run("commit-tree", "HEAD^{tree}", "-p", MAINLINE_PARENT, "-p", squash,
                              "-m", self._message_of("HEAD"))
        self._git.run("reset", "--quiet", "--soft", merge)

    def _rewritten(self, commit: str, message: str) -> str:
        parents = self._git.run("log", "-1", "--format=%P", commit).split()
        parent_options = [option for parent in parents for option in ("-p", parent)]
        return self._git.run("commit-tree", f"{commit}^{{tree}}", *parent_options, "-m", message)

    def _message_of(self, commit: str) -> str:
        return self._git.run("log", "-1", "--format=%B", commit)
