# agent-core

Two parts in one repository:

- `core/` holds what every domain shares. After every merge to `main`, CI
  splits it onto the branch `core`, and each domain vendors that branch at
  `vendor/agent-core/` with `git subtree add --squash`, then moves to a newer
  core with `git subtree pull --squash`.
- The root holds the dispatcher: its contract (`AGENTS.md`, imported by
  `CLAUDE.md`), its `.claude/` settings, the tests, and CI.

A domain links each core skill, worker, and workflow it uses into its own
`.claude/` with a relative symlink into `vendor/agent-core/`.
