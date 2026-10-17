from __future__ import annotations

import re
from collections.abc import Iterable

MACHINE_PATH = re.compile(r"(?:^|[\s(])/")


class ManifestError(Exception):
    pass


class JsonFields:
    def __init__(self, values: object, where: str) -> None:
        if not isinstance(values, dict):
            raise ManifestError(f"{where}: expected a JSON object")
        self._values = values
        self._where = where

    def refuse_unknown(self, known: Iterable[str]) -> None:
        unknown = sorted(set(self._values) - set(known))
        if unknown:
            raise ManifestError(f"{self._where}: unknown keys {unknown}")

    def text(self, key: str) -> str:
        value = self._values.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(f"{self._where}: `{key}` must be a non-empty string")
        return value

    def optional_text(self, key: str) -> str | None:
        return self.text(key) if key in self._values else None

    def texts(self, key: str) -> tuple[str, ...]:
        values = self._values.get(key, [])
        if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
            raise ManifestError(f"{self._where}: `{key}` must be a list of non-empty strings")
        return tuple(self._without_machine_path(key, value) for value in values)

    def labels(self, key: str) -> dict[str, str]:
        values = self._values.get(key, {})
        if not isinstance(values, dict) or not all(isinstance(value, str) for value in values.values()):
            raise ManifestError(f"{self._where}: `{key}` must map each string to a string")
        return {self._without_machine_path(key, name): label for name, label in values.items()}

    def flag(self, key: str) -> bool:
        value = self._values.get(key, False)
        if not isinstance(value, bool):
            raise ManifestError(f"{self._where}: `{key}` must be true or false")
        return value

    def choice(self, key: str, allowed: tuple[str, ...]) -> str:
        value = self._values.get(key)
        if value not in allowed:
            raise ManifestError(f"{self._where}: `{key}` must be one of {list(allowed)}, not {value!r}")
        return value

    def optional_choice(self, key: str, allowed: tuple[str, ...]) -> str | None:
        return self.choice(key, allowed) if key in self._values else None

    def value(self, key: str, default: object) -> object:
        return self._values.get(key, default)

    def records(self, key: str) -> list[JsonFields]:
        values = self._values.get(key, [])
        if not isinstance(values, list):
            raise ManifestError(f"{self._where}: `{key}` must be a list")
        return [JsonFields(value, f"{self._where}: {key}[{index}]") for index, value in enumerate(values)]

    def section(self, key: str) -> JsonFields:
        return JsonFields(self._values.get(key, {}), f"{self._where}: {key}")

    def refuse(self, problem: str) -> ManifestError:
        return ManifestError(f"{self._where}: {problem}")

    def _without_machine_path(self, key: str, value: str) -> str:
        if MACHINE_PATH.search(value):
            raise ManifestError(f"{self._where}: `{key}` names a path beginning with `/`: {value!r}; "
                                "name a path under `~` instead")
        return value
