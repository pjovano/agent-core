from __future__ import annotations

import os
import subprocess
import unittest

from _audit_files import TemporaryFiles

GIT_SETTINGS = ("-c", "user.name=audit test", "-c", "user.email=audit-test@example.invalid",
                "-c", "commit.gpgsign=false", "-c", "core.hooksPath=.git/hooks")
FEATURE = "Change-class: feature — the test change"
REFACTOR = "Change-class: refactor — the test change"
DEFECT = "Defect-class: a test defect class"


class GitFiles(TemporaryFiles):
    def __init__(self, case: unittest.TestCase) -> None:
        super().__init__(case)
        self.git("init", "--quiet", "--initial-branch=main")

    def git(self, *arguments: str, environment: dict | None = None) -> str:
        inherited = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
        return subprocess.run(["git", *GIT_SETTINGS, *arguments], cwd=self.root, capture_output=True, text=True,
                              check=True, env={**inherited, **(environment or {})}).stdout

    def committed(self, message: str, files: dict[str, str]) -> str:
        for name, text in files.items():
            self.written(name, text)
        self.git("add", "--all")
        self.git("commit", "--quiet", "--allow-empty", "--message", message)
        return self.git("rev-parse", "HEAD").strip()

    def committed_on(self, date: str, message: str, files: dict[str, str]) -> str:
        for name, text in files.items():
            self.written(name, text)
        self.git("add", "--all")
        dated = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        self.git("commit", "--quiet", "--message", message, environment=dated)
        return self.git("rev-parse", "HEAD").strip()

    def merged(self, branch: str, message: str) -> str:
        self.git("merge", "--quiet", "--no-ff", "--message", message, branch)
        return self.git("rev-parse", "HEAD").strip()


def message(subject: str, trailer: str) -> str:
    return f"{subject}\n\n{trailer}\n"
