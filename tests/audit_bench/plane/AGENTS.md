# Ledger — Contract

## 1. Mandate

The ledger is a directory of records. You keep it: you file each record the
user gives, and you check the ledger when the user asks.

## 2. Layout

The control plane holds two skills and two workers.

| Part | Path | Is |
| --- | --- | --- |
| glossary | `.claude/glossary.md` | the terms of the ledger |
| skills | `.claude/skills/` | `file-records` and `check-records` |
| workers | `.claude/agents/` | `record-filer` and `record-checker` |
| shared code | `lib/records.py` | the record name rule, the atomic write, and the hook table |

## 3. Operation

| Operation | Skill | Run by | Model |
| --- | --- | --- | --- |
| File | `file-records` | the `record-filer` worker | Sonnet |
| Check | `check-records` | the `record-checker` worker | Haiku |

**Write every record through `lib/records.py`.** NEVER write a record in any
other way: the atomic write keeps a crash from leaving half a record.

**A record title holds at most twelve words.** The record name rule refuses a
longer title.

**The check changes no record.** The user fixes each record the check reports.

**The hook table in `lib/records.py` names one hook, `pre-write`.** The hook
refuses a record name the ledger already holds.

## 4. Standards

Run the checks after every change. If a check fails, fix its cause before you
commit.
