from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _core_path import CoreModulePath
from _repository import REPOSITORY_ROOT

CoreModulePath.activate()

DEVELOPER_FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "developer"
RESEARCH_MANIFEST = DEVELOPER_FIXTURE / "research" / "domain.json"
PERSONAL_MANIFEST = DEVELOPER_FIXTURE / "personal" / "domain.json"
LEDGER_MANIFEST = DEVELOPER_FIXTURE / "ledger" / "domain.json"
DOMAIN_SCRIPT = REPOSITORY_ROOT / "core" / "domain.py"
MINIMAL_MANIFEST = {"name": "minimal", "summary": "Holds nothing."}


class ManifestDraft:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def written(self, values: object, name: str = "minimal") -> Path:
        domain_dir = self._directory / name
        domain_dir.mkdir(exist_ok=True)
        path = domain_dir / "domain.json"
        path.write_text(json.dumps(values), encoding="utf-8")
        return path

    def with_folders(self, *folders: dict) -> Path:
        return self.written({**MINIMAL_MANIFEST, "folders": list(folders)})

    def with_policy(self, policy: dict, *folders: dict) -> Path:
        return self.written({**MINIMAL_MANIFEST, "folders": list(folders), "policy": policy})


class DomainScript:
    @staticmethod
    def run(*arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(DOMAIN_SCRIPT), *arguments], capture_output=True, text=True,
                              cwd=REPOSITORY_ROOT)
