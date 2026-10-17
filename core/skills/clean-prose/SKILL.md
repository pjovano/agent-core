---
name: clean-prose
description: Enforces the prose standard on instruction text, which is AGENTS.md, SOUL.md, SKILL.md files, worker instructions, and any reference file a skill loads. Use this skill before adding or editing any instruction prose, including a one-sentence change; it also governs how the orchestrator explains its own work in chat. Not for domain content.
---

# Clean Prose

This skill is the standard for instruction text, the counterpart to
`clean-code` with the same force. Instruction prose is executed, by the
orchestrator and by workers that read nothing else, so it is written to be
*parsed*. A reader MUST be able to tell, from the sentence alone, whether it
binds them and what it makes them do.

**The domain's glossary.** If `.claude/glossary.md` exists, read it whole
after this file. If a rule of the glossary contradicts a rule of this file,
the glossary's rule wins.

## Scope

Applies to the repository's contract, the soul file, every `SKILL.md`, every
set of worker instructions, and every reference file a skill loads. §9 applies it to the
orchestrator's explanation of its own work in chat.

Does not apply to domain content. One exception binds: §6's paragraph rule
applies to domain content too.

## 1. Every sentence has a form

Each sentence of instruction MUST take one of five forms. A sentence that takes
none of them is either rationale, recast per §8, or decoration, cut.

| Form | Shape |
| --- | --- |
| Command | Do X. |
| Prohibition | Never X. |
| Conditional | If C, do X. / Unless C, do X. |
| Definition | X is Y. |
| Invariant | X is always true. |

Rules on form:

- **One rule per sentence.** A sentence carrying two obligations hides the
  second: split it.
- **Condition first.** Write `If C, do X`, never `Do X, in cases where C`. The
  reader must know whether the sentence applies before learning what it asks.
- **Bind every antecedent.** Replace *this*, *it*, and *that* with the noun
  wherever the referent is not the immediately preceding subject. A worker
  cannot ask what was meant.

## 2. Force is a controlled vocabulary

State obligation with these words. Each has one meaning.

- **MUST** / **ALWAYS** — required. No judgment, no exception.
- **NEVER** — prohibited. No exception.
- **SHOULD** — recommended. Deviating is permitted and requires a stated reason.
- **MAY** — permitted. The reader chooses freely.
- **PREFER X OVER Y** — X is the default, Y is available, and the sentence that
  follows says when Y wins.

A bare imperative (Command form) carries MUST. A bare `Never X` (Prohibition
form) carries NEVER. Write the capitalized word when the sentence would
otherwise read as advice.

Banned, because they state no force: *consider*, *try to*, *it is a good idea
to*, *generally*, *usually*, *where appropriate*, *as needed*. Each leaves the
reader to invent the rule. If the force is conditional, write a Conditional
sentence.

## 3. Branches are exhaustive

When a rule branches, cover every case or name the default. An uncovered case
is an instruction to guess, and different readers guess differently.

If any branch can reach a destructive or unrecoverable action, the default MUST
be `Otherwise, stop and ask the user`.

## 4. Every action states its failure branch

An instruction that can fail MUST say what happens when it does. Choose one and
write it: stop and ask, fall back to a named alternative, or report and
continue. A worker that hits an unhandled failure improvises, and improvisation
at a stage whose writes cannot be undone is unrecoverable.

## 5. One concept, one term — the Vocabulary

Fix a term and reuse it exactly, in every file. NEVER vary the wording for
elegance: in instruction text, a synonym reads as a distinction. Define a
load-bearing term once, with a Definition sentence, and reference that
definition rather than restating it.

**Canonical vocabulary.** Use the left column; a banned synonym NEVER appears
in its place.

| Term | Means | Banned synonyms |
| --- | --- | --- |
| orchestrator | the session that dispatches workers and talks to the user | main session, this session |
| worker | a subagent that runs from its own worker instructions | sub-agent, agent (alone) |
| worker instructions | the file defining one worker | agent definition, agent file, agent prompt |
| dispatch | sending one prompt to one worker | task, spawn |
| core | `core/` of the `agent-core` repository: the skills, workers, workflows, and code `agent-core` shares with every repository that vendors it | shared layer, framework, common library |
| vendored core | `vendor/agent-core/`, the core as `git subtree` copies it from `agent-core`'s branch `core` | vendor copy, submodule, core checkout |
| core unit | one skill, worker, or workflow of the core; a core skill, a core worker, and a core workflow are core units of those kinds | shared skill, imported skill, external skill |
| symlink | a relative symbolic link under `.claude/` that resolves to a core unit inside the vendored core, or inside `core/` in `agent-core` itself | link (for a symlink), alias, shortcut |
| domain | a repository that vendors the core at `vendor/agent-core/` and reaches each core unit it uses through a symlink | client repository, consumer, downstream repository |
| code overlay | `.claude/code-overlay.md` in a domain: the domain's rules on code, which `clean-code` reads after its own text | overlay (for the code overlay), code rules file, clean-code addendum |
| glossary | `.claude/glossary.md` in a domain: the domain's Vocabulary rows and its rules on instruction text, which `clean-prose` reads after its own text | overlay (for the glossary), prose overlay, vocabulary file |
| domain content | what a domain writes for the user to read, and the user's own writing, as the domain's glossary names them | user content, output (for domain content) |
| soul file | `SOUL.md` of the core, which the repository's `CLAUDE.md` imports: the standard of conduct every session that loads it keeps | persona, personality file, character file, system prompt (for the soul file) |
| user file | `USER.md` at a domain's root, never versioned: what is true of the user now in that domain, which `remember` keeps | memory file, profile, user profile, preferences file |
| Standing section | the `## Standing` section of the user file: what stays true of the user for months | permanent section, long-term memory, profile section |
| Recent section | the `## Recent` section of the user file, which holds the recent entries | log, journal, short-term memory |
| recent entry | one line of the Recent section, opening with its date as `YYYY-MM-DD` | note (for a recent entry), log line, memory (for a recent entry) |
| sorting test | the test `remember` applies to each learned item: an item that would still hold for another person using the domain is a rule, and a rule NEVER enters the user file | boundary check, memory filter, triage |
| STE rule | one row of §14's table: a property of instruction text and the limit §14 sets on it, counted as §15 states | style rule, plain-language rule, writing guideline |
| adoption ratchet | §13's rule that the STE rules bind the text a change writes, and that older text keeps its findings until a change touches it | grandfathering, legacy exemption, grace rule |
| technical name | a term of the Vocabulary or of the domain's glossary, which the STE rules count as one word | glossary term, defined term, jargon |
| force word | one of §2's words: MUST, ALWAYS, NEVER, SHOULD, MAY, PREFER | modal (for a force word), keyword (for a force word), strength word |
| main clause | a clause that could stand as a sentence on its own; §15 states where one ends | independent clause, sentence (for a main clause) |
| noun cluster | a run of nouns with no other word between them | noun stack, noun string, compound (for a noun cluster) |

Three exceptions bind: `subagent_type` is the Agent tool's literal parameter
name and stays as written; a code or configuration identifier stays as
written; quoting a banned term to state its ban is not a use.

**Extend the Vocabulary whenever a repository fixes a new term.** A build step
that names a new artifact, role, or layer MUST add it in the same session, with
its banned synonyms: a term of the core to this table, a term of one domain to
the domain's glossary. A term used in two files and defined in neither
becomes a distinction.

## 6. Modular structure, formatted to be scanned

Apply `clean-code`'s decomposition to prose: **define each operation once, as a
small named unit, and compose procedures by reference.** A rule stated inside
three procedures is three copies to drift.

Order a procedure the way it runs: preconditions, then steps in sequence, then
what the stage guarantees on completion.

**Format for the eye, not the ear.** Render the text so the binding sentence is
findable without reading the paragraph:

- Enumerable rules go in a **table**; sequences go in **numbered steps**.
- A paragraph opens with a **bold rule-head** stating the rule; what follows is
  its detail.
- Reserve flowing paragraphs for recast rationale (§8).
- One section covers one decision. A section that covers three is three
  sections.

**Break a paragraph at its joints.** One paragraph carries one unit of the
argument; where the text turns to the next unit, break. If a paragraph passes
140 words, look for a joint. Unless §14's paragraph limit binds the paragraph,
length alone NEVER forces a break. NEVER merge two units to balance length.

**An enumeration breaks between its items and NEVER inside one.** If its items
run about a line each, the list stays one paragraph at any length. Per Scope,
§6's paragraph rules bind domain content as well.

## 7. Economy

**Delete the sentence. If nothing about the reader's behaviour changes, it was
decoration.** Apply this to every sentence you write and every sentence you
edit past.

**Instruction text is a rulebook.** Banned outright:

- **Narrative** — scenarios, anecdotes, incidents.
- **Examples.** A rule that needs an example is under-specified: tighten the
  rule. Exception: data that parameterizes a rule — an enumeration of types,
  producers, fields, sentence shapes, name-shapes — is specification, not
  example.
- **Self-explanation** — a sentence justifying the sentence before it.
- **Throat-clearing** — announcing what the next section will do.
- **Qualification longer than the rule it qualifies.** Name the rare case; do
  not stage it.

## 8. What must survive

Two forms read like waste and are load-bearing. Cutting them is the
characteristic failure of a tightening pass, and it is silent.

**Guarding rationale.** A rule is *guard-dependent* if a reader who did not
know its reason would plausibly revert it. If a rule is guard-dependent, keep
its reason as one clause attached to the rule, in the shape `NEVER X: <reason>`.
Otherwise, write the bare rule and cut the reason. In both cases the story
behind the reason — the history, the incident, the alternatives weighed — is
cut.

**Repetition across a delegation boundary.** A worker inherits no
contract, so a rule restated in a worker's instructions is doing necessary
work. Duplication is a defect only within a single context. A worker that reads
two files in one run, its worker instructions and a reference file, is one
context.

## 9. Chat register

This section governs **procedural explanation**: what the orchestrator is doing
and why. It does NOT govern the substance of an answer. If the host's
own chat guidance fixes a format, keep the order below inside that format.

**The orchestrator's explanation of its own work MUST carry the structure of
the instruction it is following.** A reader MUST be able to tell which rule
produced an action without opening the rule.

**State the trigger, then the rule, then the action, in that order.** NEVER
state an action first and its reason afterwards.

**Mirror the form of the instruction being followed:**

| Instruction form | Explanation shape |
| --- | --- |
| Command | "The standard requires X. Doing X." |
| Prohibition | "X is prohibited by \<rule\>. Doing Y instead." |
| Conditional | "C holds, so X follows." / "C does not hold, so X does not apply." |
| Definition | "This is a Y, because \<criterion\>." |
| Invariant | "X holds always, so Y." |

**Name the branch not taken.** When a rule branches, say which branch did not
apply and why. A reader cannot audit a choice whose alternatives are invisible.

**The soul file binds every reply as well.** `SOUL.md` of the core states the
rules of honesty, reporting, and voice that hold for any assistant; this
section adds only the rules that tie an explanation to the instruction it
follows.

## 10. Priority

Weight a finding by how often the text is loaded. `AGENTS.md`, every skill
`description`, and every agent `description` are paid on every session; a skill
body costs nothing until invoked. Fix the always-loaded text first.

Within a file, rank by consequence: an unstated failure branch or an uncovered
case outranks a wordy sentence, because the first two change what the reader
does and the third only costs tokens.

## 11. How to change instruction text

State a cut as replacement text, never as a verdict. "These 40 words say what
these 12 do" is actionable; "this section is verbose" is not.

Edit one file per change and read the result whole.

## 12. A rule covers a defect class

A defect class is the property of an input that produces a failure, stated
without naming one input. A special case is a rule, a branch, a constant, or a
table entry that only one input, or only the inputs of one run, can meet. If
the repository's contract defines the two terms, its definitions govern. In
instruction text:

- NEVER name one input in a rule, and NEVER describe one so closely that only
  that input fits.
- If a worker or the orchestrator misjudged one input, find the sentence that
  permitted the misjudgment: an uncovered case, an undefined force, or an
  undefined term. Restate that sentence. NEVER append a sentence for the input.
- PREFER restating the rule that governs the decision OVER adding a rule
  beside it. The added rule wins only when no existing rule governs the
  decision.
- If a rule carries more than two exceptions, restate the rule so that it
  covers them: a list of exceptions grows by one per run.

## 13. The STE rules: scope and ratchet

**The STE rules restate ASD-STE100, Simplified Technical English, in house
form.** NEVER copy the specification's own text into this file.

**The STE rules bind instruction text alone.** NEVER apply them to a chat
reply: the soul file and §9 govern chat. NEVER apply them to domain content.

**The adoption ratchet binds the text a change writes.** Adoption is the
merge that adds this section to the core. If a change writes or changes a
sentence, that sentence and its paragraph MUST meet every STE rule. A
sentence older than adoption keeps its findings until a change touches it.

## 14. The STE rules and their limits

| STE rule | Limit |
| --- | --- |
| Sentence length by form | a Command, a Prohibition, or a Conditional holds at most 20 words; a Definition or an Invariant holds at most 25 |
| One instruction per sentence | each main clause carries at most one imperative or one force word |
| Active voice for actions | a Command or a Conditional carries no passive verb |
| Noun clusters | a noun cluster holds at most three nouns; a technical name or a code span counts as one noun |
| Paragraph length | a paragraph holds at most six sentences; a sequence of actions stands as numbered steps, never as a paragraph |
| One topic per paragraph | a paragraph holds one rule and the detail of that rule; no count measures this STE rule |
| Condition before action | §1's Condition first |

**Meet an STE rule by restating the text.** If a sentence passes its word
limit, split it at a clause. If a paragraph passes six sentences, break it
at a joint, per §6. NEVER cut a guarding rationale (§8) to meet an STE rule:
a reader who misses its reason reverts the rule. Rewrite a passive verb with
its actor as the subject. Break a longer noun cluster with a preposition or
a relative clause.

## 15. How the STE rules count

**A word is a run of characters between spaces or line ends that holds a
letter or a digit.** Count no Markdown markup: an emphasis mark, a list mark,
a heading mark, or the target of a link.

**Three units count as one word each.**

| Unit | Counts as |
| --- | --- |
| code span | one word |
| technical name | one word, however many words it holds |
| table cell | one word, in an STE count wider than the cell |

**A file's word count takes every word as written.** NEVER count a unit
above as one word in a file's word count: a table would escape the count.

**A sentence ends at a full stop, a question mark, or an exclamation mark
before a space or a line end.** A mark inside a code span ends no sentence.
The sentence that opens a list ends at its colon. The end of a list item or
of a table cell ends a sentence. A heading is no sentence.

**A paragraph is a run of prose lines between blank lines.** A list, a table,
a heading, and a fenced block are no paragraph.

**A table cell's words meet the word limit of the form its row takes.** If
a row states no rule, its cells take the word limit of a Definition.

**An imperative is a main clause that opens with a bare verb.** A force word
and the verb it governs are one instruction. A main clause ends at a
semicolon, at a colon, and at a comma before `and`, `or`, or `but`.

**A passive verb is a form of `be` or `get` followed by a past participle.**
