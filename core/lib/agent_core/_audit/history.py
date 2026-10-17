from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.scope import ENCODING

GIT_ENVIRONMENT_PREFIX = "GIT_"
RECORD_SEPARATOR = "\x1e"
FIELD_SEPARATOR = "\x1f"
BASELINE_LABEL = "audit/baseline.json"
BLAME_AUTHOR_TIME = "author-time "
BATCH_HEADER_FIELDS = 3
BATCH_SIZE_FIELD = 2
COMMIT_FIELDS = 4
MISSING_OBJECT = "missing"


class GitUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Commit:
    sha: str
    parents: tuple[str, ...]
    subject: str
    message: str

    @property
    def is_a_merge(self) -> bool:
        return len(self.parents) > 1


class Git:
    def __init__(self, root: Path) -> None:
        self._root = root

    def is_a_repository(self) -> bool:
        try:
            return self.output("rev-parse", "--is-inside-work-tree").strip() == "true"
        except GitUnavailable:
            return False

    def output(self, *arguments: str) -> str:
        run = self._run(list(arguments), b"")
        if run.returncode != 0:
            raise GitUnavailable(f"git {arguments[0]} failed in {self._root}: "
                                 f"{run.stderr.decode(ENCODING, 'replace').strip()}")
        return run.stdout.decode(ENCODING, "replace")

    def _run(self, arguments: list[str], given: bytes) -> subprocess.CompletedProcess:
        environment = {name: value for name, value in os.environ.items()
                       if not name.startswith(GIT_ENVIRONMENT_PREFIX)}
        try:
            return subprocess.run(["git", *arguments], cwd=self._root, env=environment, input=given,
                                  capture_output=True, check=False)
        except OSError as error:
            raise GitUnavailable(f"git cannot run in {self._root}: {error}") from error

    def commits(self, revision_range: str = "HEAD") -> list[Commit]:
        log = self.output("log", f"--format=%H{FIELD_SEPARATOR}%P{FIELD_SEPARATOR}%s{FIELD_SEPARATOR}%B"
                                 f"{RECORD_SEPARATOR}", revision_range)
        return [self._commit(record) for record in log.split(RECORD_SEPARATOR) if record.strip()]

    @staticmethod
    def _commit(record: str) -> Commit:
        sha, parents, subject, message = record.strip("\n").split(FIELD_SEPARATOR, maxsplit=COMMIT_FIELDS - 1)
        return Commit(sha, tuple(parents.split()), subject, message)

    def last_change_of(self, label: str) -> str | None:
        try:
            sha = self.output("log", "-1", "--format=%H", "--", label).strip()
        except GitUnavailable:
            return None
        return sha or None

    def blobs(self, requests: list[str]) -> list[str | None]:
        if not requests:
            return []
        run = self._run(["cat-file", "--batch"], ("\n".join(requests) + "\n").encode(ENCODING))
        if run.returncode != 0:
            raise GitUnavailable(f"git cat-file failed in {self._root}: {run.stderr.decode(ENCODING, 'replace')}")
        return BatchOutput(run.stdout).texts(len(requests))

    def line_times(self, path: Path) -> list[int]:
        resolved, root = path.resolve(), self._root.resolve()
        label = resolved.relative_to(root).as_posix() if resolved.is_relative_to(root) else str(resolved)
        try:
            porcelain = self.output("blame", "--line-porcelain", "--", label)
        except GitUnavailable:
            return []
        return [int(line.removeprefix(BLAME_AUTHOR_TIME)) for line in porcelain.splitlines()
                if line.startswith(BLAME_AUTHOR_TIME)]


class BatchOutput:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def texts(self, count: int) -> list[str | None]:
        texts, offset = [], 0
        for _request in range(count):
            end = self._raw.index(b"\n", offset)
            header = self._raw[offset:end].decode(ENCODING, "replace").split()
            offset = end + 1
            if len(header) < BATCH_HEADER_FIELDS or header[-1] == MISSING_OBJECT:
                texts.append(None)
                continue
            size = int(header[BATCH_SIZE_FIELD])
            texts.append(self._raw[offset:offset + size].decode(ENCODING, "replace"))
            offset += size + 1
        return texts


class BaselineCommit:
    def __init__(self, git: Git) -> None:
        self._git = git

    def sha(self) -> str | None:
        if not self._git.is_a_repository():
            return None
        return self._git.last_change_of(BASELINE_LABEL)
