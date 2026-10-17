from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from agent_core._domain.manifest import DomainManifest, Folder

DOCUMENTS = Path("~/Documents")
VAULT_CONFIG_SOURCE = Path("obsidian")
VAULT_CONFIG_TARGET = Path(".obsidian")
CLOUD_SESSION_VARIABLE = "CLAUDE_CODE_REMOTE"
CLOUD_SESSION_VALUE = "true"
CLOUD_REFUSAL = ("a cloud session creates no folder: the folders live on the primary; run the folder step there "
                 "to create them")


class Machine:
    def __init__(self, environment: Mapping[str, str] = os.environ) -> None:
        self._environment = environment

    @property
    def is_cloud_session(self) -> bool:
        return self._environment.get(CLOUD_SESSION_VARIABLE) == CLOUD_SESSION_VALUE


@dataclass(frozen=True)
class FolderStep:
    documents: Path
    vault_config: Path
    machine: Machine

    def report(self, manifest: DomainManifest) -> dict:
        if self.machine.is_cloud_session:
            return {"created": [], "refused": CLOUD_REFUSAL}
        entries = {folder.name: self._entry(folder) for folder in manifest.folders}
        if manifest.vault is not None:
            entries[manifest.vault]["vault_config"] = self._missing_vault_config(manifest.vault)
        return {"created": list(entries.values())}

    def run(self, manifest: DomainManifest) -> None:
        if self.machine.is_cloud_session:
            return
        for folder in manifest.folders:
            (self.documents / folder.name).mkdir(parents=True, exist_ok=True)
        if manifest.vault is not None:
            VaultConfig(self.vault_config).copy_into(self.documents / manifest.vault)

    def _entry(self, folder: Folder) -> dict:
        existed = (self.documents / folder.name).is_dir()
        return {"folder": f"{DOCUMENTS}/{folder.name}", "existed": existed, "vault_config": []}

    def _missing_vault_config(self, vault: str) -> list[str]:
        missing = VaultConfig(self.vault_config).missing_in(self.documents / vault)
        return [(VAULT_CONFIG_TARGET / relative).as_posix() for relative in missing]


class VaultConfig:
    def __init__(self, source: Path) -> None:
        self._source = source

    def missing_in(self, folder: Path) -> list[Path]:
        return [relative for relative in self._files() if not (folder / VAULT_CONFIG_TARGET / relative).exists()]

    def copy_into(self, folder: Path) -> None:
        for relative in self.missing_in(folder):
            target = folder / VAULT_CONFIG_TARGET / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._source / relative, target)

    def _files(self) -> list[Path]:
        return [path.relative_to(self._source) for path in sorted(self._source.rglob("*")) if path.is_file()]
