from __future__ import annotations

import os
import re
from pathlib import Path

ENCODING = "utf-8"
MAX_TITLE_WORDS = 12
MAX_NAME_LENGTH = 80
NAME_SEPARATOR = "-"
RECORD_SUFFIX = ".md"
PARTIAL_SUFFIX = ".partial"
WORD = re.compile(r"[a-z0-9]+")


class RecordError(ValueError):
    pass


class TitleTooLong(RecordError):
    pass


class NameTaken(RecordError):
    pass


class RecordName:
    def __init__(self, title: str) -> None:
        self._title = title

    def text(self) -> str:
        words = WORD.findall(self._title.lower())
        if len(words) > MAX_TITLE_WORDS:
            raise TitleTooLong(f"the title {self._title!r} holds more than {MAX_TITLE_WORDS} words")
        return NAME_SEPARATOR.join(words)[:MAX_NAME_LENGTH] + RECORD_SUFFIX


def refuse_a_taken_name(path: Path) -> None:
    if path.exists():
        raise NameTaken(f"the ledger already holds {path.name}")


HOOKS = {"pre-write": refuse_a_taken_name}


def write_atomically(path: Path, text: str) -> None:
    HOOKS["pre-write"](path)
    partial = path.with_suffix(PARTIAL_SUFFIX)
    partial.write_text(text, encoding=ENCODING)
    os.replace(partial, path)
