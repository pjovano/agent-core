from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agent_core._audit.bench import MANIFEST_NAME, WINDOW_LINES, BenchError
from agent_core._audit.scope import ENCODING

LINT_LAYER = "lint"
SHORTEST_COMMIT_PREFIX = 7
RECALL_DIGITS = 3
FINDING_FIELDS = ("check", "file", "line", "layer")


@dataclass(frozen=True)
class Finding:
    check: str
    file: str
    line: int
    layer: str

    @classmethod
    def of(cls, fields: dict) -> Finding:
        missing = [name for name in FINDING_FIELDS if name not in fields]
        if missing:
            raise BenchError(f"the finding {json.dumps(fields, ensure_ascii=False)} lacks {', '.join(missing)}")
        return cls(str(fields["check"]), str(fields["file"]), int(fields["line"]), str(fields["layer"]))

    def as_dict(self) -> dict:
        return {"check": self.check, "file": self.file, "line": self.line, "layer": self.layer}


class FindingsFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def findings(self) -> list[Finding]:
        try:
            payload = json.loads(self._path.read_text(encoding=ENCODING))
        except (OSError, json.JSONDecodeError) as error:
            raise BenchError(f"the findings file {self._path} cannot be read as JSON ({error})") from error
        if isinstance(payload, dict):
            return self._lint_findings(payload)
        return [Finding.of(fields) for fields in payload]

    @staticmethod
    def _lint_findings(payload: dict) -> list[Finding]:
        rows = [(check, row) for check, value in payload.items() if isinstance(value, list) for row in value]
        return [Finding.of({**row, "check": check, "layer": LINT_LAYER}) for check, row in rows]


class Location(Protocol):
    def covers(self, finding: Finding) -> bool: ...


@dataclass(frozen=True)
class FileSpan:
    file: str
    line: int
    end: int

    def covers(self, finding: Finding) -> bool:
        return finding.file == self.file and self.line - WINDOW_LINES <= finding.line <= self.end + WINDOW_LINES


@dataclass(frozen=True)
class Commit:
    sha: str

    def covers(self, finding: Finding) -> bool:
        return len(finding.file) >= SHORTEST_COMMIT_PREFIX and self.sha.startswith(finding.file)


@dataclass(frozen=True)
class PlacedSeed:
    seed_id: str
    check: str
    negative: bool
    location: Location

    @classmethod
    def of(cls, entry: dict) -> PlacedSeed:
        if "commit" in entry:
            location = Commit(entry["commit"])
        else:
            location = FileSpan(entry["file"], entry["line"], entry["end"])
        return cls(entry["id"], entry["check"], entry["negative"], location)

    def is_found_by(self, finding: Finding) -> bool:
        return finding.check == self.check and self.location.covers(finding)


class Manifest:
    def __init__(self, directory: Path) -> None:
        self._path = directory / MANIFEST_NAME

    def seeds(self) -> list[PlacedSeed]:
        if not self._path.is_file():
            raise BenchError(f"no bench manifest at {self._path}; run bench build on the directory first")
        return [PlacedSeed.of(entry) for entry in json.loads(self._path.read_text(encoding=ENCODING))["seeds"]]


class Recall:
    def __init__(self, seeds: list[PlacedSeed], findings: list[Finding]) -> None:
        self._seeds = seeds
        self._findings = findings

    def found(self) -> list[PlacedSeed]:
        return [seed for seed in self._seeds if any(seed.is_found_by(finding) for finding in self._findings)]

    def as_dict(self) -> dict:
        checks = sorted({seed.check for seed in self._seeds})
        per_check = {check: self._of([seed for seed in self._seeds if seed.check == check]) for check in checks}
        return {**self._of(self._seeds), "per_check": per_check}

    def _of(self, seeds: list[PlacedSeed]) -> dict:
        found = len(Recall(seeds, self._findings).found())
        return {"seeds": len(seeds), "found": found, "recall": round(found / len(seeds), RECALL_DIGITS)}


class BenchScore:
    def __init__(self, seeds: list[PlacedSeed], findings: list[Finding]) -> None:
        self._positive = [seed for seed in seeds if not seed.negative]
        self._negative = [seed for seed in seeds if seed.negative]
        self._findings = findings

    def report(self) -> dict:
        found = {seed.seed_id for seed in Recall(self._positive, self._findings).found()}
        return {**Recall(self._positive, self._findings).as_dict(), "per_layer": self._per_layer(),
                "negative_seeds": len(self._negative),
                "missed": [seed.seed_id for seed in self._positive if seed.seed_id not in found],
                "false_positives": self._false_positives(), "unmatched": self._unmatched()}

    def _per_layer(self) -> dict:
        layers = sorted({finding.layer for finding in self._findings})
        return {layer: Recall(self._positive, self._of_layer(layer)).as_dict() for layer in layers}

    def _of_layer(self, layer: str) -> list[Finding]:
        return [finding for finding in self._findings if finding.layer == layer]

    def _false_positives(self) -> list[dict]:
        return [{"seed": seed.seed_id, "finding": finding.as_dict()} for seed in self._negative
                for finding in self._findings if seed.location.covers(finding)]

    def _unmatched(self) -> list[dict]:
        return [finding.as_dict() for finding in self._findings if not self._is_placed(finding)]

    def _is_placed(self, finding: Finding) -> bool:
        return (any(seed.is_found_by(finding) for seed in self._positive)
                or any(seed.location.covers(finding) for seed in self._negative))
