from __future__ import annotations

from pathlib import Path

from agent_core._audit.scope import ENCODING, ControlPlaneFiles


class RelatedFiles:
    def __init__(self, files: ControlPlaneFiles) -> None:
        self._files = files

    def of(self, changed: list[Path]) -> list[Path]:
        if not changed:
            return []
        names = {token for path in changed for token in self._reference_tokens(path)}
        candidates = [path for path in self._files.all() if path not in changed]
        return sorted(path for path in candidates if self._names_any(path, names))

    @staticmethod
    def _reference_tokens(path: Path) -> set[str]:
        return {path.name, f"import {path.stem}", f"from {path.stem} import", f".{path.stem} import"}

    @staticmethod
    def _names_any(path: Path, names: set[str]) -> bool:
        try:
            text = path.read_text(encoding=ENCODING)
        except UnicodeDecodeError as error:
            raise ValueError(f"{path}: not UTF-8") from error
        return any(name in text for name in names)
