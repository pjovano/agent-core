from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.contract import WORKER_NAMED, ContractLocations, spans_in
from agent_core._audit.rows import Row
from agent_core._audit.scope import ENCODING, ControlPlaneFiles, RepositoryPath
from agent_core._audit.scripts import ScriptVocabularies
from agent_core._audit.text import CODE_SPAN, MarkdownFile

SETTINGS_PATH = Path(".claude") / "settings.json"
AGENTS_DIRECTORY = Path(".claude") / "agents"
SKILLS_DIRECTORY = Path(".claude") / "skills"
WORKFLOW_PATTERN = ".claude/workflows/*.js"
SKILL_FILE = "SKILL.md"
SCRIPT_CALL = re.compile(r"(?:^|[\s/])([\w-]+\.py)\s+([a-z][a-z0-9-]*)")
SCRIPT_NAMED = re.compile(r"([\w-]+\.py)\b")
SUBCOMMAND_HEADERS = ("Subcommand", "Command")
MODEL_FAMILIES = ("opus", "sonnet", "haiku")
INHERITED_MODEL = "inherit"
SESSION_MODEL = "session"
MODEL_FIELD = "model"
RUN_BY_COLUMN = "Run by"
MODEL_COLUMN = "Model"
SKILL_COLUMN = "Skill"
ENTRY_WRAPPER = re.compile(r"^Bash\((.*)\)$")
TRAILING_WILDCARD = ":*"
WILDCARD = "*"
SUBCOMMAND = re.compile(r"^[a-z][a-z0-9-]*$")


class XrefCheck:
    name = "xref"

    def __init__(self, plane: XrefPlane, settings: XrefSettings) -> None:
        self._instructions = [path for path in plane.instructions if path.suffix == ".md"]
        self._root = plane.files.root
        self._scope = plane.files.scope
        self._settings = settings
        self._scripts = ScriptVocabularies(plane.code, self._root, settings.known)

    def rows(self) -> list[dict]:
        return (self._prose_subcommands() + self._unnamed_subcommands() + self._missing_workers()
                + self._models() + self._allow_list() + self._hooks() + self._skills())

    def _prose_subcommands(self) -> list[dict]:
        rows = []
        for path in self._instructions:
            markdown = MarkdownFile(path)
            for line, script, name in ProseSubcommands(markdown).named():
                vocabulary = self._scripts.of_basename(script)
                if vocabulary is not None and vocabulary.closed and name not in vocabulary.names:
                    rows.append(Row("subcommand-not-in-parser", self._label(path), line,
                                    f"{script} {name}: the parser defines no {name}").as_dict())
        return rows

    def _unnamed_subcommands(self) -> list[dict]:
        mentioned = self._mentioned()
        return [Row("subcommand-not-in-prose", subcommand.file, subcommand.line,
                    f"{subcommand.name}: no instruction file names it").as_dict()
                for subcommand in self._scripts.defined() if subcommand.name not in mentioned]

    def _mentioned(self) -> set[str]:
        words = set()
        for path in self._instructions:
            for line in MarkdownFile(path).lines:
                words |= {word for span in CODE_SPAN.finditer(line) for word in span.group(0).strip("`").split()}
                words |= {match.group(2) for match in SCRIPT_CALL.finditer(line)}
        for workflow in self._root.glob(WORKFLOW_PATTERN):
            words |= set(re.findall(r"[a-z][a-z0-9-]*", workflow.read_text(encoding=ENCODING)))
        return words

    def _missing_workers(self) -> list[dict]:
        rows = []
        for path in self._instructions:
            for number, line in enumerate(MarkdownFile(path).lines, start=1):
                rows += [Row("worker-missing", self._label(path), number, f"{name}: no worker instructions name it")
                         .as_dict()
                         for name in self._workers_in(line) if not self._worker(name).is_file()]
        return rows

    @staticmethod
    def _workers_in(line: str) -> list[str]:
        return [match.group(1) or match.group(2) for match in WORKER_NAMED.finditer(line)]

    def _worker(self, name: str) -> Path:
        return self._root / AGENTS_DIRECTORY / f"{name}.md"

    def _models(self) -> list[dict]:
        rows = []
        for table in self._settings.locations.tables(self._root):
            if table.column(RUN_BY_COLUMN) is None or table.column(MODEL_COLUMN) is None:
                continue
            for row in table.rows:
                rows += self._model_rows(row.cells[table.column(RUN_BY_COLUMN)],
                                         row.cells[table.column(MODEL_COLUMN)])
        return rows

    def _model_rows(self, run_by: str, model: str) -> list[dict]:
        allowed = ModelColumn(model).families()
        if not allowed:
            return []
        rows = []
        for name in self._workers_in(run_by):
            worker = MarkdownFile(self._worker(name))
            line, value = worker.frontmatter.get(MODEL_FIELD, (0, ""))
            if line and ModelColumn(value).family() not in allowed:
                rows.append(Row("model-contradicts-table", self._label(self._worker(name)), line,
                                f"model: {value}; the contract's Model column names {model}").as_dict())
        return rows

    def _allow_list(self) -> list[dict]:
        entries = SettingsEntries(self._root / SETTINGS_PATH).entries()
        rows = []
        for entry in entries:
            vocabulary = self._scripts.of_basename(entry.script)
            if entry.subcommand and vocabulary and vocabulary.closed and entry.subcommand not in vocabulary.names:
                rows.append(Row("entry-without-subcommand", SETTINGS_PATH.as_posix(), entry.line,
                                f"{entry.script} {entry.subcommand}: the parser defines no "
                                f"{entry.subcommand}").as_dict())
        return rows + self._unlisted(entries)

    def _unlisted(self, entries: list[SettingsEntry]) -> list[dict]:
        rows = []
        for script in {entry.script for entry in entries if entry.subcommand}:
            listed = [entry for entry in entries if entry.script == script]
            if any(entry.subcommand is None for entry in listed):
                continue
            named = {entry.subcommand for entry in listed}
            rows += [Row("subcommand-without-entry", subcommand.file, subcommand.line,
                         f"{script} {subcommand.name}: no allow-list entry names it").as_dict()
                     for subcommand in self._scripts.defined_by(script) if subcommand.name not in named]
        return rows

    def _hooks(self) -> list[dict]:
        hook_list = self._settings.locations.hook_list
        if hook_list is None:
            return []
        in_contract = hook_list.named(self._root, self._scope)
        in_module = hook_list.hooks.named(self._root)
        rows = [Row("hook-not-in-module", hook_list.file, line, f"{name}: {hook_list.hooks.file} defines no "
                    f"such hook").as_dict() for name, line in in_contract.items() if name not in in_module]
        return rows + [Row("hook-not-in-contract", hook_list.hooks.file, line, f"{name}: the contract's hook "
                           f"list does not name it").as_dict() for name, line in in_module.items()
                       if name not in in_contract]

    def _skills(self) -> list[dict]:
        file = self._settings.locations.table_file()
        return [Row("skill-missing", file, line, f"{name}: no skill of that name").as_dict()
                for table in self._settings.locations.tables(self._root)
                for line, cell in table.cells_of(SKILL_COLUMN) for name in spans_in(cell)
                if not (self._root / SKILLS_DIRECTORY / name / SKILL_FILE).is_file()]

    def _label(self, path: Path) -> str:
        return RepositoryPath(path, self._root).label()


@dataclass(frozen=True)
class XrefPlane:
    instructions: list[Path]
    code: list[Path]
    files: ControlPlaneFiles


@dataclass(frozen=True)
class XrefSettings:
    locations: ContractLocations
    known: dict[str, frozenset[str]]


class ProseSubcommands:
    def __init__(self, markdown: MarkdownFile) -> None:
        self._markdown = markdown

    def named(self) -> list[tuple[int, str, str]]:
        return self._called() + self._tabled()

    def _called(self) -> list[tuple[int, str, str]]:
        return [(number, match.group(1), match.group(2)) for number, line in enumerate(self._markdown.lines, 1)
                for span in CODE_SPAN.finditer(line) for match in SCRIPT_CALL.finditer(span.group(0).strip("`"))]

    def _tabled(self) -> list[tuple[int, str, str]]:
        scripts = sorted({match.group(1) for line in self._markdown.lines for span in CODE_SPAN.finditer(line)
                          for match in SCRIPT_NAMED.finditer(span.group(0))})
        if len(scripts) != 1:
            return []
        return [(line, scripts[0], name) for table in self._markdown.tables() if table.header[:1] and
                table.header[0] in SUBCOMMAND_HEADERS for line, cell in table.cells_of(table.header[0])
                for name in self._first_words(cell)]

    @staticmethod
    def _first_words(cell: str) -> list[str]:
        spans = spans_in(cell)
        first = spans[0].split()[0] if spans and spans[0].split() else ""
        return [first] if SUBCOMMAND.match(first) else []


class ModelColumn:
    def __init__(self, text: str) -> None:
        self._text = text.lower()

    def families(self) -> set[str]:
        named = {family for family in MODEL_FAMILIES if family in self._text}
        return named | ({INHERITED_MODEL} if SESSION_MODEL in self._text else set())

    def family(self) -> str:
        return next((family for family in MODEL_FAMILIES if family in self._text), self._text)


@dataclass(frozen=True)
class SettingsEntry:
    script: str
    subcommand: str | None
    line: int


class SettingsEntries:
    def __init__(self, path: Path) -> None:
        self._path = path

    def entries(self) -> list[SettingsEntry]:
        try:
            text = self._path.read_text(encoding=ENCODING)
            settings = json.loads(text)
        except (OSError, ValueError):
            return []
        commands = settings.get("permissions", {}).get("allow", []) + \
            settings.get("sandbox", {}).get("excludedCommands", [])
        lines = text.splitlines()
        return [entry for command in commands for entry in self._parsed(command, lines)]

    def _parsed(self, command: str, lines: list[str]) -> list[SettingsEntry]:
        wrapped = ENTRY_WRAPPER.match(command)
        tokens = (wrapped.group(1) if wrapped else command).removesuffix(TRAILING_WILDCARD).split()
        scripts = [index for index, token in enumerate(tokens) if token.endswith(".py")]
        if not scripts:
            return []
        script = Path(tokens[scripts[0]]).name
        following = tokens[scripts[0] + 1].rstrip(WILDCARD).removesuffix(":") if len(tokens) > scripts[0] + 1 \
            else ""
        spelled = json.dumps(command, ensure_ascii=False)
        line = next((number for number, text in enumerate(lines, 1) if spelled in text), 1)
        return [SettingsEntry(script, following if SUBCOMMAND.match(following) else None, line)]
