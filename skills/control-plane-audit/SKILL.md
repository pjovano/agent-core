---
name: control-plane-audit
description: "Control-plane audit — run the core's audit engine over one repository's control plane: the audit set since the last accepted audit, the lint rows, the checks the repository's audit/checks.py adds, and the audit baseline. Use when asked to audit or lint a control plane that has no audit skill of its own."
---

# control-plane-audit

The engine audits one root. The root is the directory `--root` names. If
`--root` is absent, the root is the nearest directory above the script's named
path that holds `.claude/skills/control-plane-audit`. The script's named path
is the path the command names, before any symlink resolves. A domain's own
audit skill MAY invoke the engine and add its procedure.

## Definitions

* **Audit baseline.** `audit/baseline.json` under the root holds one digest
  per control-plane file, as of the last accepted audit. Each domain keeps
  its own audit baseline.
* **Audit set.** The audit set is the files a run reads whole: every file
  changed since the last accepted audit, and every control-plane file whose
  text names one of them.
* **Domain checks.** `audit/checks.py` under the root defines `DOMAIN`, a
  `DomainChecks`. If the file is absent, the engine runs the core's checks
  alone.

| Field of `DomainChecks` | Holds |
| --- | --- |
| `scope` | a `Scope`: the root files, group patterns, path prefixes, and named roots the domain adds to the core's |
| `lint` | each lint check: a `name`, and `findings(audit_set)`, which returns the check's rows |
| `reports` | each report: a `name`, a `help`, and `report(root)`, which returns a JSON object |

A report wrapped in `PrimaryOnly` runs only where its presence holds.
Elsewhere the report prints `{"skipped": <reason>}`.

## Commands

Every command is `python3 .claude/skills/control-plane-audit/scripts/audit.py
[--root <root>] <subcommand>`. If the root's contract names an interpreter,
run the command under that interpreter.

| Command | Prints | Writes |
| --- | --- | --- |
| `changed` | `accepted`, the audit set as `changed` and `related`, the `removed` files, and `counts` | nothing |
| `changed --all` | the same, with every control-plane file as the audit set | nothing |
| `lint` | `files`, the counts; `code`, one row per Clean Code measure; `pointers`, one row per dead path or future date; then one key per lint check of the domain checks | nothing |
| `lint --changed` | the same, over the audit set alone | nothing |
| the name of a report | the report of the domain checks with that name | nothing |
| `accept` | the date recorded and the number of files | the audit baseline |
| `bench build <dir>` | the seed manifest: each seed's `id`, `check`, `class`, and `negative`, with its `file`, `line`, and `end`, or its `commit` | `<dir>`: the seeded plane, its git history, and `bench-manifest.json` |
| `bench score <dir> <findings>` | `seeds`, `found`, `recall`, and `per_check` over every layer; `per_layer`; `missed`; `false_positives`; `unmatched` | nothing |

`lint` reads every control-plane file, whatever the audit set: a script's
coverage costs no judgment.

**If the audit baseline is not valid JSON, every command prints
`{"error": …}` and exits 1.** Restore the audit baseline from git, then run
the command again.

**If no root is found, every command prints `{"error": …}` and exits 1.**
Run the command again with `--root` and the domain root.

**If `audit/checks.py` defines no `DOMAIN`, every command fails and names the
file.** Stop and report the failure to the user.

**Run `accept` ONLY on the user's instruction:** accepting records every file
as audited, and an unfixed finding then goes unread until its file changes.

## The audit test bench

**The bench measures an audit's recall.** The bench is a synthetic control
plane, `tests/audit_bench/plane/` under the root, with one seed per defect
class in `tests/audit_bench/seeds.json`. Only `agent-core` holds the bench.

* **Seed.** A seed is one defect: `{id, check, class, target, mutation}`. Its
  `mutation` holds `find` and `replace`, or `after` and `insert`.
* **Commit seed.** A commit seed is a seed whose `mutation` holds `message`.
  The build applies it in a commit of its own, with that message.
* **Negative seed.** A negative seed is a seed that carries `"negative": true`.
  Every finding inside its window is a false positive.
* **Window.** A seed's window is the lines of its new text, widened by two
  lines on each side. A commit seed's window is its commit.
* **Found.** A finding finds a seed if both name one check and the finding
  falls inside the seed's window. A finding names a commit by seven or more
  leading characters of its hash.
* **Recall.** A check's recall is the share of its seeds that a finding
  finds. `per_layer` gives the recall of each layer's findings alone.

**`bench build` reads the bench from the root and writes only into
`<dir>`.** The build copies the plane and renames each top-level `dot-` entry
to begin with `.`: the plane stores `.claude/` as `dot-claude/`, so that no
session loads the plane's skills from `agent-core`. The build records the
plane at rest in the audit baseline of `<dir>` and commits it. Then the build
commits every seed but the commit seeds, then each commit seed alone.

**`bench score` reads two shapes of findings file.** An object is the output
of `lint`: each key whose value is a list is a check, and each row is a
finding of the layer `lint`. A list holds findings, each with `check`, `file`,
`line`, and `layer`.

**If a bench command fails, the command prints `{"error": …}` and exits 1.**

| Command | Fails if | Fix |
| --- | --- | --- |
| `bench build` | the root holds no `tests/audit_bench/` | run the command again with `--root` and the root of `agent-core` |
| `bench build` | `<dir>` holds a file | name a new or empty directory |
| `bench build` | a seed's anchor occurs other than once in its target, or its new text occurs other than once after every seed | fix that seed in `seeds.json` |
| `bench build` | the windows of two seeds of one check overlap, or a negative seed's window overlaps another seed's | move one seed of the pair in `seeds.json` |
| `bench build` | git is absent, or a git command fails | stop and report the error to the user |
| `bench score` | `<dir>` holds no `bench-manifest.json` | run `bench build` on a new directory first |
| `bench score` | the findings file is no JSON, or a finding lacks a field | fix the findings file |
