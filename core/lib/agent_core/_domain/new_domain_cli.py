from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_core._domain.answers import DomainAnswers, FolderAnswers
from agent_core._domain.fields import JsonFields, ManifestError
from agent_core._domain.folder_step import DOCUMENTS, VAULT_CONFIG_SOURCE, FolderStep, Machine
from agent_core._domain.git import GitError
from agent_core._domain.manifest import MANIFEST_NAME, DomainManifest, JsonFile
from agent_core._domain.repository import DOMAIN_BRANCH, ExistingDomain, NewDomain, TargetRefused
from agent_core._domain.shelf import DEVELOPER_ROOT
from agent_core._domain.subtree import CORE_BRANCH, DEFAULT_CORE_URL, CoreSource
from agent_core._domain.vendored import DomainSettings

PROGRAM = "new_domain.py"
DESCRIPTION = "Make a domain from the domain template, and run the folder step that gives it its folders."
EXIT_FAILURE = 1
HELP_CREATE = ("copy the domain template, vendor the core, link its units, write domain.json and the settings blocks, "
               f"commit them on the branch {DOMAIN_BRANCH}, then run the folder step")
HELP_FOLDERS = "the folder step on an existing domain: add its vault and its folders to domain.json, and create them"
HELP_ANSWERS = "the JSON file holding the user's answers"
HELP_INTO = f"the new domain's directory; default {DEVELOPER_ROOT}/<name>"
HELP_DOMAIN = "the existing domain's directory; default the working directory"
HELP_CORE_URL = f"the repository whose branch the domain vendors; default {DEFAULT_CORE_URL}"
HELP_CORE_BRANCH = f"the branch the domain vendors; default {CORE_BRANCH}"
FAILURES = (ManifestError, GitError, TargetRefused, OSError)


class CommandLine:
    def run(self, argv: list[str]) -> None:
        try:
            self._run(argv)
        except FAILURES as error:
            self._print({"error": str(error)})
            sys.exit(EXIT_FAILURE)

    def _run(self, argv: list[str]) -> None:
        parser = self._parser()
        args = parser.parse_args(argv)
        if args.handler is None:
            parser.print_help()
            return
        args.handler(args)

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
        parser.set_defaults(handler=None)
        commands = parser.add_subparsers(dest="command")
        create = self._command(commands, "create", HELP_CREATE, self._create)
        create.add_argument("--into", type=Path, help=HELP_INTO)
        create.add_argument("--core-url", default=DEFAULT_CORE_URL, help=HELP_CORE_URL)
        create.add_argument("--core-branch", default=CORE_BRANCH, help=HELP_CORE_BRANCH)
        folders = self._command(commands, "folders", HELP_FOLDERS, self._folders)
        folders.add_argument("--domain", type=Path, default=Path.cwd(), help=HELP_DOMAIN)
        return parser

    @staticmethod
    def _command(commands, name: str, help_text: str, handler) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.add_argument("answers", type=Path, help=HELP_ANSWERS)
        command.set_defaults(handler=handler)
        return command

    def _create(self, args: argparse.Namespace) -> None:
        answers = DomainAnswers.read(args.answers)
        root = (args.into or DEVELOPER_ROOT / answers.name).expanduser()
        NewDomain(root, answers).create(CoreSource(args.core_url, args.core_branch))
        self._finish_with_the_folder_step(root, {"domain": str(root), "branch": DOMAIN_BRANCH})

    def _folders(self, args: argparse.Namespace) -> None:
        domain = ExistingDomain(args.domain)
        fields = JsonFields(JsonFile(args.answers).values(), str(args.answers))
        domain.add_folders(FolderAnswers.parsed(fields, domain.name))
        self._finish_with_the_folder_step(args.domain, {"domain": str(args.domain)})

    def _finish_with_the_folder_step(self, domain_root: Path, payload: dict) -> None:
        step = FolderStepAt(domain_root)
        report = step.report()
        step.run()
        self._print({**payload, "settings": DomainSettings(domain_root).blocks_of_domain_json(), "folders": report})

    @staticmethod
    def _print(payload: object) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


class FolderStepAt:
    def __init__(self, domain_root: Path) -> None:
        self._manifest_path = domain_root / MANIFEST_NAME
        self._step = FolderStep(DOCUMENTS.expanduser(), domain_root / VAULT_CONFIG_SOURCE, Machine())

    def report(self) -> dict:
        return self._step.report(DomainManifest.read(self._manifest_path))

    def run(self) -> None:
        self._step.run(DomainManifest.read(self._manifest_path))
