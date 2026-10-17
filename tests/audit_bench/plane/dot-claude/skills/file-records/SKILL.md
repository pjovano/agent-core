---
name: file-records
description: "File records — on request, write each record the user gives into the ledger, named by the record name rule."
---

# file-records

The `record-filer` worker runs this skill. Every command is
`python3 .claude/skills/file-records/scripts/file_records.py <subcommand>`.

| Subcommand | Does |
| --- | --- |
| `list` | prints each record name of the ledger |
| `file <title>` | asks the registry to confirm the title, then writes one record |

1. Run `list`. If it exits 1, stop and report its error to the user.
2. Run `file <title>` once for each record. If it exits 1, stop and report its
   error to the user.
3. Report each record name that `file` prints.

**If the registry is offline, `file` prints an error and exits 1.** Stop and
report the error to the user.
