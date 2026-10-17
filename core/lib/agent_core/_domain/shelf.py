from __future__ import annotations

from pathlib import Path

from agent_core._domain.manifest import MANIFEST_NAME, DomainManifest

DEVELOPER_ROOT = Path("~/Developer")


class ManifestShelf:
    def __init__(self, named: list[Path], developer_root: Path = DEVELOPER_ROOT) -> None:
        self._named = named
        self._developer_root = developer_root

    def manifests(self) -> list[DomainManifest]:
        return [DomainManifest.read(path) for path in self._paths()]

    def _paths(self) -> list[Path]:
        if self._named:
            return list(self._named)
        return sorted(self._developer_root.expanduser().glob(f"*/{MANIFEST_NAME}"))
