from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agent_core._domain.answers import VAULT_KEY, DomainAnswers, FolderAnswers
from agent_core._domain.git import Git
from agent_core._domain.fields import JsonFields, ManifestError
from agent_core._domain.manifest import MANIFEST_NAME, DomainManifest, JsonFile
from agent_core._domain.subtree import CommitMessages, CoreSource, SquashedSubtree
from agent_core._domain.template import DomainTemplate
from agent_core._domain.vendored import VENDOR_PREFIX, DomainSettings, ManifestFile, SettingsFile

MAIN_BRANCH = "main"
DOMAIN_BRANCH = "new-domain"
LINKED_KINDS = {"skills": "", "agents": ".md", "workflows": ".js"}
TRAILER = "Change-class: feature — {what}"
ROOT_MESSAGE = ("The domain's main starts from an empty root commit\n\n"
                + TRAILER.format(what="the root commit that the domain's first pull request merges into"))
START_MESSAGE = ("The domain starts from the agent-core domain template\n\n"
                 + TRAILER.format(what="the domain template's files"))
VENDOR_MESSAGES = CommitMessages(
    merge="The domain vendors the core of agent-core at vendor/agent-core\n\n" + TRAILER.format(what="the vendored core"),
    squash_trailer=TRAILER.format(what="the core's files, squashed for the vendored core"))
LINK_MESSAGE = ("The domain links every core unit and carries its manifest and settings blocks\n\n"
                + TRAILER.format(what="the core links, domain.json, and the settings blocks of .claude/settings.json"))


class TargetRefused(Exception):
    pass


class NewDomain:
    def __init__(self, root: Path, answers: DomainAnswers) -> None:
        self._root = root
        self._answers = answers
        self._git = Git(root)

    def create(self, core: CoreSource) -> None:
        ManifestCheck(self._answers).refuse_if_invalid()
        Target(self._root, DomainTemplate()).prepare()
        self._git.run("switch", "--quiet", "--create", DOMAIN_BRANCH, MAIN_BRANCH)
        DomainTemplate().written_into(self._root, self._template_values())
        self._commit(START_MESSAGE)
        SquashedSubtree(self._git, VENDOR_PREFIX).add(core, VENDOR_MESSAGES)
        CoreLinks(self._root).create()
        self._write_manifest_and_settings()
        self._commit(LINK_MESSAGE)

    def _template_values(self) -> dict[str, str]:
        return {"name": self._answers.name, "summary": self._answers.summary, "mandate": self._answers.mandate}

    def _write_manifest_and_settings(self) -> None:
        manifest = self._answers.manifest()
        blocks = DomainSettings(self._root).blocks(manifest)
        ManifestFile(self._root).write(manifest)
        SettingsFile(self._root).write_blocks(blocks)

    def _commit(self, message: str) -> None:
        self._git.run("add", "--all")
        self._git.run("commit", "--quiet", "--message", message)


class ManifestCheck:
    def __init__(self, answers: DomainAnswers) -> None:
        self._answers = answers

    def refuse_if_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / MANIFEST_NAME
            candidate.write_text(json.dumps(self._answers.manifest()), encoding="utf-8")
            try:
                DomainManifest.read(candidate)
            except ManifestError as error:
                problem = str(error).removeprefix(f"{candidate}: ")
                raise ManifestError(f"{self._answers.source}: the answers make a manifest domain.py refuses: "
                                    f"{problem}") from error


class Target:
    def __init__(self, root: Path, template: DomainTemplate) -> None:
        self._root = root
        self._template = template
        self._git = Git(root)

    def prepare(self) -> None:
        if self._is_repository():
            self._refuse_uncommitted_changes()
        else:
            self._create_repository()
        self._give_main_its_root()
        self._refuse_taken_paths()

    def _is_repository(self) -> bool:
        return (self._root / ".git").exists()

    def _refuse_uncommitted_changes(self) -> None:
        if self._git.run("status", "--porcelain"):
            raise TargetRefused(f"{self._root} has uncommitted changes; commit or remove them first")

    def _create_repository(self) -> None:
        if self._root.exists() and any(self._root.iterdir()):
            raise TargetRefused(f"{self._root} holds files and is no git repository; name an empty directory")
        self._root.mkdir(parents=True, exist_ok=True)
        self._git.run("init", "--quiet", "--initial-branch", MAIN_BRANCH)

    def _give_main_its_root(self) -> None:
        if self._git.succeeds("rev-parse", "--verify", "--quiet", f"refs/heads/{MAIN_BRANCH}"):
            return
        if self._git.succeeds("rev-parse", "--verify", "--quiet", "HEAD"):
            raise TargetRefused(f"{self._root} has commits but no branch {MAIN_BRANCH}; name a repository whose "
                                f"pull requests merge into {MAIN_BRANCH}")
        self._git.run("symbolic-ref", "HEAD", f"refs/heads/{MAIN_BRANCH}")
        self._git.run("commit", "--quiet", "--allow-empty", "--message", ROOT_MESSAGE)

    def _refuse_taken_paths(self) -> None:
        tracked = set(self._git.run("ls-tree", "-r", "--name-only", MAIN_BRANCH).splitlines())
        taken = [template_file.relative_target.as_posix() for template_file in self._template.files()
                 if template_file.relative_target.as_posix() in tracked]
        if taken:
            raise TargetRefused(f"{self._root} already holds {taken} on {MAIN_BRANCH}, which the template would "
                                "overwrite")


class CoreLinks:
    def __init__(self, root: Path) -> None:
        self._root = root

    def create(self) -> None:
        for kind, suffix in LINKED_KINDS.items():
            for unit in self._units(kind, suffix):
                link = self._root / ".claude" / kind / unit.name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(Path("..", "..", VENDOR_PREFIX, kind, unit.name))

    def _units(self, kind: str, suffix: str) -> list[Path]:
        directory = self._root / VENDOR_PREFIX / kind
        return [unit for unit in sorted(directory.iterdir()) if self._is_unit(unit, suffix)]

    @staticmethod
    def _is_unit(unit: Path, suffix: str) -> bool:
        return (unit.is_file() and unit.suffix == suffix) if suffix else unit.is_dir()


class ExistingDomain:
    def __init__(self, root: Path) -> None:
        self._root = root
        path = root / MANIFEST_NAME
        self._manifest = JsonFile(path).values()
        self.name = JsonFields(self._manifest, str(path)).text("name")

    def add_folders(self, folders: FolderAnswers) -> None:
        extended = self._with_folders(folders)
        DomainSettings(self._root).refuse_if_invalid(extended)
        ManifestFile(self._root).write(extended)

    def _with_folders(self, folders: FolderAnswers) -> dict:
        if folders.vault is not None and VAULT_KEY in self._manifest:
            raise TargetRefused(f"{self._root / MANIFEST_NAME} already names its vault, "
                                f"{self._manifest[VAULT_KEY]!r}; decline the vault to add other folders")
        added = folders.manifest_fields()
        return {**self._manifest, **added, "folders": self._manifest.get("folders", []) + added["folders"]}
