from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from _repository import REPOSITORY_ROOT

CORE_DIR = REPOSITORY_ROOT / "core"
TEMPLATE_DIR = CORE_DIR / "templates" / "domain"
NEW_DOMAIN_SCRIPT = CORE_DIR / "skills" / "new-domain" / "scripts" / "new_domain.py"
CORE_BRANCH = "core"
CLOUD_SESSION_VARIABLE = "CLAUDE_CODE_REMOTE"
DOMAIN_NAME = "ledger-assistant"
BASIC_ANSWERS = {"name": DOMAIN_NAME, "summary": "Keeps the user's accounts.",
                 "mandate": "The domain keeps the user's accounts."}
IDENTITY = {
    "GIT_AUTHOR_NAME": "New Domain",
    "GIT_AUTHOR_EMAIL": "new-domain@example.invalid",
    "GIT_COMMITTER_NAME": "New Domain",
    "GIT_COMMITTER_EMAIL": "new-domain@example.invalid",
}


def isolated_environment(home: Path, cloud: bool = False) -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items()
                 if not key.startswith("GIT_") and key != CLOUD_SESSION_VARIABLE}
    cloud_session = {CLOUD_SESSION_VARIABLE: "true"} if cloud else {}
    return {**inherited, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(home),
            **IDENTITY, **cloud_session}


class PublishedCore:
    def __init__(self, workspace: Path) -> None:
        self.directory = workspace / "published-core"

    def published(self) -> PublishedCore:
        shutil.copytree(CORE_DIR, self.directory, ignore=shutil.ignore_patterns("__pycache__"))
        for arguments in (("init", "--quiet", "--initial-branch", CORE_BRANCH), ("add", "--all"),
                          ("commit", "--quiet", "--message", "Publish the core")):
            subprocess.run(["git", *arguments], cwd=self.directory, check=True, capture_output=True,
                           env=isolated_environment(self.directory))
        return self


@dataclass(frozen=True)
class Outcome:
    returncode: int
    payload: dict
    domain: Path
    documents: Path

    def manifest(self) -> dict:
        return json.loads((self.domain / "domain.json").read_text(encoding="utf-8"))


class NewDomainRun:
    def __init__(self, workspace: Path, core: PublishedCore) -> None:
        self._workspace = workspace
        self._core = core
        self.home = workspace / "home"
        self.domain = workspace / DOMAIN_NAME
        self.home.mkdir(exist_ok=True)

    def create(self, answers: dict, cloud: bool = False) -> Outcome:
        return self._run(["create", str(self._answers_file(answers)), "--into", str(self.domain),
                          "--core-url", str(self._core.directory)], cloud)

    def folders(self, answers: dict, cloud: bool = False) -> Outcome:
        return self._run(["folders", str(self._answers_file(answers)), "--domain", str(self.domain)], cloud)

    def _answers_file(self, answers: dict) -> Path:
        path = self._workspace / "answers.json"
        path.write_text(json.dumps(answers), encoding="utf-8")
        return path

    def _run(self, arguments: list[str], cloud: bool) -> Outcome:
        completed = subprocess.run([sys.executable, str(NEW_DOMAIN_SCRIPT), *arguments], capture_output=True,
                                   text=True, cwd=self._workspace, env=isolated_environment(self.home, cloud))
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {"stderr": completed.stderr}
        return Outcome(completed.returncode, payload, self.domain, self.home / "Documents")
