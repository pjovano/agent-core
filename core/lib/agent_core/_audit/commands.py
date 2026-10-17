from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Protocol

FAILURES_KEY = "failures"
FLAG_NEW = "--new"
HELP_NEW = "leave out every row whose fingerprint the audit baseline acknowledges"
HELP_PROSE = "the prose rows of the named instruction files, or of every instruction file"
HELP_PATHS = "the instruction files to lint; if none is named, every instruction file"
HELP_ACKNOWLEDGE = "record lint rows as acknowledged in the audit baseline, each with its reason"
HELP_FINGERPRINTS = "the fingerprints of the rows"
HELP_REASON = "why the rows stand"
HELP_EVERY_ROW = "acknowledge every row the lint prints that the audit baseline does not acknowledge"
HELP_DISMISS = "remove acknowledgements from the audit baseline"
HELP_RATCHET = "fail if the instruction text grew since the base commit without a stated reason"
HELP_BASE = "the base commit of the pull request"
HELP_BODY = "a file holding the pull request's body"

Handler = Callable[[argparse.Namespace], dict]


class Subcommand:
    def __init__(self, name: str, help_text: str, handler: Handler) -> None:
        self._name = name
        self._help = help_text
        self._handler = handler

    def added_to(self, commands: argparse._SubParsersAction) -> argparse.ArgumentParser:
        command = commands.add_parser(self._name, help=self._help)
        command.set_defaults(handler=self._handler)
        return command


class LintedDomain(Protocol):
    def prose(self, args: argparse.Namespace) -> dict: ...

    def acknowledge(self, args: argparse.Namespace) -> dict: ...

    def dismiss(self, args: argparse.Namespace) -> dict: ...

    def ratchet(self, args: argparse.Namespace) -> dict: ...


class LintCommands:
    def __init__(self, domain: LintedDomain) -> None:
        self._domain = domain

    def added_to(self, commands: argparse._SubParsersAction) -> None:
        prose = Subcommand("prose", HELP_PROSE, self._domain.prose).added_to(commands)
        prose.add_argument(FLAG_NEW, action="store_true", help=HELP_NEW)
        prose.add_argument("paths", nargs="*", type=Path, help=HELP_PATHS)
        acknowledge = Subcommand("acknowledge", HELP_ACKNOWLEDGE, self._domain.acknowledge).added_to(commands)
        acknowledge.add_argument("--reason", required=True, help=HELP_REASON)
        chosen = acknowledge.add_mutually_exclusive_group(required=True)
        chosen.add_argument("--every-row", action="store_true", help=HELP_EVERY_ROW)
        chosen.add_argument("fingerprints", nargs="*", default=[], help=HELP_FINGERPRINTS)
        dismiss = Subcommand("dismiss", HELP_DISMISS, self._domain.dismiss).added_to(commands)
        dismiss.add_argument("fingerprints", nargs="+", help=HELP_FINGERPRINTS)
        ratchet = Subcommand("ratchet", HELP_RATCHET, self._domain.ratchet).added_to(commands)
        ratchet.add_argument("--base", required=True, help=HELP_BASE)
        ratchet.add_argument("--body-file", type=Path, help=HELP_BODY)


class ParserNames:
    def __init__(self, parser: argparse.ArgumentParser) -> None:
        self._parser = parser

    def names(self) -> frozenset[str]:
        return frozenset(self._of(self._parser))

    def _of(self, parser: argparse.ArgumentParser) -> set[str]:
        names = set()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    names |= {name} | self._of(child)
        return names
