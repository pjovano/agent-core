from __future__ import annotations

import re
import unittest

from _repository import REPOSITORY_ROOT

CLEAN_PROSE = REPOSITORY_ROOT / "core" / "skills" / "clean-prose" / "SKILL.md"
EARLIER_HEADINGS = (
    "## 1. Every sentence has a form", "## 2. Force is a controlled vocabulary", "## 3. Branches are exhaustive",
    "## 4. Every action states its failure branch", "## 5. One concept, one term — the Vocabulary",
    "## 6. Modular structure, formatted to be scanned", "## 7. Economy", "## 8. What must survive",
    "## 9. Chat register", "## 10. Priority", "## 11. How to change instruction text",
    "## 12. A rule covers a defect class",
)
FIRST_STE_SECTION = 13
VOCABULARY_SECTION = 5
LIMIT_OF_RULE = {
    "Sentence length by form": ("a Command, a Prohibition, or a Conditional holds at most 20 words",
                                "a Definition or an Invariant holds at most 25"),
    "One instruction per sentence": ("each main clause carries at most one imperative or one force word",),
    "Active voice for actions": ("a Command or a Conditional carries no passive verb",),
    "Noun clusters": ("a noun cluster holds at most three nouns", "a technical name or a code span counts as one noun"),
    "Paragraph length": ("a paragraph holds at most six sentences",
                         "a sequence of actions stands as numbered steps, never as a paragraph"),
    "One topic per paragraph": ("a paragraph holds one rule and the detail of that rule",),
    "Condition before action": ("§1's Condition first",),
}
COUNTING_RULES = (
    "| code span | one word |", "| technical name | one word, however many words it holds |",
    "| table cell | one word, in any count wider than the cell |",
    "A table cell's words meet the limit of the form its row takes.",
    "A sentence that carries an imperative or a force word takes the 20-word limit.",
    "Every other sentence takes the 25-word limit.",
)
RATCHET_RULES = (
    "If a change writes or changes a sentence, that sentence and its paragraph MUST meet every STE rule.",
    "A sentence older than adoption keeps its findings until a change touches it.",
)
SCOPE_RULES = ("**The STE rules bind instruction text alone.**", "NEVER apply them to a chat reply",
               "NEVER apply them to domain content.")
STE_TERMS = ("STE rule", "adoption ratchet", "technical name", "force word", "main clause", "noun cluster")
SENTENCE_LIMIT = 25
INSTRUCTION_LIMIT = 20
PARAGRAPH_LIMIT = 6
FORCE_WORD = re.compile(r"\b(MUST|ALWAYS|NEVER|SHOULD|MAY|PREFER)\b")
CONDITION_OPENING = re.compile(r"^(If|Unless)\b")
CLAUSE_END = re.compile(r";|:|, (?:and|or|but)\b")
SECTION_HEADING = re.compile(r"^## (\d+)\. ", re.MULTILINE)
VOCABULARY_ROW = re.compile(r"^\| ([^|]+?) \|", re.MULTILINE)
CODE_SPAN = re.compile(r"`[^`]+`")
MARKUP = re.compile(r"\*+|\]\([^)]*\)|\[")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
WORD = re.compile(r"\S*[A-Za-z0-9]\S*")
WHITESPACE_RUN = re.compile(r"\s+")
TABLE_RULE = re.compile(r"^\|(\s*-+\s*\|)+$")
STANDS_APART = re.compile(r"^(#|\||- |\d+\. )")


class CleanProse:
    def __init__(self) -> None:
        self.raw = CLEAN_PROSE.read_text(encoding="utf-8")
        self.flat = WHITESPACE_RUN.sub(" ", self.raw)

    def headings(self) -> list[str]:
        return [line for line in self.raw.splitlines() if SECTION_HEADING.match(line)]

    def ste_sections(self) -> str:
        return self.raw[self._start_of(FIRST_STE_SECTION):]

    def vocabulary_section(self) -> str:
        return self.raw[self._start_of(VOCABULARY_SECTION):self._start_of(VOCABULARY_SECTION + 1)]

    def _start_of(self, number: int) -> int:
        return next(match.start() for match in SECTION_HEADING.finditer(self.raw) if int(match.group(1)) == number)

    def vocabulary_rows(self, terms: tuple[str, ...]) -> str:
        return "\n".join(line for line in self.raw.splitlines()
                         if any(line.startswith(f"| {term} |") for term in terms))

    def technical_names(self) -> list[str]:
        terms = VOCABULARY_ROW.findall(self.vocabulary_section())
        return sorted({term for term in terms if " " in term}, key=len, reverse=True)


class Sentence:
    def __init__(self, text: str, technical_names: list[str]) -> None:
        self.text = text
        self._technical_names = technical_names

    def words(self) -> int:
        counted = CODE_SPAN.sub("X", self.text)
        for name in self._technical_names:
            counted = re.sub(rf"\b{re.escape(name)}", "X", counted)
        return len(WORD.findall(counted))

    def limit(self) -> int:
        instructs = FORCE_WORD.search(self.text) or CONDITION_OPENING.match(self.text)
        return INSTRUCTION_LIMIT if instructs else SENTENCE_LIMIT

    def force_words_in_one_main_clause(self) -> int:
        return max(len(FORCE_WORD.findall(clause)) for clause in CLAUSE_END.split(CODE_SPAN.sub("X", self.text)))


class Passage:
    def __init__(self, text: str, technical_names: list[str]) -> None:
        self._text = text
        self._technical_names = technical_names

    def paragraphs(self) -> list[list[Sentence]]:
        return [self._sentences(block) for block in self._text.split("\n\n") if self._is_paragraph(block)]

    def table_cells(self) -> list[Sentence]:
        rows = [line for line in self._text.splitlines() if line.startswith("|") and not TABLE_RULE.match(line)]
        return [sentence for row in rows for cell in row.strip("|").split("|") for sentence in self._sentences(cell)]

    def sentences(self) -> list[Sentence]:
        return [sentence for paragraph in self.paragraphs() for sentence in paragraph] + self.table_cells()

    def _is_paragraph(self, block: str) -> bool:
        return bool(block.strip()) and not STANDS_APART.match(block.strip())

    def _sentences(self, block: str) -> list[Sentence]:
        flat = MARKUP.sub("", WHITESPACE_RUN.sub(" ", block)).strip()
        return [Sentence(text, self._technical_names) for text in SENTENCE_END.split(flat) if text]


class TheEarlierSectionsKeepTheirNumbers(unittest.TestCase):
    def test_sections_one_to_twelve_keep_their_numbers_and_titles(self) -> None:
        self.assertEqual(list(EARLIER_HEADINGS), CleanProse().headings()[:len(EARLIER_HEADINGS)])


class TheStePassageStatesEachRule(unittest.TestCase):
    def test_the_limits_table_carries_each_rule_with_its_threshold(self) -> None:
        rows = {line.split("|")[1].strip(): line for line in CleanProse().ste_sections().splitlines()
                if line.startswith("| ")}
        missing = {rule: [limit for limit in limits if limit not in rows.get(rule, "")]
                   for rule, limits in LIMIT_OF_RULE.items()}
        self.assertEqual({rule: [] for rule in LIMIT_OF_RULE}, missing)

    def test_the_counting_rule_is_stated(self) -> None:
        self.assertEqual([], [rule for rule in COUNTING_RULES if rule not in CleanProse().flat])

    def test_the_ratchet_binds_only_text_a_change_writes(self) -> None:
        self.assertEqual([], [rule for rule in RATCHET_RULES if rule not in CleanProse().flat])

    def test_chat_replies_and_domain_content_stay_out_of_scope(self) -> None:
        self.assertEqual([], [rule for rule in SCOPE_RULES if rule not in CleanProse().flat])

    def test_the_vocabulary_defines_each_term_the_ste_rules_fix(self) -> None:
        terms = set(VOCABULARY_ROW.findall(CleanProse().vocabulary_section()))
        self.assertEqual([], [term for term in STE_TERMS if term not in terms])


class TheStePassageMeetsItsOwnLimits(unittest.TestCase):
    def setUp(self) -> None:
        skill = CleanProse()
        text = skill.ste_sections() + "\n\n" + skill.vocabulary_rows(STE_TERMS)
        self.passage = Passage(text, skill.technical_names())

    def test_each_sentence_meets_the_limit_of_its_form(self) -> None:
        long = [(sentence.words(), sentence.text) for sentence in self.passage.sentences()
                if sentence.words() > sentence.limit()]
        self.assertEqual([], long)

    def test_each_paragraph_holds_at_most_six_sentences(self) -> None:
        long = [paragraph[0].text for paragraph in self.passage.paragraphs() if len(paragraph) > PARAGRAPH_LIMIT]
        self.assertEqual([], long)

    def test_each_main_clause_carries_at_most_one_force_word(self) -> None:
        crowded = [sentence.text for paragraph in self.passage.paragraphs() for sentence in paragraph
                   if sentence.force_words_in_one_main_clause() > 1]
        self.assertEqual([], crowded)


if __name__ == "__main__":
    unittest.main()
