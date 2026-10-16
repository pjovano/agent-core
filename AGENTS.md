# agent-core — Contract

This contract is a placeholder. It states the repository's layout and its
standards; the dispatcher's own rules arrive with its skills.

## 1. Layout

The repository holds two parts.

| Part | Path | Is |
| --- | --- | --- |
| core | `core/` | what every domain carries: `SOUL.md`, `skills/`, `agents/`, `workflows/`, `audit/`, `lib/`, `templates/domain/`, `domain.py`; `core/README.md` names the parts still empty |
| dispatcher | the root | this contract, `CLAUDE.md`, `.claude/`, `bin/`, `tests/`, `pyproject.toml`, `.gitleaks.toml`, and `.github/`; `bin/remote_control.py` installs the Remote Control job, which no domain carries |
| branch `core` | — | `core/` alone, split from `main` by CI after every merge; every domain vendors it at `vendor/agent-core/` with `git subtree` |

**`core/SOUL.md` binds every session.** The soul file is the standard of
conduct every session keeps. `CLAUDE.md` holds two lines: `@AGENTS.md`, then
`@core/SOUL.md`. If a host reads only this contract, read `core/SOUL.md`
whole after it.

**The dispatcher keeps no `USER.md`.** It routes each request to a domain
session, which holds the user file. NEVER create a `USER.md` in this
repository, and NEVER commit one: `.gitignore` names `/USER.md`, and a test
fails if git tracks a `USER.md` at any depth.

## 2. Rules of the layout

* **`core/` holds no contract.** NEVER put an `AGENTS.md` or a `CLAUDE.md`
  in `core/`: the branch `core` carries `core/` into every domain, and the
  dispatcher's contract never enters a domain.
* **A core unit the root uses is a link.** Each core skill the dispatcher
  uses sits at `.claude/skills/<skill>`, each core worker at
  `.claude/agents/<worker>.md`, and each core workflow at
  `.claude/workflows/<workflow>.js`, as a relative symlink into `core/`.
  NEVER copy a core unit into `.claude/`, and NEVER link one by an absolute
  path: a copy drifts, and an absolute path names one machine.
* **Edit a core unit at its path under `core/`.** NEVER edit it through its
  link under `.claude/`.
* **CI alone writes the branch `core`.** NEVER commit on `core` or push to
  it: a domain's next `git subtree pull` expects `core` to extend the history
  it vendored.

## 3. Standards

**Every change reaches `main` through a pull request.**

* Commit on a branch cut from `main`; NEVER commit on `main` itself.
* Title the pull request with the rule or the behaviour the change leaves in
  place. NEVER title it by a date, a run, or its branch name alone.
* End every commit message with a trailer: `Defect-class: <class>` for a
  fix, or `Change-class: refactor|feature — <what>` otherwise.

**Run the checks from the repository root after every change**, and fix
every failure they name:

* the suite: `python3 -m unittest discover -s tests`;
* the linter: `ruff check .`, the version `.github/workflows/ci.yml` pins.

CI fails a pull request that fails the suite, the linter, the secret scan,
or the decision gate. The secret scan runs gitleaks over the tree and every
commit. The decision gate fails while the pull request carries the
`needs-decision` label.

**If `.claude/skills/clean-code/` exists, invoke `clean-code` before writing
or changing code. If `.claude/skills/clean-prose/` exists, invoke
`clean-prose` before writing or changing instruction text.**
