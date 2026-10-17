from __future__ import annotations

import re

DEFECT_TRAILER = re.compile(r"^Defect-class:[ \t]*\S", re.MULTILINE)
CHANGE_TRAILER = re.compile(r"^Change-class:[ \t]*(refactor|feature)[ \t]+—[ \t]+\S", re.MULTILINE)
DEFECT = "defect"
FEATURE = "feature"
REFACTOR = "refactor"
UNTRAILERED = "none"
GROWING_CLASSES = (DEFECT, FEATURE)


class CommitClass:
    def __init__(self, message: str) -> None:
        self._message = message

    def name(self) -> str:
        if DEFECT_TRAILER.search(self._message):
            return DEFECT
        change = CHANGE_TRAILER.search(self._message)
        return change.group(1) if change else UNTRAILERED

    def carries_a_trailer(self) -> bool:
        return self.name() != UNTRAILERED

    def may_grow_the_text(self) -> bool:
        return self.name() in GROWING_CLASSES
