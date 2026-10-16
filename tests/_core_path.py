from __future__ import annotations

import sys

from _repository import REPOSITORY_ROOT

CORE_LIB = REPOSITORY_ROOT / "core" / "lib"
BIN_DIR = REPOSITORY_ROOT / "bin"


class CoreModulePath:
    @staticmethod
    def activate() -> None:
        for directory in (CORE_LIB, BIN_DIR):
            entry = str(directory)
            if entry not in sys.path:
                sys.path.insert(0, entry)
