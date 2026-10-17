from __future__ import annotations

import re

FORCE_WORDS = frozenset({"MUST", "ALWAYS", "NEVER", "SHOULD", "MAY", "PREFER"})
CONDITION_OPENERS = frozenset({"if", "unless", "when", "whenever", "once", "where", "while", "until"})
PROHIBITION_OPENERS = frozenset({"never"})
OBJECT_OPENERS = frozenset({
    "the", "a", "an", "each", "every", "its", "their", "it", "them", "one", "all", "any", "no", "that", "this",
    "these", "those", "your", "what", "how", "only", "both", "nothing", "none", "so", "at", "from", "to", "with",
    "in", "on", "by", "for", "over", "into", "onto", "out", "up", "down", "back", "once", "again", "first",
})
NON_VERBS = frozenset({
    "the", "a", "an", "each", "every", "its", "their", "it", "this", "that", "these", "those", "one", "all", "any",
    "no", "none", "both", "either", "neither", "some", "many", "most", "few", "such", "another", "other", "here",
    "there", "then", "also", "only", "even", "so", "thus", "hence", "otherwise", "nothing", "everything", "who",
    "which", "what", "how", "why", "where", "when", "in", "on", "at", "by", "for", "from", "with", "without",
    "after", "before", "during", "under", "over", "between", "through", "per", "to", "of", "as", "and", "or",
    "but", "nor", "yet", "you", "we", "they", "he", "she", "i", "my", "our", "his", "her", "stage", "step",
    "part", "row", "column", "table", "section", "file", "files", "work", "works", "page", "pages", "two",
    "three", "four", "five", "six", "seven", "eight", "nine", "ten", "today", "now",
})
STOP_WORDS = frozenset({
    "the", "a", "an", "each", "every", "its", "their", "it", "this", "that", "these", "those", "one", "all", "any",
    "no", "and", "or", "but", "nor", "of", "to", "in", "on", "at", "by", "for", "from", "with", "without", "as",
    "into", "onto", "over", "under", "after", "before", "per", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "can", "cannot", "will", "would", "may", "must", "never",
    "always", "not", "if", "unless", "when", "where", "which", "who", "whose", "what", "how", "than", "then",
    "so", "only", "also", "own", "same", "other", "another", "such", "more", "most", "less", "least", "you",
    "your", "they", "them", "we", "our", "he", "she", "his", "her", "there", "here", "both", "either",
    "neither", "between", "through", "out", "up", "down", "off", "again", "once", "about", "against", "within",
    "via", "because", "while", "until", "since", "though", "although", "whether", "else", "otherwise",
    "first", "last", "next", "new", "old", "same", "whole", "full", "empty", "true", "false", "none", "nothing",
})
IRREGULAR_PARTICIPLES = frozenset({
    "written", "made", "built", "kept", "held", "run", "read", "set", "given", "taken", "done", "found", "known",
    "shown", "sent", "left", "put", "cut", "met", "paid", "said", "seen", "told", "thought", "brought", "bought",
    "caught", "taught", "chosen", "driven", "frozen", "hidden", "spoken", "broken", "begun", "drawn", "grown",
    "thrown", "torn", "lost", "split", "spent", "struck", "stuck", "won", "bound", "laid", "led", "lit", "meant",
    "fed", "felt", "dealt", "hung", "heard", "sold", "sought", "shot", "swept", "wound", "understood",
    "withdrawn", "overwritten", "rewritten", "rebuilt", "unread", "forbidden", "undone", "redone", "rerun",
})
PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being|get|gets|got|gotten|getting)\s+(?:\w+ly\s+)?(\w+)\b")
CLAUSE_BREAK = re.compile(r";|:|,\s+(?:and|or|but)\s+")
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
ADVERB_SUFFIX = "ly"
GERUND_SUFFIX = "ing"
PARTICIPLE_SUFFIX = "ed"
PLURAL_SUFFIX = "s"
DOUBLE_S = "ss"
SHORTEST_NOUN = 3
IMPERATIVE_WORDS = 2


def is_participle(word: str) -> bool:
    lowered = word.lower()
    return lowered.endswith(PARTICIPLE_SUFFIX) or lowered in IRREGULAR_PARTICIPLES


def opens_with_an_imperative(words: list[str]) -> bool:
    if len(words) < IMPERATIVE_WORDS or not words[0][:1].isupper() or not words[0].isalpha():
        return False
    first, second = words[0].lower(), words[1]
    if first in NON_VERBS or first in CONDITION_OPENERS:
        return False
    return second.lower() in OBJECT_OPENERS or not second.isalpha()


def is_plain_noun(word: str) -> bool:
    lowered = word.lower()
    return (word.isalpha() and word.islower() and len(word) >= SHORTEST_NOUN and lowered not in STOP_WORDS
            and not lowered.endswith((ADVERB_SUFFIX, GERUND_SUFFIX, PARTICIPLE_SUFFIX)))


def ends_a_run(word: str) -> bool:
    return word.endswith(PLURAL_SUFFIX) and not word.endswith(DOUBLE_S)
