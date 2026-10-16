---
name: review-pr
description: Pull request review — if asked to review a pull request, a branch, or a diff, invoke this skill, also when the request never says "review" ("anything wrong with this PR?", "what do you think of these changes?", "look over PR 12") or names a focus ("review PR 12 for security"). The skill prints its findings in the shell and posts nothing to GitHub.
allowed-tools: Read, Grep, Glob, AskUserQuestion, Bash(git status:*), Bash(git branch:*), Bash(git symbolic-ref:*), Bash(git fetch:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*), Bash(gh auth status:*), Bash(gh pr list:*), Bash(gh pr view:*), Bash(gh repo view:*), mcp__github__list_pull_requests, mcp__github__pull_request_read
---

# Review a pull request

Review the change a pull request carries, or the current branch when it has
no pull request, and print the findings in the shell. The printed review is
the whole deliverable: the user reads it and decides what to say on the pull
request.

NEVER write to GitHub: no review, no comment, no approval, no label. NEVER
offer to post the findings either. A post sends notifications and leaves
public text the user never chose.

NEVER change the working tree beyond checking out the branch under review.
NEVER check it out over uncommitted changes without the user's yes.

If the user names a focus (security, performance, a file), review it first
and keep every other finding short.

## What a review checks

1. **The repository's contract.** Read `AGENTS.md` at the repository root,
   `CLAUDE.md` with every file it imports, and `REVIEW.md` if it exists. A
   change that breaks a rule they state is a finding, and the finding cites
   the rule. The rules bind the commits and the title as well as the code: a
   contract that fixes a commit trailer or a title form binds every commit
   and the pull request's title.
2. **The user's guide.** A user may keep a guide at
   `~/.config/review-pr/review_guide.md`. Nothing creates it, so it may be
   absent. If it exists, follow its focus areas, and drop every finding in a
   category its "Skip These" section lists. The guide NEVER skips a contract
   rule.
3. **The defects any change can carry:** bugs, logic errors, and unhandled
   edge cases; security holes (injection, XSS, broken auth, a leaked
   secret); performance costs (N+1 queries, needless work); code that is
   unclear or hard to change; missing or wrong error handling; a critical
   path with no test.

## Phase 1: gather

Read the change with git on a local checkout: `git diff -U10` gives wide
context, and the files around the change are on disk. Use GitHub for
read-only lookups alone: find the pull request, read its metadata, and read
the feedback already on it. Use `gh` when it works. When `gh` is absent or
unauthenticated, make the same lookups with the host's read-only GitHub
tools, such as `list_pull_requests` and `pull_request_read`.

1. **Find what to review.** A pull request number the user gives wins.
   Otherwise list the open pull requests whose head is the current branch:
   ```bash
   gh pr list --head "$(git branch --show-current)" --json number,title
   ```
   * One found: review it.
   * Several found: list them, and ask the user which one to review.
   * None found: review in **branch mode**. A missing pull request is no
     reason to stop. Tell the user that no open pull request was found and
     that you review the branch against the default branch. Name the default
     branch with `git symbolic-ref --short refs/remotes/origin/HEAD` (strip
     the `origin/`), or with
     `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`. Use
     it as `<base>`, and skip steps 2, 3, and 5: branch mode has no pull
     request to read. If the current branch is the default branch, review
     the working tree instead (`git diff HEAD`, and `git status --porcelain`
     for untracked files). If it holds no change, say so and stop.
2. **Read the metadata in one call:**
   ```bash
   gh pr view <number> --json number,title,body,headRefName,baseRefName
   ```
   The title and the body state the intent. `baseRefName` is `<base>`.
3. **Check out the head.** If `git branch --show-current` differs from
   `headRefName`, run `git status --porcelain` first. If it lists a change,
   tell the user and wait for their yes. Then run `gh pr checkout <number>`,
   or without `gh`, `git fetch origin <headRefName>` and
   `git checkout <headRefName>`.
4. **Read the diff.** Fetch the base first, since a fresh clone may lack it:
   ```bash
   git fetch origin <base>
   git diff --stat origin/<base>...HEAD
   git diff -U10 origin/<base>...HEAD
   ```
   Read the `--stat` first. Past about 2000 changed lines, NEVER read the
   whole diff at once. Read it file by file
   (`git diff -U10 origin/<base>...HEAD -- <path>`): the files with the most
   change and the critical paths (auth, security, data handling) first.
   Skip generated files (`*.generated.*`, `*.min.js`), lock files
   (`package-lock.json`, `yarn.lock`, `Cargo.lock`, `uv.lock`), and vendored
   code. A domain vendors agent-core at `vendor/agent-core/` and moves it
   only by `git subtree pull`: skip what a subtree pull brings, and flag any
   other change under `vendor/agent-core/`, since the domain's next subtree
   pull conflicts with it or overwrites it.
5. **Read the feedback already on the pull request,** in its three places,
   so the review never repeats it:
   ```bash
   # inline review comments, each on a file and a line
   gh api repos/{owner}/{repo}/pulls/<number>/comments --jq '.[] | {path, line, body}'
   # review summaries and top-level comments
   gh pr view <number> --json reviews,comments --jq '{reviews: [.reviews[] | {author: .author.login, body}], comments: [.comments[] | {author: .author.login, body}]}'
   ```
   `gh` fills in `{owner}` and `{repo}`; substitute the number yourself.
   NEVER pass `gh api` a method or a field: either one makes it write. Drop
   every finding an existing comment already makes (same file, same line,
   same point).
6. **Read the commits:**
   ```bash
   git log --format='%H%n%s%n%b%n---' origin/<base>..HEAD
   ```
7. **Read the code around the change** from the files on disk wherever the
   diff alone leaves a question open.

### Line numbers

Every finding names a line of the new file, as it stands in the checkout, so
the user can jump to it. In a hunk header `@@ -a,b +c,d @@`, `c` is the
new-file line of the hunk's first line. Count forward through the context
lines and the `+` lines, and skip the `-` lines. When in doubt, confirm the
line with `grep -n` or by reading the file.

## Phase 2: analyse

Read the title, the body, and the commit messages first: they state why the
change exists. Code that does not do what they state is a finding.

Give each issue one severity:

* **Critical** blocks the merge: a bug, a security hole, or a break of a
  contract rule that the contract states with NEVER or that CI enforces.
* **Suggestion** is worth changing before the merge.
* **Nitpick** is style or preference.

Record for each issue its file, its line, its description, its failure
scenario, and its severity.

### Every finding names a failure scenario

A finding enters the review only with a concrete failure scenario: the
input, state, or timing that triggers it, and the wrong output, crash, or
exposure that follows. "This could break" is no scenario. "An empty `items`
list makes `total / len(items)` raise `ZeroDivisionError`" is one.

For a suggestion or a nitpick, where nothing crashes, the scenario is the
concrete cost: what is duplicated, what work is wasted, what grows harder
to change, or which rule breaks.

If you cannot write the scenario, drop the finding. A finding without one is
a guess, and the user cannot turn a guess into a review comment.

Explain why each issue matters, not only what it is: the user writes their
own comments from your reasoning.

## Phase 3: print

Print the review and stop. There is no selection step and no posting step.

* No finding: print the summary block alone.
* One or two findings: print each detail block, then the summary block.
* Three or more findings: print the table, then every detail block, then
  the summary block.

Order the findings by severity, critical first, then by file and line.
Number the table rows and the detail blocks alike, so the user can jump from
one to the other.

The table:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 #  │ Severity │ Location              │ Issue Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1  │ CRITICAL │ auth.rs:45            │ Token expiration not checked
 2  │ SUGGEST  │ auth.rs:23            │ Use constant-time comparison
 3  │ SUGGEST  │ middleware.rs:67      │ Error message reveals user existence
 4  │ NITPICK  │ auth.rs:12            │ Unused import
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

A detail block, which always carries a `Failure scenario:` line:

```
──────────────────────────────────────────────────────
[1] CRITICAL - auth.rs:45
──────────────────────────────────────────────────────
Token expiration is not being checked, so `claims.exp` is never compared
against the current time.

Failure scenario: a client presents a token issued yesterday with a 1-hour
expiry. `decode_token` succeeds, `claims.exp` is ignored, and the request is
authorized as that user.

Context:
    43│     let token = extract_token(&headers)?;
    44│     let claims = decode_token(&token)?;
  > 45│     Ok(claims.user_id)  // Missing: check claims.exp
    46│ }
──────────────────────────────────────────────────────
```

The summary block. In branch mode, its `PR:` line reads
`Branch: <branch> vs <base>`.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Review Complete

PR: #<number> <title>
Critical issues: X
Suggestions: Y
Nitpicks: Z

[If critical issues > 0]
  ⚠️  Critical issues were found. PR should not be merged until addressed.

[If critical issues == 0]
  ✓ No critical issues found.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## When a lookup fails

If a `gh` lookup fails, run `gh auth status` before retrying. If `gh` stays
unusable, use the host's read-only GitHub tools. If the host has none,
review in branch mode, and say in the summary that the pull request's
metadata and feedback went unread.
