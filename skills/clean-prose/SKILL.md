---
name: clean-prose
description: Enforces the prose standard on instruction text, which is AGENTS.md, SKILL.md files, worker instructions, and any reference file a skill loads. Use this skill before adding or editing any instruction prose, including a one-sentence change; it also governs how the orchestrator explains its own work in chat. Not for domain content.
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

Applies to the repository's contract, every `SKILL.md`, every set of worker
instructions, and every reference file a skill loads. §9 applies it to the
orchestrator's explanation of its own work in chat.

Does not apply to domain content: what a domain writes for the user to read,
and the user's own writing, as the domain's glossary names them. One exception
binds: §6's paragraph rule applies to domain content too.

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
140 words, look for a joint. Length alone NEVER forces a break, and NEVER merge
two units to balance length. An enumeration breaks between its items and NEVER
inside one; if its items run about a line each, the list stays one paragraph at
any length. Per Scope, this rule binds domain content as well.

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

**When an action fails, name the failure branch the instruction specifies.**
NEVER improvise a recovery silently.

**Mark judgment as judgment.** If no rule governs a choice, say so: "No rule
covers this; choosing X because Y." NEVER present a preference as a
requirement, and NEVER present a requirement as a preference.

**When reversing a recommendation, name what changed:** the rule, the
measurement, or the fact. A reversal with no stated cause is indistinguishable
from noise.

**Banned: narration that cites nothing.** *Let me go ahead and…*, *I'll just…*,
*Now I'll…*. Each announces an action while withholding its reason.

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
