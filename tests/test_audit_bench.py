from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _audit_files import AuditRun, TemporaryFiles
from _repository import REPOSITORY_ROOT

from agent_core._audit.bench import BENCH_SOURCE, MANIFEST_NAME, BenchSource
from agent_core._audit.cli import CommandLine

BENCH_DIRECTORY = "bench"
LINT_FILE = "lint.json"
FINDINGS_FILE = "findings.json"
SCRIPT = REPOSITORY_ROOT / ".claude" / "skills" / "control-plane-audit" / "scripts" / "audit.py"
SEEDS = json.loads((REPOSITORY_ROOT / BENCH_SOURCE / "seeds.json").read_text(encoding="utf-8"))
PLANE_FILES = 9
PINNED_LINT_FOUND = {"code": 4, "delegation": 0, "failure": 0, "pointers": 2, "prose": 0, "redundancy": 0,
                     "special": 0, "staleness": 0, "xref": 0}
PINNED_LINT_RECALL = 0.188
COMMIT_SEED = "special-commit-trailer"
TRAILER_MARKS = ("Defect-class:", "Change-class:")
REPORT_NAME = "rooted"
ROOTED_CHECKS = f'''from __future__ import annotations

from agent_core._audit.checks import DomainChecks


class Rooted:
    name = "{REPORT_NAME}"
    help = "the root the engine hands the report"

    def report(self, root):
        return {{"root": str(root.resolve())}}


DOMAIN = DomainChecks(reports=(Rooted(),))
'''
OUTSIDE_COMMANDS = (("changed",), ("changed", "--all"), ("lint",), ("lint", "--changed"), (REPORT_NAME,),
                    ("accept",))


class Bench:
    def __init__(self, case: unittest.TestCase) -> None:
        self._files = TemporaryFiles(case)
        self.directory = self._files.root / BENCH_DIRECTORY

    @property
    def scratch(self) -> TemporaryFiles:
        return self._files

    def built(self, root: Path = REPOSITORY_ROOT) -> dict:
        return Outcome.of(root, "bench", "build", str(self.directory))

    def scored(self, findings: Path) -> dict:
        return Outcome.of(REPOSITORY_ROOT, "bench", "score", str(self.directory), str(findings))


class Outcome:
    @staticmethod
    def of(root: Path, *arguments: str) -> dict:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), contextlib.suppress(SystemExit):
            CommandLine().run(["--root", str(root), *arguments])
        return json.loads(captured.getvalue())


class BenchRoot:
    def __init__(self, case: unittest.TestCase, seeds: list[dict]) -> None:
        self._files = TemporaryFiles(case)
        self._files.written(str(BENCH_SOURCE / "seeds.json"), json.dumps(seeds))
        self._files.linked(str(BENCH_SOURCE / "plane"), str(REPOSITORY_ROOT / BENCH_SOURCE / "plane"))
        self.root = self._files.root


class TestThePlaneAtRest(unittest.TestCase):
    def setUp(self) -> None:
        self.bench = Bench(self)
        self.bench.built(BenchRoot(self, []).root)
        self.lint = AuditRun(self.bench.directory).payload("lint")

    def test_the_plane_at_rest_yields_no_code_row(self) -> None:
        self.assertEqual([], self.lint["code"])

    def test_the_plane_at_rest_yields_no_pointers_row(self) -> None:
        self.assertEqual([], self.lint["pointers"])

    def test_the_plane_holds_its_control_plane_files_under_their_built_names(self) -> None:
        self.assertEqual(PLANE_FILES, self.lint["files"]["control_plane"])


class TestTheSeeds(unittest.TestCase):
    def test_every_seed_names_a_target_of_the_built_plane(self) -> None:
        bench = Bench(self)
        bench.built(BenchRoot(self, []).root)
        missing = [seed["id"] for seed in SEEDS if not (bench.directory / seed["target"]).is_file()]
        self.assertEqual([], missing)

    def test_no_seed_text_is_in_the_plane_at_rest(self) -> None:
        bench = Bench(self)
        bench.built(BenchRoot(self, []).root)
        present = [seed.seed_id for seed in BenchSource(REPOSITORY_ROOT).seeds()
                   if seed.mutation.located_text in (bench.directory / seed.target).read_text(encoding="utf-8")]
        self.assertEqual([], present)

    def test_the_seeds_hold_negative_seeds(self) -> None:
        self.assertEqual(2, len([seed for seed in SEEDS if seed.get("negative")]))


class TestTheBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        cls.directory = Path(cls._directory.name) / BENCH_DIRECTORY
        cls.manifest = Outcome.of(REPOSITORY_ROOT, "bench", "build", str(cls.directory))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_the_manifest_holds_one_entry_per_seed(self) -> None:
        self.assertEqual([seed["id"] for seed in SEEDS], [entry["id"] for entry in self.manifest["seeds"]])

    def test_each_entry_names_its_check_and_class(self) -> None:
        expected = [(seed["check"], seed["class"]) for seed in SEEDS]
        self.assertEqual(expected, [(entry["check"], entry["class"]) for entry in self.manifest["seeds"]])

    def test_each_file_entry_names_a_line_of_its_target(self) -> None:
        entries = [entry for entry in self.manifest["seeds"] if "file" in entry]
        lengths = {entry["file"]: self._lines_of(entry["file"]) for entry in entries}
        self.assertEqual([], [entry["id"] for entry in entries if not 1 <= entry["line"] <= lengths[entry["file"]]])

    def test_the_build_writes_the_manifest_it_prints(self) -> None:
        written = json.loads((self.directory / MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(self.manifest, written)

    def test_the_commit_seed_is_a_commit_of_its_own_with_no_trailer(self) -> None:
        entry = next(entry for entry in self.manifest["seeds"] if entry["id"] == COMMIT_SEED)
        message = self._git("log", "-1", "--format=%B", entry["commit"])
        self.assertFalse(any(mark in message for mark in TRAILER_MARKS))

    def test_every_other_commit_carries_a_trailer(self) -> None:
        messages = self._git("log", "--skip=1", "--format=%B%x00").split("\0")
        bare = [message for message in messages if message.strip() and not any(m in message for m in TRAILER_MARKS)]
        self.assertEqual([], bare)

    def test_the_audit_baseline_records_the_plane_at_rest(self) -> None:
        changed = AuditRun(self.directory).payload("changed")["changed"]
        targets = sorted({seed["target"] for seed in SEEDS})
        self.assertEqual(targets, sorted(changed))

    def _lines_of(self, name: str) -> int:
        return len((self.directory / name).read_text(encoding="utf-8").splitlines())

    def _git(self, *arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=self.directory, capture_output=True, text=True,
                              check=True).stdout


class TestABuildThatCannotRun(unittest.TestCase):
    def test_a_seed_whose_anchor_is_absent_fails_naming_the_seed(self) -> None:
        stray = {**SEEDS[0], "id": "stray", "mutation": {"find": "no such text", "replace": "x"}}
        outcome = Bench(self).built(BenchRoot(self, [stray]).root)
        self.assertIn("seed stray", outcome["error"])

    def test_seeds_that_crowd_one_window_fail_naming_both(self) -> None:
        first = {"id": "first", "check": "prose", "class": "c", "target": "AGENTS.md",
                 "mutation": {"find": "# Ledger — Contract", "replace": "# Ledger, Contract"}}
        second = {**first, "id": "second", "mutation": {"find": "## 1. Mandate", "replace": "## 1. Remit"}}
        outcome = Bench(self).built(BenchRoot(self, [first, second]).root)
        self.assertIn("first and second", outcome["error"])

    def test_a_build_into_a_directory_that_holds_a_file_fails(self) -> None:
        bench = Bench(self)
        bench.scratch.written(f"{BENCH_DIRECTORY}/kept.txt", "kept\n")
        self.assertIn("not an empty directory", bench.built()["error"])

    def test_a_root_without_the_bench_fails_naming_the_root_option(self) -> None:
        self.assertIn("--root", Bench(self).built(TemporaryFiles(self).root)["error"])


class TestTheLintLayersRecall(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        root = Path(cls._directory.name)
        Outcome.of(REPOSITORY_ROOT, "bench", "build", str(root / BENCH_DIRECTORY))
        lint = root / LINT_FILE
        lint.write_text(json.dumps(AuditRun(root / BENCH_DIRECTORY).payload("lint")), encoding="utf-8")
        cls.score = Outcome.of(REPOSITORY_ROOT, "bench", "score", str(root / BENCH_DIRECTORY), str(lint))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_the_lint_layer_finds_the_pinned_seeds_of_each_check(self) -> None:
        found = {check: row["found"] for check, row in self.score["per_layer"]["lint"]["per_check"].items()}
        self.assertEqual(PINNED_LINT_FOUND, found)

    def test_the_lint_layers_recall_is_pinned(self) -> None:
        self.assertEqual(PINNED_LINT_RECALL, self.score["per_layer"]["lint"]["recall"])

    def test_no_lint_finding_lands_on_a_negative_seed(self) -> None:
        self.assertEqual([], self.score["false_positives"])

    def test_every_lint_finding_lands_on_a_seed(self) -> None:
        self.assertEqual([], self.score["unmatched"])


class TestTheScore(unittest.TestCase):
    def setUp(self) -> None:
        self.bench = Bench(self)
        seeds = [{"id": "near", "check": "prose", "class": "c", "negative": False, "file": "a.md", "line": 10,
                  "end": 11},
                 {"id": "decoy", "check": "redundancy", "class": "c", "negative": True, "file": "b.md", "line": 5,
                  "end": 5},
                 {"id": "history", "check": "special", "class": "c", "negative": False, "commit": "abcdef0123"}]
        self.bench.scratch.written(f"{BENCH_DIRECTORY}/{MANIFEST_NAME}", json.dumps({"seeds": seeds}))

    def scored(self, *findings: dict) -> dict:
        return self.bench.scored(self.bench.scratch.written(FINDINGS_FILE, json.dumps(list(findings))))

    def test_a_finding_inside_the_window_finds_its_seed(self) -> None:
        score = self.scored(finding("prose", "a.md", 13))
        self.assertEqual(1, score["per_check"]["prose"]["found"])

    def test_a_finding_past_the_window_is_unmatched(self) -> None:
        score = self.scored(finding("prose", "a.md", 14))
        self.assertEqual([finding("prose", "a.md", 14)], score["unmatched"])

    def test_a_finding_of_another_check_finds_no_seed(self) -> None:
        self.assertEqual(["near", "history"], self.scored(finding("xref", "a.md", 10))["missed"])

    def test_a_finding_on_a_negative_seed_is_a_false_positive(self) -> None:
        score = self.scored(finding("prose", "b.md", 6))
        self.assertEqual([{"seed": "decoy", "finding": finding("prose", "b.md", 6)}], score["false_positives"])

    def test_a_commit_prefix_of_seven_characters_finds_the_commit_seed(self) -> None:
        self.assertEqual(1, self.scored(finding("special", "abcdef0", 1))["per_check"]["special"]["found"])

    def test_a_commit_prefix_of_six_characters_finds_nothing(self) -> None:
        self.assertEqual(0, self.scored(finding("special", "abcdef", 1))["per_check"]["special"]["found"])

    def test_the_recall_is_given_per_layer(self) -> None:
        score = self.scored(finding("prose", "a.md", 10), {**finding("special", "abcdef0", 1), "layer": "lint"})
        self.assertEqual({"judgment": 0.5, "lint": 0.5},
                         {layer: row["recall"] for layer, row in score["per_layer"].items()})

    def test_the_recall_over_every_layer_counts_each_seed_once(self) -> None:
        score = self.scored(finding("prose", "a.md", 10), {**finding("prose", "a.md", 11), "layer": "lint"})
        self.assertEqual((2, 1), (score["seeds"], score["found"]))

    def test_a_finding_without_a_layer_fails_naming_the_field(self) -> None:
        bare = {"check": "prose", "file": "a.md", "line": 10}
        self.assertIn("lacks layer", self.scored(bare)["error"])

    def test_a_directory_without_a_manifest_fails(self) -> None:
        empty = TemporaryFiles(self)
        findings = empty.written(FINDINGS_FILE, "[]")
        outcome = Outcome.of(REPOSITORY_ROOT, "bench", "score", str(empty.root), str(findings))
        self.assertIn("no bench manifest", outcome["error"])


def finding(check: str, file: str, line: int) -> dict:
    return {"check": check, "file": file, "line": line, "layer": "judgment"}


class TestEveryCheckReadsTheBenchThroughItsRoot(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        outside = Path(cls._directory.name)
        cls.bench = outside / BENCH_DIRECTORY
        Outcome.of(REPOSITORY_ROOT, "bench", "build", str(cls.bench))
        (cls.bench / "audit" / "checks.py").write_text(ROOTED_CHECKS, encoding="utf-8")
        (outside / "elsewhere").mkdir()
        cls.outputs = {command: cls._run(outside / "elsewhere", command) for command in OUTSIDE_COMMANDS}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    @classmethod
    def _run(cls, working_directory: Path, command: tuple[str, ...]) -> str:
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(cls.bench), *command],
                              cwd=working_directory, env=environment, capture_output=True, text=True,
                              check=True).stdout

    def test_no_output_names_the_repository_the_engine_is_installed_in(self) -> None:
        naming = [" ".join(command) for command, output in self.outputs.items() if str(REPOSITORY_ROOT) in output]
        self.assertEqual([], naming)

    def test_every_file_label_names_a_file_of_the_bench(self) -> None:
        labels = [label for output in self.outputs.values() for label in FileLabels(json.loads(output)).all()]
        self.assertEqual([], [label for label in labels if not (self.bench / label).is_file()])

    def test_the_audit_set_counts_the_bench_alone(self) -> None:
        counts = json.loads(self.outputs[("changed", "--all")])["counts"]
        self.assertEqual(PLANE_FILES + 1, counts["control_plane"])

    def test_a_domain_report_receives_the_bench_as_its_root(self) -> None:
        self.assertEqual(str(self.bench.resolve()), json.loads(self.outputs[(REPORT_NAME,)])["root"])

    def test_accept_writes_the_baseline_of_the_bench(self) -> None:
        recorded = json.loads((self.bench / "audit" / "baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(PLANE_FILES + 1, len(recorded["digests"]))

    def test_accept_writes_no_baseline_into_the_repository(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "audit" / "baseline.json").exists())


class FileLabels:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def all(self) -> list[str]:
        listed = [label for key in ("changed", "related", "removed") for label in self._payload.get(key, [])]
        return listed + [row["file"] for value in self._payload.values() if isinstance(value, list)
                         for row in value if isinstance(row, dict)]


if __name__ == "__main__":
    unittest.main()
