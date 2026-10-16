# core

What every domain carries. CI splits this directory onto the branch `core`
after every merge to `main`, and a domain vendors that branch at
`vendor/agent-core/` with `git subtree`.

| Part | Holds | Filled by |
| --- | --- | --- |
| `skills/` | the shared skills, each linked into a domain's `.claude/skills/` | `core-probe` now; `clean-code` and `clean-prose` in A1 |
| `agents/` | the shared workers, each linked into a domain's `.claude/agents/` | `core-probe` now; the rendered workers in G19 |
| `workflows/` | the shared saved workflows, each linked into a domain's `.claude/workflows/` | `core-probe` now |
| `audit/` | the control-plane audit engine | A2 |
| `lib/` | the agent-host port and its adapters | G19 |
| `templates/domain/` | the domain template `new-domain` copies | A5 |
| `domain.py` | the manifest reader and the settings generator | G20 |

The `core-probe` skill, worker, and workflow prove that a linked core unit
loads. A1 removes them once the core holds its first real skills.

This directory never holds an `AGENTS.md` or a `CLAUDE.md`: the dispatcher's
contract stays at the repository root and never enters a domain.
