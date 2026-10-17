from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agent_core._audit import english
from agent_core._audit.rows import Row
from agent_core._audit.scope import RepositoryPath
from agent_core._audit.text import CODE_FENCES, JOINER, MASK, Block, MarkdownFile, Sentence, TechnicalNames, masked
from agent_core._audit.vocabulary import Glossary, Synonym

BANNED_FORCE = re.compile(r"\b(?:consider|try to|it is a good idea to|generally|usually|where appropriate|"
                          r"as needed)\b", re.IGNORECASE)
BARE_SHOULD = re.compile(r"\b[Ss]hould\b")
AGENT_ALONE = re.compile(r"(?<![\w-])agents?(?![\w-])")
ITALIC_OR_QUOTED = re.compile(r"(?<!\*)\*(?!\*)[^*\n]+?(?<!\*)\*(?!\*)|\"[^\"\n]*\"|“[^”\n]*”")
MARKUP_EDGES = "*_~([\"'"
CLAUSE_PUNCTUATION = ",.;:!?)"
COMMAND_LIMIT = 20
DEFINITION_LIMIT = 25
LONGEST_NOUN_CLUSTER = 3
LONGEST_PARAGRAPH = 6
PARAGRAPH = "paragraph"
RULE_FORCE = "banned-force-word"
RULE_SHOULD = "bare-should"
RULE_SYNONYM = "banned-synonym"
RULE_AGENT = "agent-alone"
RULE_LENGTH = "long-sentence"
RULE_INSTRUCTIONS = "one-instruction"
RULE_PASSIVE = "passive-voice"
RULE_CLUSTER = "noun-cluster"
RULE_PARAGRAPH = "long-paragraph"


class ProseCheck:
    name = "prose"

    def __init__(self, paths: list[Path], root: Path) -> None:
        self._paths = [path for path in paths if path.suffix == ".md"]
        self._root = root
        self._glossary = Glossary(root)

    def rows(self) -> list[dict]:
        names = self._glossary.technical_names()
        language = ProseLanguage(names, SynonymUses(self._glossary.synonyms(), names))
        return [row for path in self._paths for row in ProseFile(path, self._root, language).rows(
            self._glossary.table_lines() if path == self._glossary.path else set())]


@dataclass(frozen=True)
class ProseLanguage:
    names: TechnicalNames
    synonyms: SynonymUses


class ProseFile:
    def __init__(self, path: Path, root: Path, language: ProseLanguage) -> None:
        self._markdown = MarkdownFile(path)
        self._label = RepositoryPath(path, root).label()
        self._names = language.names
        self._synonyms = language.synonyms

    def rows(self, exempt_lines: set[int]) -> list[dict]:
        blocks = self._markdown.blocks()
        lines = [(number, line) for block in blocks for number, line in block.lines if number not in exempt_lines]
        return (self._word_rows(lines) + [row for block in blocks for row in self._block_rows(block)])

    def _word_rows(self, lines: list[tuple[int, str]]) -> list[dict]:
        rows = []
        for number, line in lines:
            text = ITALIC_OR_QUOTED.sub(lambda span: MASK * len(span.group(0)), masked(line))
            rows += [self._row(RULE_FORCE, number, match.group(0)) for match in BANNED_FORCE.finditer(text)]
            rows += [self._row(RULE_SHOULD, number, "write SHOULD with its reason, or a Command")
                     for _match in BARE_SHOULD.finditer(text)]
            rows += [self._row(RULE_AGENT, number, f"{match.group(0)}: write worker, or name the agent")
                     for match in AGENT_ALONE.finditer(text)]
            rows += [self._row(RULE_SYNONYM, number, detail) for detail in self._synonyms.used_in(text)]
        return rows

    def _block_rows(self, block: Block) -> list[dict]:
        sentences = block.sentences()
        rows = [row for sentence in sentences for row in self._sentence_rows(sentence)]
        if block.kind == PARAGRAPH and len(sentences) > LONGEST_PARAGRAPH:
            rows.append(self._row(RULE_PARAGRAPH, block.line, f"{len(sentences)} sentences"))
        return rows

    def _sentence_rows(self, sentence: Sentence) -> list[dict]:
        if sentence.text.lstrip().startswith(CODE_FENCES):
            return []
        shaped = ShapedSentence(sentence, self._names)
        rows = []
        if shaped.length() > shaped.limit():
            rows.append(self._row(RULE_LENGTH, sentence.line, f"{shaped.length()} words; a {shaped.form} "
                                                              f"holds at most {shaped.limit()}"))
        if shaped.most_instructions() > 1:
            rows.append(self._row(RULE_INSTRUCTIONS, sentence.line, "a main clause carries two instructions"))
        rows += [self._row(RULE_PASSIVE, sentence.line, passive) for passive in shaped.passives()]
        rows += [self._row(RULE_CLUSTER, sentence.line, cluster) for cluster in shaped.noun_clusters()]
        return rows

    def _row(self, rule: str, line: int, detail: str) -> dict:
        return Row(rule, self._label, line, detail).as_dict()


class SynonymUses:
    def __init__(self, synonyms: list[Synonym], names: TechnicalNames) -> None:
        self._synonyms = [(synonym, synonym.pattern()) for synonym in synonyms]
        self._names = names

    def used_in(self, text: str) -> list[str]:
        merged = self._names.merged(text)
        lowered = merged.lower()
        return [synonym.detail() for synonym, pattern in self._synonyms
                if synonym.word.lower() in lowered and synonym.sense_is_in(lowered)
                and any(not self._inside_a_name(merged, match) for match in pattern.finditer(merged))]

    @staticmethod
    def _inside_a_name(merged: str, match: re.Match) -> bool:
        return JOINER in merged[match.start("word") - 1:match.end() + 1]


class ShapedSentence:
    def __init__(self, sentence: Sentence, names: TechnicalNames) -> None:
        self._words = sentence.words(names)
        self._names = names
        self._bare = [word.strip(MARKUP_EDGES) for word in self._words]
        self.form = self._form()

    def length(self) -> int:
        return len(self._words)

    def limit(self) -> int:
        return DEFINITION_LIMIT if self.form == "definition" else COMMAND_LIMIT

    def most_instructions(self) -> int:
        text = " ".join(self._words)
        return max((self._instructions(clause.split()) for clause in english.CLAUSE_BREAK.split(text)), default=0)

    def passives(self) -> list[str]:
        if self.form == "definition":
            return []
        text = " ".join(self._bare)
        return [match.group(0) for match in english.PASSIVE.finditer(text) if english.is_participle(match.group(1))]

    def noun_clusters(self) -> list[str]:
        clusters, run = [], []
        for word in self._words:
            if self._is_a_noun(word.strip(MARKUP_EDGES)):
                run.append(word)
                if english.ends_a_run(word.rstrip(CLAUSE_PUNCTUATION)) or word[-1:] in CLAUSE_PUNCTUATION:
                    run = self._closed(run, clusters)
            else:
                run = self._closed(run, clusters)
        self._closed(run, clusters)
        return clusters

    def _form(self) -> str:
        words = [word for word in self._bare if word]
        if not words:
            return "definition"
        if words[0].lower() in english.PROHIBITION_OPENERS:
            return "prohibition"
        if words[0].lower() in english.CONDITION_OPENERS:
            return "conditional"
        if english.opens_with_an_imperative(words) or any(word in english.FORCE_WORDS for word in words):
            return "command"
        return "definition"

    def _instructions(self, clause: list[str]) -> int:
        bare = [word.strip(MARKUP_EDGES + CLAUSE_PUNCTUATION) for word in clause]
        bare = [word for word in bare if word]
        forces = sum(1 for word in bare if word in english.FORCE_WORDS)
        opens = bool(bare) and bare[0] not in english.FORCE_WORDS and english.opens_with_an_imperative(bare)
        return forces + int(opens)

    def _is_a_noun(self, word: str) -> bool:
        stripped = word.rstrip(CLAUSE_PUNCTUATION)
        return (bool(stripped) and set(stripped) == {MASK}) or JOINER in stripped or \
            english.is_plain_noun(stripped)

    @staticmethod
    def _closed(run: list[str], clusters: list[str]) -> list[str]:
        if len(run) > LONGEST_NOUN_CLUSTER:
            clusters.append(" ".join(run).replace(JOINER, " "))
        return []
