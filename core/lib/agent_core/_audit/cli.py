from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent_core._audit.baseline import (
    BASELINE_PATH,
    STATUS_CHANGED,
    STATUS_NEW,
    STATUS_REMOVED,
    Baseline,
    CorruptBaseline,
)
from agent_core._audit.bench import BenchBuild, BenchError, BenchSource
from agent_core._audit.bench_score import BenchScore, FindingsFile, Manifest
from agent_core._audit.checks import DomainChecksFile, ReportCheck
from agent_core._audit.commands import FAILURES_KEY, FLAG_NEW, HELP_NEW, LintCommands, ParserNames, Subcommand
from agent_core._audit.history import GitUnavailable
from agent_core._audit.lint import Lint, LintInputs, UnknownRowType
from agent_core._audit.prose import ProseCheck
from agent_core._audit.ratchet import PullRequest, WordRatchet
from agent_core._audit.related import RelatedFiles
from agent_core._audit.rows import Acknowledged, Fingerprints
from agent_core._audit.scope import (
    CODE_GROUPS,
    CORE_SCOPE,
    ENCODING,
    INSTRUCTION_GROUPS,
    PIPELINE_GROUPS,
    ControlPlaneFiles,
    RepositoryPath,
)
from agent_core._audit.weight import OwnedInstructions

DESCRIPTION = "Control-plane audit: the mechanical half of an audit, over what changed since the last one."
PROGRAM = "audit.py"
CODE_SUFFIX = ".py"
EXIT_FAILURE = 1
FLAG_ROOT = "--root"
FLAG_ALL = "--all"
FLAG_CHANGED = "--changed"
FLAG_ONLY = "--only"
SKILL_LINK = Path(".claude") / "skills" / "control-plane-audit"
ENGINE_SCRIPT = Path("scripts") / "audit.py"
HELP_ROOT = f"the domain root to audit; if absent, the nearest directory above the script that holds {SKILL_LINK}"
NAME_THE_ROOT = f"name the root with {FLAG_ROOT}"
HELP_CHANGED = "the audit set: the files changed since the last accepted audit, and the files that name them"
HELP_LINT = "the mechanical checks over the whole control plane"
HELP_ACCEPT = "record every control-plane file as audited, ending this audit"
HELP_ALL = "cover every control-plane file"
HELP_CHANGED_ONLY = "cover only the files changed since the last accepted audit"
HELP_ONLY = "print only the named row types, and compute no other"
HELP_BENCH = "the audit test bench: a synthetic control plane with one seeded defect per class"
HELP_BENCH_BUILD = "copy the bench plane into a new directory, apply every seed, and print the seed manifest"
HELP_BENCH_SCORE = "match the findings to the seeds of a built bench, and print the recall"
HELP_BENCH_DIRECTORY = "the bench directory"
HELP_FINDINGS = "a JSON file: the output of lint, or a list of findings, each with check, file, line, and layer"



class CommandLine:
    def __init__(self, script: Path | None = None) -> None:
        self._script = script

    def run(self, argv: list[str]) -> None:
        try:
            self._run(argv)
        except (CorruptBaseline, RootNotFound, BenchError, GitUnavailable, UnknownRowType) as error:
            self._print({"error": str(error)})
            sys.exit(EXIT_FAILURE)

    def _run(self, argv: list[str]) -> None:
        domain = AuditedDomain(RootOption(self._script).parsed(argv))
        parser = self._parser(domain)
        domain.learn(ParserNames(parser).names())
        args = parser.parse_args(argv)
        if args.handler is None:
            parser.print_help()
            return
        payload = args.handler(args)
        self._print(payload)
        if payload.get(FAILURES_KEY):
            sys.exit(EXIT_FAILURE)

    @staticmethod
    def _print(payload: dict) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    def _parser(self, domain: AuditedDomain) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
        RootOption.added_to(parser)
        parser.set_defaults(handler=None)
        commands = parser.add_subparsers(dest="command")
        changed = Subcommand("changed", HELP_CHANGED, domain.changed).added_to(commands)
        changed.add_argument(FLAG_ALL, action="store_true", help=HELP_ALL)
        lint = Subcommand("lint", HELP_LINT, domain.lint).added_to(commands)
        lint.add_argument(FLAG_CHANGED, action="store_true", help=HELP_CHANGED_ONLY)
        lint.add_argument(FLAG_NEW, action="store_true", help=HELP_NEW)
        lint.add_argument(FLAG_ONLY, nargs="+", default=[], metavar="ROW", help=HELP_ONLY)
        LintCommands(domain).added_to(commands)
        for check in domain.reports():
            ReportSubcommand(check, domain.root).added_to(commands)
        Subcommand("accept", HELP_ACCEPT, domain.accept).added_to(commands)
        BenchSubcommand(domain.root).added_to(commands)
        return parser


class RootNotFound(LookupError):
    pass


class RootOption:
    def __init__(self, script: Path | None) -> None:
        self._script = script

    def parsed(self, argv: list[str]) -> Path:
        parser = argparse.ArgumentParser(add_help=False)
        self.added_to(parser)
        known, _rest = parser.parse_known_args(argv)
        return self._linking_root() if known.root is None else Path(known.root)

    @staticmethod
    def added_to(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(FLAG_ROOT, help=HELP_ROOT)

    def _linking_root(self) -> Path:
        if self._script is None:
            raise RootNotFound(f"no script path to find the root from; {NAME_THE_ROOT}")
        return LinkingRoot(self._script).found()


class LinkingRoot:
    def __init__(self, script: Path) -> None:
        self._script = Path(os.path.abspath(script))

    def found(self) -> Path:
        linking = [directory for directory in self._script.parents if (directory / SKILL_LINK).exists()]
        if not linking:
            raise RootNotFound(f"no directory above {self._script} holds {SKILL_LINK}; {NAME_THE_ROOT}")
        return linking[0]


class AuditedDomain:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._checks = DomainChecksFile(root).loaded()
        self._files = ControlPlaneFiles(root, CORE_SCOPE.extended_by(self._checks.scope))
        self._baseline_path = root / BASELINE_PATH
        self._known: dict[str, frozenset[str]] = {}

    @property
    def root(self) -> Path:
        return self._root

    def reports(self) -> tuple[ReportCheck, ...]:
        return self._checks.reports

    def learn(self, subcommands: frozenset[str]) -> None:
        self._known = {(SKILL_LINK / ENGINE_SCRIPT).as_posix(): subcommands}

    def changed(self, args: argparse.Namespace) -> dict:
        audit_set = self._everything() if args.all else self._changes()
        return audit_set.as_dict()

    def lint(self, args: argparse.Namespace) -> dict:
        audit_set = self._changes() if args.changed else self._everything()
        inputs = LintInputs(audit_set, self._files, self._checks, self._known)
        lint = Lint(inputs, self._baseline().weight(), frozenset(args.only))
        return lint.unacknowledged(self._baseline().acknowledged()) if args.new else lint.payload()

    def prose(self, args: argparse.Namespace) -> dict:
        named = {Path(os.path.abspath(path)) for path in args.paths}
        instructions = self._everything().instructions()
        chosen = [path for path in instructions if not named or Path(os.path.abspath(path)) in named
                  or path.resolve() in {name.resolve() for name in named}]
        rows = Fingerprints(self._root).stamped(ProseCheck(chosen, self._root).rows())
        return {"prose": Acknowledged(self._baseline().acknowledged()).unacknowledged(rows) if args.new else rows}

    def acknowledge(self, args: argparse.Namespace) -> dict:
        fingerprints = self._every_unacknowledged() if args.every_row else args.fingerprints
        return self._baseline().acknowledge({fingerprint: args.reason for fingerprint in fingerprints})

    def dismiss(self, args: argparse.Namespace) -> dict:
        return self._baseline().dismiss(args.fingerprints)

    def ratchet(self, args: argparse.Namespace) -> dict:
        body = args.body_file.read_text(encoding=ENCODING) if args.body_file else ""
        return WordRatchet(self._files, PullRequest(args.base, body)).verdict()

    def accept(self, _args: argparse.Namespace) -> dict:
        weight = OwnedInstructions(self._files).texts().counts()
        return self._baseline().accept(self._files.all(), weight)

    def _every_unacknowledged(self) -> list[str]:
        audit_set = self._everything()
        payload = Lint(LintInputs(audit_set, self._files, self._checks, self._known), None)
        rows = payload.unacknowledged(self._baseline().acknowledged())
        return [row["fingerprint"] for value in rows.values() if isinstance(value, list) for row in value
                if isinstance(row, dict) and "fingerprint" in row]

    def _baseline(self) -> Baseline:
        return Baseline(self._baseline_path, self._root)

    def _everything(self) -> AuditSet:
        return AuditSet.of_everything(self._files, self._baseline_path)

    def _changes(self) -> AuditSet:
        return AuditSet.of_changes(self._files, self._baseline_path)


class ReportSubcommand(Subcommand):
    def __init__(self, check: ReportCheck, root: Path) -> None:
        super().__init__(check.name, check.help, self._reported)
        self._check = check
        self._root = root

    def _reported(self, _args: argparse.Namespace) -> dict:
        return self._check.report(self._root)


class BenchSubcommand:
    def __init__(self, root: Path) -> None:
        self._root = root

    def added_to(self, commands: argparse._SubParsersAction) -> None:
        actions = commands.add_parser("bench", help=HELP_BENCH).add_subparsers(dest="bench_command", required=True)
        build = Subcommand("build", HELP_BENCH_BUILD, self._built).added_to(actions)
        build.add_argument("directory", type=Path, help=HELP_BENCH_DIRECTORY)
        score = Subcommand("score", HELP_BENCH_SCORE, self._scored).added_to(actions)
        score.add_argument("directory", type=Path, help=HELP_BENCH_DIRECTORY)
        score.add_argument("findings", type=Path, help=HELP_FINDINGS)

    def _built(self, args: argparse.Namespace) -> dict:
        return BenchBuild(BenchSource(self._root), args.directory).manifest()

    @staticmethod
    def _scored(args: argparse.Namespace) -> dict:
        return BenchScore(Manifest(args.directory).seeds(), FindingsFile(args.findings).findings()).report()


class EveryFile:
    def selected(self, paths: list[Path], _baseline: Baseline) -> list[Path]:
        return paths


class ChangedFiles:
    def __init__(self, root: Path) -> None:
        self._root = root

    def selected(self, paths: list[Path], baseline: Baseline) -> list[Path]:
        if baseline.accepted_on() is None:
            return paths
        changed = baseline.changed(paths)
        unaudited = set(changed[STATUS_NEW]) | set(changed[STATUS_CHANGED])
        return [path for path in paths if RepositoryPath(path, self._root).label() in unaudited]


class AuditSet:
    def __init__(self, selection: EveryFile | ChangedFiles, files: ControlPlaneFiles, baseline_path: Path) -> None:
        self._selection = selection
        self._files = files
        self._baseline = Baseline(baseline_path, files.root)

    @classmethod
    def of_everything(cls, files: ControlPlaneFiles, baseline_path: Path) -> AuditSet:
        return cls(EveryFile(), files, baseline_path)

    @classmethod
    def of_changes(cls, files: ControlPlaneFiles, baseline_path: Path) -> AuditSet:
        return cls(ChangedFiles(files.root), files, baseline_path)

    @property
    def root(self) -> Path:
        return self._files.root

    def as_dict(self) -> dict:
        changed = self._baseline.changed(self._files.all())
        read_first = self._selected(self._files.groups())
        return {"accepted": self._baseline.accepted_on(), "changed": self._named(read_first),
                "related": self._named(RelatedFiles(self._files).of(read_first)),
                STATUS_REMOVED: changed[STATUS_REMOVED], "counts": self.counts()}

    def instructions(self) -> list[Path]:
        return self._selected(INSTRUCTION_GROUPS)

    def code(self) -> list[Path]:
        return [path for path in self._selected(CODE_GROUPS) if path.suffix == CODE_SUFFIX]

    def pipeline_code(self) -> list[Path]:
        return [path for path in self._selected(PIPELINE_GROUPS) if path.suffix == CODE_SUFFIX]

    def counts(self) -> dict:
        return {"instructions": len(self.instructions()), "code": len(self.code()),
                "control_plane": len(self._files.all())}

    def _selected(self, groups: tuple[str, ...]) -> list[Path]:
        return self._selection.selected(self._files.of_groups(groups), self._baseline)

    def _named(self, paths: list[Path]) -> list[str]:
        return [RepositoryPath(path, self.root).label() for path in paths]
