from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

CORE_PREFIX = "core"
VENDOR_PREFIX = "vendor/agent-core"
CORE_BRANCH = "core"
MAIN_BRANCH = "main"
SQUASH_SUBJECT = f"Squashed '{VENDOR_PREFIX}/' changes"
MERGE_PARENT_COUNT = 2
IDENTITY = {
    "GIT_AUTHOR_NAME": "Round Trip",
    "GIT_AUTHOR_EMAIL": "round-trip@example.invalid",
    "GIT_COMMITTER_NAME": "Round Trip",
    "GIT_COMMITTER_EMAIL": "round-trip@example.invalid",
}


def isolated_environment() -> dict[str, str]:
    inherited = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return {**inherited, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", **IDENTITY}


class Git:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def run(self, *arguments: str) -> str:
        try:
            return self._completed(arguments).stdout.strip()
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"git {' '.join(arguments)} failed in {self._directory}: {error.stderr.strip()}") from error

    def _completed(self, arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *arguments], cwd=self._directory, env=isolated_environment(),
                              capture_output=True, text=True, check=True)


class Repository:
    def __init__(self, directory: Path) -> None:
        directory.mkdir()
        self.directory = directory
        self.git = Git(directory).run
        self.git("init", "--quiet", "--initial-branch", MAIN_BRANCH)

    def commit(self, message: str, files: dict[str, str]) -> None:
        for relative_path, text in files.items():
            self._write(relative_path, text)
        self.git("add", "--all")
        self.git("commit", "--quiet", "--message", message)

    def subjects(self, revision_range: str) -> list[str]:
        return self.git("log", "--format=%s", revision_range).splitlines()

    def parent_count(self, revision: str) -> int:
        return len(self.git("rev-list", "--parents", "--max-count=1", revision).split()) - 1

    def _write(self, relative_path: str, text: str) -> None:
        path = self.directory / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


@dataclass(frozen=True)
class RoundTripRecord:
    split_files: list[str]
    pulled_subjects: list[str]
    pull_head_parents: int
    vendored_files: dict[str, str]


class RoundTrip:
    def __init__(self, workspace: Path) -> None:
        self._core = Repository(workspace / "agent-core")
        self._published = workspace / "agent-core.git"
        Git(workspace).run("init", "--quiet", "--bare", str(self._published))
        self._domain = Repository(workspace / "domain")

    def record(self) -> RoundTripRecord:
        self._core.commit("Start the core", {f"{CORE_PREFIX}/README.md": "v1\n", "AGENTS.md": "the contract\n"})
        self._publish_core()
        self._domain.commit("Start the domain", {"README.md": "domain\n"})
        self._vendor("add", "Vendor the core")
        before_pull = self._domain.git("rev-parse", "HEAD")
        self._core.commit("Change the core", {f"{CORE_PREFIX}/README.md": "v2\n", f"{CORE_PREFIX}/CHANGED.md": "new\n"})
        self._publish_core()
        self._vendor("pull", "Pull the core")
        return self._recorded(before_pull)

    def _publish_core(self) -> None:
        split = self._core.git("subtree", "split", "--prefix", CORE_PREFIX, "HEAD")
        self._core.git("push", "--quiet", str(self._published), f"{split}:refs/heads/{CORE_BRANCH}")

    def _vendor(self, subcommand: str, message: str) -> None:
        self._domain.git("subtree", subcommand, "--prefix", VENDOR_PREFIX, "--squash", "--message", message,
                         str(self._published), CORE_BRANCH)

    def _recorded(self, before_pull: str) -> RoundTripRecord:
        vendor_dir = self._domain.directory / VENDOR_PREFIX
        return RoundTripRecord(
            split_files=Git(self._published).run("ls-tree", "-r", "--name-only", CORE_BRANCH).splitlines(),
            pulled_subjects=self._domain.subjects(f"{before_pull}..HEAD"),
            pull_head_parents=self._domain.parent_count("HEAD"),
            vendored_files={path.name: path.read_text(encoding="utf-8") for path in vendor_dir.iterdir()},
        )


class SubtreeRoundTrip(unittest.TestCase):
    record: RoundTripRecord

    @classmethod
    def setUpClass(cls) -> None:
        workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(workspace.cleanup)
        cls.record = RoundTrip(Path(workspace.name)).record()

    def test_the_split_holds_the_content_of_core_alone(self) -> None:
        self.assertEqual(["CHANGED.md", "README.md"], self.record.split_files)

    def test_the_pull_lands_as_one_squash_commit_and_one_merge(self) -> None:
        commit_kinds = [SQUASH_SUBJECT if subject.startswith(SQUASH_SUBJECT) else subject
                        for subject in self.record.pulled_subjects]
        self.assertEqual(["Pull the core", SQUASH_SUBJECT], commit_kinds)
        self.assertEqual(MERGE_PARENT_COUNT, self.record.pull_head_parents)

    def test_the_core_change_arrives_in_the_vendored_copy(self) -> None:
        self.assertEqual({"CHANGED.md": "new\n", "README.md": "v2\n"}, self.record.vendored_files)


if __name__ == "__main__":
    unittest.main()
