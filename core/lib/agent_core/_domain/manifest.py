from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from agent_core._domain.fields import JsonFields, ManifestError

MANIFEST_NAME = "domain.json"
DOCUMENTS = "~/Documents"
HOME = "~"
READ = "read"
WRITE = "write"
ACCESS_LEVELS = (READ, WRITE)
PARENT_SEGMENT = ".."
FOLDER_KEYS = ("name", "access", "sensitive", "write_within")
POLICY_KEYS = ("allow", "prompt_on", "network_hosts", "allow_local_binding", "write_paths", "excluded_commands")
FILE_TOOL_RULE = re.compile(r"^(?:Edit|Write)\(~/Documents/(?P<folder>[^/)]+)")


@dataclass(frozen=True)
class Folder:
    name: str
    access: str
    sensitive: bool
    write_within: tuple[str, ...]

    @classmethod
    def parsed(cls, fields: JsonFields) -> Folder:
        fields.refuse_unknown(FOLDER_KEYS)
        folder = cls(FolderName(fields).value(), fields.choice("access", ACCESS_LEVELS), fields.flag("sensitive"),
                     fields.texts("write_within"))
        folder._check_write_within(fields)
        return folder

    @property
    def path(self) -> str:
        return f"{DOCUMENTS}/{self.name}"

    @property
    def is_writable(self) -> bool:
        return self.access == WRITE

    def write_paths(self) -> list[str]:
        if not self.write_within:
            return [self.path]
        return [f"{self.path}/{subfolder}" for subfolder in self.write_within]

    def _check_write_within(self, fields: JsonFields) -> None:
        if self.write_within and not self.is_writable:
            raise fields.refuse("`write_within` narrows a `write` folder; a `read` folder grants no write")
        for subfolder in self.write_within:
            if not RelativeSubpath(subfolder).stays_inside():
                raise fields.refuse(f"`write_within` entry {subfolder!r} must stay inside the folder")


class FolderName:
    def __init__(self, fields: JsonFields) -> None:
        self._fields = fields

    def value(self) -> str:
        name = self._fields.text("name")
        if "/" in name or name in (".", PARENT_SEGMENT):
            raise self._fields.refuse(f"folder name {name!r} must name one folder directly in {DOCUMENTS}")
        return name


class RelativeSubpath:
    def __init__(self, text: str) -> None:
        self._path = PurePosixPath(text)

    def stays_inside(self) -> bool:
        return not self._path.is_absolute() and PARENT_SEGMENT not in self._path.parts


@dataclass(frozen=True)
class Policy:
    allow: tuple[str, ...]
    prompt_on: dict[str, str]
    network_hosts: tuple[str, ...]
    allow_local_binding: bool
    write_paths: tuple[str, ...]
    excluded_commands: tuple[str, ...]

    @classmethod
    def parsed(cls, fields: JsonFields) -> Policy:
        fields.refuse_unknown(POLICY_KEYS)
        policy = cls(fields.texts("allow"), fields.labels("prompt_on"), fields.texts("network_hosts"),
                     fields.flag("allow_local_binding"), fields.texts("write_paths"),
                     fields.texts("excluded_commands"))
        policy._check_write_paths(fields)
        return policy

    def file_tool_folders(self) -> set[str]:
        matches = (FILE_TOOL_RULE.match(rule) for rule in self.allow)
        return {match["folder"] for match in matches if match}

    def _check_write_paths(self, fields: JsonFields) -> None:
        for path in self.write_paths:
            if not OutsideDocuments(path).holds():
                raise fields.refuse(f"`write_paths` entry {path!r} must sit under `{HOME}/` and outside "
                                    f"`{DOCUMENTS}`, whose folders `folders` grants")


class OutsideDocuments:
    def __init__(self, path: str) -> None:
        self._path = PurePosixPath(path)

    def holds(self) -> bool:
        parts = self._path.parts
        under_home = len(parts) > 1 and parts[0] == HOME and PARENT_SEGMENT not in parts
        return under_home and not self._path.is_relative_to(DOCUMENTS)


@dataclass(frozen=True)
class DomainManifest:
    path: Path
    name: str
    summary: str
    folders: tuple[Folder, ...]
    policy: Policy

    @classmethod
    def read(cls, path: Path) -> DomainManifest:
        fields = JsonFields(ManifestFile(path).values(), str(path))
        folders = tuple(Folder.parsed(record) for record in fields.records("folders"))
        manifest = cls(path, fields.text("name"), fields.text("summary"), folders,
                       Policy.parsed(fields.section("policy")))
        manifest._check_consistency(fields)
        return manifest

    def folder_names(self) -> set[str]:
        return {folder.name for folder in self.folders}

    def writable_folders(self) -> list[Folder]:
        return [folder for folder in self.folders if folder.is_writable]

    def sensitive_folders(self) -> list[Folder]:
        return [folder for folder in self.folders if folder.sensitive]

    def _check_consistency(self, fields: JsonFields) -> None:
        if len(self.folder_names()) != len(self.folders):
            raise fields.refuse("`folders` names one folder twice")
        stray = self.policy.file_tool_folders() - {folder.name for folder in self.writable_folders()}
        if stray:
            raise fields.refuse(f"`policy.allow` grants the Edit or Write tool in {sorted(stray)}, "
                                "which `folders` does not list as `write`")


class ManifestFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def values(self) -> object:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except OSError as error:
            raise ManifestError(f"{self._path}: cannot be read: {error.strerror}") from error
        except json.JSONDecodeError as error:
            raise ManifestError(f"{self._path}: is not JSON: {error}") from error
