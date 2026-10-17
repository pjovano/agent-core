from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from agent_core._audit.checks import DomainChecks
from agent_core._audit.clones import CloneCheck
from agent_core._audit.magic import MagicNumbers
from agent_core._audit.measures import CodeMeasures
from agent_core._audit.pointers import InstructionPointers
from agent_core._audit.prose import ProseCheck
from agent_core._audit.redundancy import CopyGroup, RedundancyCheck
from agent_core._audit.rows import Acknowledged, Fingerprints
from agent_core._audit.ruff import RuffMissing, RuffRows
from agent_core._audit.scope import CONTRACT_GROUP, ControlPlaneFiles
from agent_core._audit.special import CodeFiles, SpecialCheck
from agent_core._audit.staleness import StalenessCheck
from agent_core._audit.weight import OwnedInstructions, WeightRow
from agent_core._audit.xref import XrefCheck, XrefPlane, XrefSettings

if TYPE_CHECKING:
    from agent_core._audit.cli import AuditSet

SKIPPED_KEY = "skipped"
WEIGHT_KEY = "weight"
CODE_SUFFIX = ".py"


@dataclass(frozen=True)
class LintInputs:
    audit_set: AuditSet
    files: ControlPlaneFiles
    checks: DomainChecks
    known: dict[str, frozenset[str]]


class Lint:
    def __init__(self, inputs: LintInputs, recorded_weight: dict | None) -> None:
        self._inputs = inputs
        self._recorded_weight = recorded_weight
        self._root = inputs.files.root
        self._skipped: dict[str, str] = {}

    def payload(self) -> dict:
        audit_set = self._inputs.audit_set
        rows = {"code": self._code(), "pointers": InstructionPointers(audit_set.instructions(), self._inputs.files)
                .findings(), "prose": ProseCheck(audit_set.instructions(), self._root).rows(),
                "xref": self._xref(), "redundancy": self._redundancy(), "staleness": self._staleness(),
                "special": SpecialCheck(CodeFiles(audit_set.pipeline_code(), self._tests(), self._root)).rows()}
        for check in self._inputs.checks.lint:
            rows[check.name] = rows.get(check.name, []) + check.findings(audit_set)
        stamped = {name: Fingerprints(self._root).stamped(value) for name, value in rows.items()}
        weight = WeightRow(OwnedInstructions(self._inputs.files).texts().counts(), self._recorded_weight)
        return {"files": audit_set.counts(), **stamped, WEIGHT_KEY: weight.as_dict(),
                **({SKIPPED_KEY: self._skipped} if self._skipped else {})}

    def unacknowledged(self, acknowledged: dict[str, str]) -> dict:
        filtered = Acknowledged(acknowledged)
        return {name: filtered.unacknowledged(value) if isinstance(value, list) else value
                for name, value in self.payload().items()}

    def _code(self) -> list[dict]:
        code = self._inputs.audit_set.code()
        rows = CodeMeasures(code, self._root).findings()
        try:
            rows += RuffRows(code, self._root).rows()
        except RuffMissing as missing:
            self._skipped["code"] = str(missing)
        pipeline = self._inputs.audit_set.pipeline_code()
        return rows + MagicNumbers(pipeline, self._root).findings() + CloneCheck(pipeline, self._root).rows()

    def _xref(self) -> list[dict]:
        settings = XrefSettings(self._inputs.checks.contract, self._inputs.known)
        plane = XrefPlane(self._inputs.audit_set.instructions(), self._everything(("code",)), self._inputs.files)
        return XrefCheck(plane, settings).rows()

    def _redundancy(self) -> list[dict]:
        grouped = self._inputs.files.by_group()
        return RedundancyCheck([CopyGroup(self._markdown(grouped.get(CONTRACT_GROUP, []))),
                                CopyGroup(self._markdown(grouped.get("skills", []))),
                                CopyGroup(self._markdown(grouped.get("workers", [])), crosses_a_boundary=True)],
                               self._root).rows()

    @staticmethod
    def _markdown(paths: list[Path]) -> list[Path]:
        return [path for path in paths if path.suffix == ".md"]

    def _staleness(self) -> list[dict]:
        contract = self._inputs.files.of_groups((CONTRACT_GROUP,))
        return StalenessCheck(self._inputs.audit_set.instructions(), contract, self._root).rows()

    def _tests(self) -> list[Path]:
        return self._everything(("tests",))

    def _everything(self, groups: tuple[str, ...]) -> list[Path]:
        return [path for path in self._inputs.files.of_groups(groups) if path.suffix == CODE_SUFFIX]
