from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_core._audit.scope import CONTRACT_GROUP, ENCODING, INSTRUCTION_GROUPS, ControlPlaneFiles, RepositoryPath
from agent_core._audit.text import FileWords, MarkdownText

INSTRUCTION_SUFFIX = ".md"
VENDORED_CORE = "vendor/agent-core/"
ALWAYS_LOADED = "always_loaded"
REST = "rest"
INSTRUCTION_TEXT = "instruction_text"
GROUP_NAMES = (ALWAYS_LOADED, REST)


@dataclass(frozen=True)
class InstructionTexts:
    texts: dict[str, str]
    contract: frozenset[str]

    def counts(self) -> dict:
        files = {label: FileWords(text).count() for label, text in sorted(self.texts.items())}
        always = sum(words for label, words in files.items() if label in self.contract) + sum(
            FileWords(MarkdownText(text).description()).count() for label, text in self.texts.items()
            if label not in self.contract)
        total = sum(files.values())
        return {INSTRUCTION_TEXT: total, ALWAYS_LOADED: always, REST: total - always, "files": files}


class OwnedInstructions:
    def __init__(self, files: ControlPlaneFiles) -> None:
        self._files = files

    def texts(self) -> InstructionTexts:
        grouped = self._files.by_group()
        texts, contract, seen = {}, set(), set()
        for group in INSTRUCTION_GROUPS:
            for path in grouped.get(group, []):
                if self._weighed(path, seen):
                    label = RepositoryPath(path, self._files.root).label()
                    texts[label] = path.read_text(encoding=ENCODING)
                    contract |= {label} if group == CONTRACT_GROUP else set()
        return InstructionTexts(texts, frozenset(contract))

    def _weighed(self, path: Path, seen: set[Path]) -> bool:
        resolved = path.resolve()
        if path.suffix != INSTRUCTION_SUFFIX or resolved in seen or self._is_vendored(resolved):
            return False
        seen.add(resolved)
        return True

    def _is_vendored(self, resolved: Path) -> bool:
        root = self._files.root.resolve()
        return resolved.is_relative_to(root) and resolved.relative_to(root).as_posix().startswith(VENDORED_CORE)


class WeightRow:
    def __init__(self, counts: dict, recorded: dict | None) -> None:
        self._counts = counts
        self._recorded = recorded

    def as_dict(self) -> dict:
        growth = None if not self._recorded else {
            name: self._counts[name] - self._recorded.get(name, 0) for name in (ALWAYS_LOADED, REST, INSTRUCTION_TEXT)}
        return {"growth_since_accept": growth, **{key: value for key, value in self._counts.items()}}
