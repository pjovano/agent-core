from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from agent_core._audit.scope import Scope

if TYPE_CHECKING:
    from agent_core._audit.cli import AuditSet

CHECKS_PATH = Path("audit") / "checks.py"
DOMAIN_NAME = "DOMAIN"
SKIPPED_KEY = "skipped"
MODULE_PREFIX = "_domain_audit_checks_"
MODULE_DIGEST_LENGTH = 16


class LintCheck(Protocol):
    name: str

    def findings(self, audit_set: AuditSet) -> list[dict]: ...


class ReportCheck(Protocol):
    name: str
    help: str

    def report(self, root: Path) -> dict: ...


class Presence(Protocol):
    def is_present(self) -> bool: ...

    def absence(self) -> str: ...


@dataclass(frozen=True)
class DomainChecks:
    scope: Scope = field(default_factory=Scope)
    lint: tuple[LintCheck, ...] = ()
    reports: tuple[ReportCheck, ...] = ()


class PrimaryOnly:
    def __init__(self, check: ReportCheck, presence: Presence) -> None:
        self._check = check
        self._presence = presence

    @property
    def name(self) -> str:
        return self._check.name

    @property
    def help(self) -> str:
        return self._check.help

    def report(self, root: Path) -> dict:
        if self._presence.is_present():
            return self._check.report(root)
        return {SKIPPED_KEY: self._presence.absence()}


class DomainChecksMissing(LookupError):
    pass


class DomainChecksFile:
    def __init__(self, root: Path) -> None:
        self._path = root / CHECKS_PATH

    def loaded(self) -> DomainChecks:
        if not self._path.is_file():
            return DomainChecks()
        module = self._module()
        if not hasattr(module, DOMAIN_NAME):
            raise DomainChecksMissing(f"{self._path} defines no {DOMAIN_NAME}; define it as a DomainChecks")
        return getattr(module, DOMAIN_NAME)

    def _module(self):
        name = MODULE_PREFIX + hashlib.sha256(str(self._path.resolve()).encode()).hexdigest()[:MODULE_DIGEST_LENGTH]
        specification = importlib.util.spec_from_file_location(name, self._path)
        module = importlib.util.module_from_spec(specification)
        sys.modules[name] = module
        specification.loader.exec_module(module)
        return module
