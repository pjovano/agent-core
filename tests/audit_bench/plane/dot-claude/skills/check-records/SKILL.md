---
name: check-records
description: "Check records — on request, report each record of the ledger whose name breaks the record name rule."
---

# check-records

The `record-checker` worker runs this skill. The check changes no record.

1. Run `python3 .claude/skills/file-records/scripts/file_records.py list`. If
   it exits 1, stop and report its error to the user.
2. For each record name that `list` prints, compare the name with the record
   name rule in `lib/records.py`.
3. Report each record name that breaks the rule, with the rule it breaks.

**If `list` prints no record name, report that the ledger is empty.**

**If a record name breaks the rule, name the record in the report.**
