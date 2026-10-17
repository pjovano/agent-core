from __future__ import annotations

import os
from pathlib import Path


class ReplacementFile:
    def __init__(self, target: Path, suffix: str) -> None:
        self._target = target
        self._partial = target.with_suffix(suffix)
        self._committed = False

    @property
    def path(self) -> Path:
        return self._partial

    def commit(self) -> None:
        self._flush_to_disk()
        self._partial.replace(self._target)
        self._committed = True

    def _flush_to_disk(self) -> None:
        descriptor = os.open(self._partial, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def __enter__(self) -> ReplacementFile:
        return self

    def __exit__(self, *_exception) -> None:
        if not self._committed:
            self._partial.unlink(missing_ok=True)
