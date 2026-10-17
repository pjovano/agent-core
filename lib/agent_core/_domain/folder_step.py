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

    def run(self, manifest: DomainManifest) -> dict:
        if self.machine.is_cloud_session:
            return {"created": [], "refused": CLOUD_REFUSAL}
        created = {folder.name: self._prepared(folder) for folder in manifest.folders}
        if manifest.vault is not None:
            created[manifest.vault]["vault_config"] = self._made_a_vault(manifest.vault)
        return {"created": list(created.values())}

    def _prepared(self, folder: Folder) -> dict:
        path = self.documents / folder.name
        existed = path.is_dir()
        path.mkdir(parents=True, exist_ok=True)
        return {"folder": f"{DOCUMENTS}/{folder.name}", "existed": existed, "vault_config": []}

    def _made_a_vault(self, vault: str) -> list[str]:
        return VaultConfig(self.vault_config).copied_into(self.documents / vault)


class VaultConfig:
    def __init__(self, source: Path) -> None:
        self._source = source

    def copied_into(self, folder: Path) -> list[str]:
        target_dir = folder / VAULT_CONFIG_TARGET
        missing = [path for path in self._files() if not (target_dir / path).exists()]
        for relative in missing:
            (target_dir / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._source / relative, target_dir / relative)
        return [(VAULT_CONFIG_TARGET / relative).as_posix() for relative in missing]

    def _files(self) -> list[Path]:
        return [path.relative_to(self._source) for path in sorted(self._source.rglob("*")) if path.is_file()]
