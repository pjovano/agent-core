from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

from agent_core._audit.baseline import (
    BASELINE_PATH,
    STATUS_CHANGED,
    STATUS_NEW,
    STATUS_REMOVED,
    Baseline,
    CorruptBaseline,
)
from agent_core._audit.checks import DomainChecksFile, ReportCheck
from agent_core._audit.measures import CodeMeasures
from agent_core._audit.pointers import InstructionPointers
from agent_core._audit.related import RelatedFiles
from agent_core._audit.scope import (
    CODE_GROUPS,
    CORE_SCOPE,
    INSTRUCTION_GROUPS,
    PIPELINE_GROUPS,
    ControlPlaneFiles,
    RepositoryPath,
)

DESCRIPTION = "Control-plane audit: the mechanical half of an audit, over what changed since the last one."
PROGRAM = "audit.py"
CODE_SUFFIX = ".py"
EXIT_FAILURE = 1
FLAG_ROOT = "--root"
FLAG_ALL = "--all"
FLAG_CHANGED = "--changed"
SKILL_LINK = Path(".claude") / "skills" / "control-plane-audit"
HELP_ROOT = f"the domain root to audit; if absent, the nearest directory above the script that holds {SKILL_LINK}"
NAME_THE_ROOT = f"name the root with {FLAG_ROOT}"
HELP_CHANGED = "the audit set: the files changed since the last accepted audit, and the files that name them"
HELP_LINT = "the mechanical checks over the whole control plane"
HELP_ACCEPT = "record every control-plane file as audited, ending this audit"
HELP_ALL = "cover every control-plane file"
HELP_CHANGED_ONLY = "cover only the files changed since the last accepted audit"

Handler = Callable[[argparse.Namespace], dict]


class CommandLine:
    def __init__(self, script: Path | None = None) -> None:
        self._script = script

    def run(self, argv: list[str]) -> None:
        try:
            self._run(argv)
        except (CorruptBaseline, RootNotFound) as error:
            self._print({"error": str(error)})
            sys.exit(EXIT_FAILURE)

    def _run(self, argv: list[str]) -> None:
        domain = AuditedDomain(RootOption(self._script).parsed(argv))
        parser = self._parser(domain)
        args = parser.parse_args(argv)
        if args.handler is None:
            parser.print_help()
            return
        self._print(args.handler(args))

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
        for check in domain.reports():
            ReportSubcommand(check, domain.root).added_to(commands)
        Subcommand("accept", HELP_ACCEPT, domain.accept).added_to(commands)
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

    @property
    def root(self) -> Path:
        return self._root

    def reports(self) -> tuple[ReportCheck, ...]:
        return self._checks.reports

    def changed(self, args: argparse.Namespace) -> dict:
        audit_set = self._everything() if args.all else self._changes()
        return audit_set.as_dict()

    def lint(self, args: argparse.Namespace) -> dict:
        audit_set = self._changes() if args.changed else self._everything()
        rows = {"files": audit_set.counts(), "code": CodeMeasures(audit_set.code(), self._root).findings(),
                "pointers": InstructionPointers(audit_set.instructions(), self._files).findings()}
        return {**rows, **{check.name: check.findings(audit_set) for check in self._checks.lint}}

    def accept(self, _args: argparse.Namespace) -> dict:
        return Baseline(self._baseline_path, self._root).accept(self._files.all())

    def _everything(self) -> AuditSet:
        return AuditSet.of_everything(self._files, self._baseline_path)

    def _changes(self) -> AuditSet:
        return AuditSet.of_changes(self._files, self._baseline_path)


class Subcommand:
    def __init__(self, name: str, help_text: str, handler: Handler) -> None:
        self._name = name
        self._help = help_text
        self._handler = handler

    def added_to(self, commands: argparse._SubParsersAction) -> argparse.ArgumentParser:
        command = commands.add_parser(self._name, help=self._help)
        command.set_defaults(handler=self._handler)
        return command


class ReportSubcommand(Subcommand):
    def __init__(self, check: ReportCheck, root: Path) -> None:
        super().__init__(check.name, check.help, self._reported)
        self._check = check
        self._root = root

    def _reported(self, _args: argparse.Namespace) -> dict:
        return self._check.report(self._root)


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
