# core

What every domain carries. CI splits this directory onto the branch `core`
after every merge to `main`, and a domain vendors that branch at
`vendor/agent-core/` with `git subtree`.

| Part | Holds | Filled by |
| --- | --- | --- |
| `SOUL.md` | the soul file, which every `CLAUDE.md` imports | A6 |
| `skills/` | the shared skills, each linked into a domain's `.claude/skills/` | `core-probe`, `review-pr`, `clean-code`, `clean-prose`, `remember`, and `control-plane-audit`; `clean-code` reads a domain's `.claude/code-overlay.md`, `clean-prose` its `.claude/glossary.md`, `remember` keeps a domain's `USER.md`, and `control-plane-audit` runs the audit engine with a domain's `audit/checks.py` |
| `agents/` | the shared workers, each linked into a domain's `.claude/agents/` | `core-probe` now; the rendered workers in G19 |
| `workflows/` | the shared saved workflows, each linked into a domain's `.claude/workflows/` | `core-probe` now |
| `audit/` | the audit's committed data: the practices digest | U8 |
| `lib/` | `agent_core/`, the core's one Python package: the control-plane audit engine, `_audit/`; the manifest reader and the settings generator, `_domain/`; the host ports `Scheduler`, `Notifier`, and `SystemReadings`, with their macOS adapters; the agent-host port and its adapters | the audit engine, `_domain/`, and the host ports now; the agent-host port in G19 |
| `templates/domain/` | the domain template `new-domain` copies | A5 |
| `domain.py` | the command line of the manifest reader, `domain.py manifests`, and of the settings generator, `domain.py settings` and `domain.py guards` | G20 |

Every part exists from the start, and `agent-core`'s
`tests/test_core_layout.py` pins it. Until an item fills a directory of the
table, the directory holds an empty `.gitkeep`, so that git tracks it; the
item that fills it deletes the `.gitkeep`.

## `domain.json`

Each domain keeps one `domain.json` at its root. `domain.py manifests` reads
every `~/Developer/*/domain.json`, or the manifests named on its command line,
and refuses a manifest with an unknown folder key or policy key, so that a
misspelt `sensitive` never drops a guard.

| Field | Holds |
| --- | --- |
| `name` | the domain's name, the repository's name |
| `summary` | one sentence on what the domain does |
| `folders` | the folders directly in `~/Documents` the domain works on: each a `name`, an `access` of `read` or `write`, an optional `sensitive: true`, and, on a `write` folder, an optional `write_within`, the subfolders its sandboxed writes are limited to |
| `policy.allow` | the permission rules `permissions.allow` carries; an `Edit` or `Write` rule under `~/Documents` names a `write` folder |
| `policy.prompt_on` | each command fragment the domain's own hook turns into a permission prompt, with the consequence the prompt names |
| `policy.network_hosts` | the hosts the sandbox lets a command reach |
| `policy.allow_local_binding` | whether a sandboxed command may bind a local port |
| `policy.write_paths` | the paths under `~` and outside `~/Documents` a sandboxed command may write |
| `policy.excluded_commands` | the commands that run outside the sandbox |

No field names a path beginning with `/`: a path under `~` resolves on any
machine.

## `domain.py settings` and `domain.py guards`

`domain.py settings` prints the `permissions` and `sandbox` blocks of
`.claude/settings.json` for the domain whose manifest `--domain` names,
`./domain.json` by default, from that manifest alone. The sandbox writes to
exactly the `write` folders, narrowed by `write_within`, and to
`policy.write_paths`.

**A guard keeps a domain out of another domain's sensitive folder.** A guard
is three rules for one folder: a `Read(~/Documents/<folder>/**)` and an
`Edit(~/Documents/<folder>/**)` rule in `permissions.deny`, and a
`sandbox.filesystem.denyRead` entry. For each `sensitive` folder of another
manifest that `domain.py manifests` reads, `domain.py guards` prints one
guard, unless the domain's manifest lists the folder. If no folder needs a
guard, the command prints both lists empty.

**The guards go into `.claude/settings.local.json`, which the domain's
`.gitignore` names.** NEVER commit a guard: a guard names another domain's
folder, and a domain's repository MAY be public. Claude Code merges these
lists with the lists of `.claude/settings.json`.

Neither command writes a file. The session writes the output with the Write
tool: the sandbox denies Bash every write to `.claude/settings.json`.

**What Claude Code enforces from the blocks and the guards.** The sandbox
binds Bash alone, and only where the sandbox runs.

| Policy part | Setting | Enforced by | Does not hold |
| --- | --- | --- | --- |
| `write` folders and `policy.write_paths` | `sandbox.filesystem.allowWrite` | the sandbox, on a Bash command | in a cloud session, whose sandbox is inert; for the Edit and Write tools, which follow permission rules |
| a `sensitive` folder of another domain | `sandbox.filesystem.denyRead` | the sandbox, on a Bash command | for the Read tool; in a cloud session |
| the same folder | `Read(...)` in `permissions.deny` | the permission rules, on the Read tool, in every permission mode, also in an untrusted workspace | for Grep and Glob, untested: the docs apply Read rules to them only as a best effort |
| the same folder | `Edit(...)` in `permissions.deny` | the permission rules, on every tool that edits a file, in every permission mode | — |
| `policy.allow` | `permissions.allow` | the permission rules: a matching call runs without a prompt | in a headless session in an untrusted workspace, which ignores the rules; an allow rule carries no guarantee |
| `policy.network_hosts`, `policy.allow_local_binding` | `sandbox.network` | the sandbox, on a Bash command | in a cloud session |
| `policy.excluded_commands` | `sandbox.excludedCommands` | nothing: each command runs outside the sandbox | — |
| `policy.prompt_on` | none | the domain's own hook, which reads `domain.json` | in a domain without such a hook |

The `core-probe` skill, worker, and workflow prove that a linked core unit
loads. The item that gives the core its first real worker and workflow
removes them.

This directory never holds an `AGENTS.md` or a `CLAUDE.md`: the dispatcher's
contract stays at the repository root and never enters a domain.

`SOUL.md` is no contract: it states conduct, never a repository's rules, and
a domain imports it from `vendor/agent-core/SOUL.md`. It is instruction text,
and `clean-prose` binds it.
