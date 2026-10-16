# core

What every domain carries. CI splits this directory onto the branch `core`
after every merge to `main`, and a domain vendors that branch at
`vendor/agent-core/` with `git subtree`.

| Part | Holds | Filled by |
| --- | --- | --- |
| `SOUL.md` | the soul file, which every `CLAUDE.md` imports | A6 |
| `skills/` | the shared skills, each linked into a domain's `.claude/skills/` | `core-probe`, `review-pr`, `clean-code`, `clean-prose`, and `remember`; `clean-code` reads a domain's `.claude/code-overlay.md`, `clean-prose` its `.claude/glossary.md`, and `remember` keeps a domain's `USER.md` |
| `agents/` | the shared workers, each linked into a domain's `.claude/agents/` | `core-probe` now; the rendered workers in G19 |
| `workflows/` | the shared saved workflows, each linked into a domain's `.claude/workflows/` | `core-probe` now |
| `audit/` | the control-plane audit engine | A2 |
| `lib/` | `agent_core/`, the core's one Python package: the host ports `Scheduler`, `Notifier`, and `SystemReadings`, with their macOS adapters; the agent-host port and its adapters | the host ports now; the agent-host port in G19 |
| `templates/domain/` | the domain template `new-domain` copies | A5 |
| `domain.py` | the manifest reader and the settings generator | G20 |

Every part exists from the start, and `agent-core`'s
`tests/test_core_layout.py` pins it. Until an item fills a directory of the
table, the directory holds an empty `.gitkeep`, so that git tracks it; the
item that fills it deletes the `.gitkeep`. `domain.py` stays empty until G20
fills it.

The `core-probe` skill, worker, and workflow prove that a linked core unit
loads. The item that gives the core its first real worker and workflow
removes them.

This directory never holds an `AGENTS.md` or a `CLAUDE.md`: the dispatcher's
contract stays at the repository root and never enters a domain.

`SOUL.md` is no contract: it states conduct, never a repository's rules, and
a domain imports it from `vendor/agent-core/SOUL.md`. It is instruction text,
and `clean-prose` binds it.
