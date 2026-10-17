---
name: control-plane-audit
description: "Control-plane audit — run the core's audit engine over one repository's control plane: the audit set since the last accepted audit, the lint rows, the checks the repository's audit/checks.py adds, and the audit baseline. Use when asked to audit or lint a control plane that has no audit skill of its own."
---

# control-plane-audit

The engine audits one root: the working directory, or the directory `--root`
names. A domain's own audit skill MAY invoke the engine and add its procedure.

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

`lint` reads every control-plane file, whatever the audit set: a script's
coverage costs no judgment.

**If the audit baseline is not valid JSON, every command prints
`{"error": …}` and exits 1.** Restore the audit baseline from git, then run
the command again.

**If `audit/checks.py` defines no `DOMAIN`, every command fails and names the
file.** Stop and report the failure to the user.

**Run `accept` ONLY on the user's instruction:** accepting records every file
as audited, and an unfixed finding then goes unread until its file changes.
