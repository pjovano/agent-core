from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from agent_core._audit.replacement import ReplacementFile
from agent_core._audit.scope import ENCODING, RepositoryPath

BASELINE_PATH = Path("audit") / "baseline.json"
STATUS_NEW = "new"
STATUS_CHANGED = "changed"
STATUS_REMOVED = "removed"
_PARTIAL_SUFFIX = ".partial"


class CorruptBaseline(ValueError):
    pass


class Baseline:
    def __init__(self, path: Path, root: Path, today: date | None = None) -> None:
        self._path = path
        self._root = root
        self._today = date.today() if today is None else today

    def accepted_on(self) -> str | None:
        return self._recorded().get("accepted")

    def audited(self) -> dict:
        return self._recorded().get("digests", {})

    def changed(self, paths: list[Path]) -> dict[str, list[str]]:
        audited = self.audited()
        present = self._present(paths)
        return {STATUS_NEW: self._new(present, audited), STATUS_CHANGED: self._modified(present, audited),
                STATUS_REMOVED: sorted(name for name in audited if name not in present)}

    def accept(self, paths: list[Path]) -> dict:
        digests = self._present(paths)
        recorded = {"accepted": self._today.isoformat(), "digests": digests}
        self._write(recorded)
        return {"accepted": recorded["accepted"], "files": len(digests)}

    def _write(self, recorded: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with ReplacementFile(self._path, _PARTIAL_SUFFIX) as replacement:
            replacement.path.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding=ENCODING)
            replacement.commit()

    def _present(self, paths: list[Path]) -> dict[str, str]:
        return {RepositoryPath(path, self._root).label(): self._digest(path) for path in paths}

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _new(present: dict, audited: dict) -> list[str]:
        return sorted(name for name in present if name not in audited)

    @staticmethod
    def _modified(present: dict, audited: dict) -> list[str]:
        return sorted(name for name, digest in present.items() if name in audited and audited[name] != digest)

    def _recorded(self) -> dict:
        try:
            text = self._path.read_text(encoding=ENCODING)
        except FileNotFoundError:
            return {}
        return self._parsed(text)

    def _parsed(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise CorruptBaseline(f"the audit baseline {self._path} is not valid JSON ({error}); restore it "
                                  f"from git and run the command again") from error
