from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.baseline import BASELINE_PATH, Baseline
from agent_core._audit.checks import DomainChecksFile
from agent_core._audit.scope import CORE_SCOPE, ENCODING, ControlPlaneFiles

BENCH_SOURCE = Path("tests") / "audit_bench"
SEEDS_NAME = "seeds.json"
PLANE_NAME = "plane"
MANIFEST_NAME = "bench-manifest.json"
HIDDEN_SOURCE_PREFIX = "dot-"
HIDDEN_PREFIX = "."
IGNORED_SOURCE_FILES = ("__pycache__", "*.pyc")
AT_REST_MESSAGE = "Add the control plane\n\nChange-class: feature — the control plane"
SEEDED_MESSAGE = "Revise the control plane\n\nChange-class: feature — revisions across the control plane"
GIT_SETTINGS = ("-c", "user.name=audit bench", "-c", "user.email=audit-bench@example.invalid",
                "-c", "commit.gpgsign=false", "-c", "core.hooksPath=.git/hooks")
GIT_ENVIRONMENT_PREFIX = "GIT_"
SEED_FIELDS = ("id", "check", "class", "target", "mutation")
WINDOW_LINES = 2


class BenchError(ValueError):
    pass


@dataclass(frozen=True)
class Mutation:
    anchor: str
    new_text: str
    keeps_anchor: bool
    message: str | None = None

    @classmethod
    def of(cls, fields: dict, seed_id: str) -> Mutation:
        message = fields.get("message")
        if "find" in fields and "replace" in fields:
            return cls(fields["find"], fields["replace"], False, message)
        if "after" in fields and "insert" in fields:
            return cls(fields["after"], fields["insert"], True, message)
        raise BenchError(f"seed {seed_id}: its mutation needs find and replace, or after and insert")

    @property
    def located_text(self) -> str:
        return self.new_text.strip()

    def applied_to(self, text: str) -> str:
        replacement = self.anchor + self.new_text if self.keeps_anchor else self.new_text
        return text.replace(self.anchor, replacement, 1)


@dataclass(frozen=True)
class Seed:
    seed_id: str
    check: str
    defect_class: str
    target: str
    mutation: Mutation
    negative: bool = False

    @classmethod
    def of(cls, fields: dict) -> Seed:
        missing = [name for name in SEED_FIELDS if name not in fields]
        if missing:
            raise BenchError(f"seed {fields.get('id', '?')}: lacks {', '.join(missing)}")
        mutation = Mutation.of(fields["mutation"], fields["id"])
        if not mutation.located_text:
            raise BenchError(f"seed {fields['id']}: its new text is blank, so no line can locate it")
        return cls(fields["id"], fields["check"], fields["class"], fields["target"], mutation,
                   bool(fields.get("negative", False)))

    @property
    def is_committed_alone(self) -> bool:
        return self.mutation.message is not None

    def apply(self, directory: Path) -> None:
        path = self._target_in(directory)
        text = path.read_text(encoding=ENCODING)
        occurrences = text.count(self.mutation.anchor)
        if occurrences != 1:
            raise BenchError(f"seed {self.seed_id}: its anchor occurs {occurrences} times in {self.target}, "
                             f"not once")
        path.write_text(self.mutation.applied_to(text), encoding=ENCODING)

    def entry(self) -> dict:
        return {"id": self.seed_id, "check": self.check, "class": self.defect_class, "negative": self.negative}

    def located_in(self, directory: Path) -> dict:
        text = self._target_in(directory).read_text(encoding=ENCODING)
        located = self.mutation.located_text
        if text.count(located) != 1:
            raise BenchError(f"seed {self.seed_id}: its new text occurs {text.count(located)} times in "
                             f"{self.target} once every seed is applied, not once")
        line = text.count("\n", 0, text.index(located)) + 1
        return {"file": self.target, "line": line, "end": line + located.count("\n")}

    def _target_in(self, directory: Path) -> Path:
        path = directory / self.target
        if not path.is_file():
            raise BenchError(f"seed {self.seed_id}: its target {self.target} is not a file of the plane")
        return path


class BenchSource:
    def __init__(self, root: Path) -> None:
        self._directory = root / BENCH_SOURCE

    def seeds(self) -> list[Seed]:
        path = self._directory / SEEDS_NAME
        if not path.is_file():
            raise BenchError(f"no bench seeds at {path}; name the root that holds {BENCH_SOURCE} with --root")
        seeds = [Seed.of(fields) for fields in json.loads(path.read_text(encoding=ENCODING))]
        counts = Counter(seed.seed_id for seed in seeds)
        repeated = sorted(seed_id for seed_id, count in counts.items() if count > 1)
        if repeated:
            raise BenchError(f"{path}: the seed ids {', '.join(repeated)} repeat; give each seed its own id")
        return seeds

    def plane(self) -> Path:
        path = self._directory / PLANE_NAME
        if not path.is_dir():
            raise BenchError(f"no bench plane at {path}; name the root that holds {BENCH_SOURCE} with --root")
        return path


class BenchBuild:
    def __init__(self, source: BenchSource, directory: Path) -> None:
        self._source = source
        self._directory = directory

    def manifest(self) -> dict:
        seeds = self._source.seeds()
        self._lay_out_the_plane()
        repository = BenchRepository(self._directory)
        repository.start(AT_REST_MESSAGE)
        self._seed_together([seed for seed in seeds if not seed.is_committed_alone], repository)
        commits = {seed.seed_id: self._committed(seed, repository) for seed in seeds if seed.is_committed_alone}
        manifest = {"seeds": [{**seed.entry(), **self._location(seed, commits)} for seed in seeds]}
        SeedSpacing(manifest["seeds"]).refuse_crowding()
        (self._directory / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding=ENCODING)
        return manifest

    def _lay_out_the_plane(self) -> None:
        if self._directory.exists() and not self._is_empty_directory():
            raise BenchError(f"{self._directory} is not an empty directory; name a new or empty one")
        shutil.copytree(self._source.plane(), self._directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(*IGNORED_SOURCE_FILES))
        self._reveal_hidden_entries()
        self._accept_the_plane()

    def _is_empty_directory(self) -> bool:
        return self._directory.is_dir() and not any(self._directory.iterdir())

    def _reveal_hidden_entries(self) -> None:
        for entry in list(self._directory.iterdir()):
            if entry.name.startswith(HIDDEN_SOURCE_PREFIX):
                entry.rename(self._directory / (HIDDEN_PREFIX + entry.name.removeprefix(HIDDEN_SOURCE_PREFIX)))

    def _accept_the_plane(self) -> None:
        scope = CORE_SCOPE.extended_by(DomainChecksFile(self._directory).loaded().scope)
        files = ControlPlaneFiles(self._directory, scope)
        Baseline(self._directory / BASELINE_PATH, self._directory).accept(files.all())

    def _seed_together(self, seeds: list[Seed], repository: BenchRepository) -> None:
        for seed in seeds:
            seed.apply(self._directory)
        repository.commit(SEEDED_MESSAGE)

    def _committed(self, seed: Seed, repository: BenchRepository) -> str:
        seed.apply(self._directory)
        return repository.commit(seed.mutation.message)

    def _location(self, seed: Seed, commits: dict[str, str]) -> dict:
        if seed.seed_id in commits:
            return {"commit": commits[seed.seed_id]}
        return seed.located_in(self._directory)


class SeedSpacing:
    def __init__(self, entries: list[dict]) -> None:
        self._entries = [entry for entry in entries if "file" in entry]

    def refuse_crowding(self) -> None:
        crowded = [f"{first['id']} and {second['id']}" for first, second in itertools.combinations(self._entries, 2)
                   if self._compete(first, second)]
        if crowded:
            raise BenchError(f"the windows of these seeds overlap, so one finding would match both: "
                             f"{'; '.join(crowded)}; move one seed of each pair")

    @staticmethod
    def _compete(first: dict, second: dict) -> bool:
        one_reader = first["check"] == second["check"] or first["negative"] or second["negative"]
        overlapping = first["line"] - WINDOW_LINES <= second["end"] + WINDOW_LINES and \
            second["line"] - WINDOW_LINES <= first["end"] + WINDOW_LINES
        return first["file"] == second["file"] and one_reader and overlapping


class BenchRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def start(self, message: str) -> str:
        self._git("init", "--quiet")
        return self.commit(message)

    def commit(self, message: str) -> str:
        self._git("add", "--all")
        self._git("commit", "--quiet", "--no-verify", "--allow-empty", "--message", message)
        return self._git("rev-parse", "HEAD").strip()

    def _git(self, *arguments: str) -> str:
        environment = {name: value for name, value in os.environ.items()
                       if not name.startswith(GIT_ENVIRONMENT_PREFIX)}
        try:
            run = subprocess.run(["git", *GIT_SETTINGS, *arguments], cwd=self._directory, env=environment,
                                 capture_output=True, text=True, check=False)
        except FileNotFoundError as error:
            raise BenchError("git is not installed; the bench builds a git history and needs it") from error
        if run.returncode != 0:
            raise BenchError(f"git {arguments[0]} failed in {self._directory}: {run.stderr.strip()}")
        return run.stdout
