from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_core._domain.fields import JsonFields
from agent_core._domain.manifest import ACCESS_LEVELS, WRITE, JsonFile

UNATTENDED_READ_ONLY = "read-only"
UNATTENDED_NONE = "none"
UNATTENDED_LEVELS = (UNATTENDED_READ_ONLY, UNATTENDED_NONE)
VAULT_KEY = "vault"


@dataclass(frozen=True)
class FolderAnswer:
    name: str
    access: str
    sensitive: bool

    def as_manifest_entry(self) -> dict:
        entry = {"name": self.name, "access": self.access}
        return {**entry, "sensitive": True} if self.sensitive else entry


@dataclass(frozen=True)
class FolderAnswers:
    sensitive: bool
    vault: FolderAnswer | None
    others: tuple[FolderAnswer, ...]

    @classmethod
    def parsed(cls, fields: JsonFields, own_folder: str) -> FolderAnswers:
        sensitive = fields.flag("sensitive")
        others = tuple(cls._other(record, sensitive) for record in fields.records("folders"))
        return cls(sensitive, VaultAnswer(fields, own_folder).folder(sensitive), others)

    @staticmethod
    def _other(record: JsonFields, domain_is_sensitive: bool) -> FolderAnswer:
        sensitive = record.flag("sensitive") or domain_is_sensitive
        return FolderAnswer(record.text("name"), record.choice("access", ACCESS_LEVELS), sensitive)

    def every_folder(self) -> tuple[FolderAnswer, ...]:
        return self.others if self.vault is None else (self.vault, *self.others)

    def manifest_fields(self) -> dict:
        folders = {"folders": [folder.as_manifest_entry() for folder in self.every_folder()]}
        return folders if self.vault is None else {**folders, VAULT_KEY: self.vault.name}


class VaultAnswer:
    def __init__(self, fields: JsonFields, own_folder: str) -> None:
        self._fields = fields
        self._own_folder = own_folder

    def folder(self, sensitive: bool) -> FolderAnswer | None:
        name = self._name()
        return None if name is None else FolderAnswer(name, WRITE, sensitive)

    def _name(self) -> str | None:
        choice = self._fields.value(VAULT_KEY, True)
        if isinstance(choice, bool):
            return self._own_folder if choice else None
        return self._fields.text(VAULT_KEY)


@dataclass(frozen=True)
class DomainAnswers:
    source: Path
    name: str
    summary: str
    mandate: str
    folders: FolderAnswers
    fields: JsonFields

    @classmethod
    def read(cls, path: Path) -> DomainAnswers:
        fields = JsonFields(JsonFile(path).values(), str(path))
        name = fields.text("name")
        return cls(path, name, fields.text("summary"), fields.text("mandate"), FolderAnswers.parsed(fields, name),
                   fields)

    def manifest(self) -> dict:
        return {"name": self.name, "summary": self.summary, "handles": self.fields.value("handles", []),
                "entry_skills": list(self.fields.texts("entry_skills")),
                "exposure": self.fields.value("exposure", {}), **self.folders.manifest_fields(),
                "policy": self.fields.value("policy", {}), "unattended": self._unattended()}

    def _unattended(self) -> str:
        default = UNATTENDED_NONE if self.folders.sensitive else UNATTENDED_READ_ONLY
        return self.fields.optional_choice("unattended", UNATTENDED_LEVELS) or default

