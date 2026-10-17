from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_core._domain.fields import ManifestError
from agent_core._domain.manifest import MANIFEST_NAME, DomainManifest
from agent_core._domain.settings import SettingsBlocks
from agent_core._domain.shelf import DEVELOPER_ROOT, ManifestShelf

PROGRAM = "domain.py"
DESCRIPTION = "Read the domains' manifests, and generate a domain's settings blocks from them."
EXIT_FAILURE = 1
HELP_MANIFESTS = f"list every manifest: each named one, or every {DEVELOPER_ROOT}/*/{MANIFEST_NAME}"
HELP_SETTINGS = ("print the `permissions` and `sandbox` blocks of the domain's .claude/settings.json, "
                 "guarding every sensitive folder of the other manifests")
HELP_NAMED = f"the manifests to read; if none, every {MANIFEST_NAME} one level under the developer root"
HELP_DEVELOPER = f"the directory whose subdirectories hold the domains; default {DEVELOPER_ROOT}"
HELP_DOMAIN = f"the manifest of the domain whose settings to generate; default ./{MANIFEST_NAME}"


class CommandLine:
    def run(self, argv: list[str]) -> None:
        try:
            self._run(argv)
        except ManifestError as error:
            self._print({"error": str(error)})
            sys.exit(EXIT_FAILURE)

    def _run(self, argv: list[str]) -> None:
        parser = self._parser()
        args = parser.parse_args(argv)
        if args.handler is None:
            parser.print_help()
            return
        self._print(args.handler(args))

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=PROGRAM, description=DESCRIPTION)
        parser.set_defaults(handler=None)
        commands = parser.add_subparsers(dest="command")
        self._shelf_command(commands, "manifests", HELP_MANIFESTS, self._manifests)
        settings = self._shelf_command(commands, "settings", HELP_SETTINGS, self._settings)
        settings.add_argument("--domain", type=Path, default=Path(MANIFEST_NAME), help=HELP_DOMAIN)
        return parser

    @staticmethod
    def _shelf_command(commands, name: str, help_text: str, handler) -> argparse.ArgumentParser:
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.add_argument("named", nargs="*", type=Path, metavar="MANIFEST", help=HELP_NAMED)
        command.add_argument("--developer", type=Path, default=DEVELOPER_ROOT, help=HELP_DEVELOPER)
        command.set_defaults(handler=handler)
        return command

    @staticmethod
    def _manifests(args: argparse.Namespace) -> list[dict]:
        manifests = ManifestShelf(args.named, args.developer).manifests()
        return [ManifestListing(manifest).as_dict() for manifest in manifests]

    @staticmethod
    def _settings(args: argparse.Namespace) -> dict:
        neighbours = ManifestShelf(args.named, args.developer).manifests()
        return SettingsBlocks(DomainManifest.read(args.domain), neighbours).as_dict()

    @staticmethod
    def _print(payload: object) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


class ManifestListing:
    def __init__(self, manifest: DomainManifest) -> None:
        self._manifest = manifest

    def as_dict(self) -> dict:
        folders = [{"name": folder.name, "access": folder.access, "sensitive": folder.sensitive}
                   for folder in self._manifest.folders]
        return {"name": self._manifest.name, "summary": self._manifest.summary,
                "path": HomeRelative(self._manifest.path).text(), "folders": folders}


class HomeRelative:
    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()

    def text(self) -> str:
        home = Path.home().resolve()
        if self._path.is_relative_to(home):
            return f"~/{self._path.relative_to(home).as_posix()}"
        return self._path.as_posix()
