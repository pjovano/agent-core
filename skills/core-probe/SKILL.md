---
name: core-probe
description: Core probe — if asked to probe the core, invoke this skill. The skill replies CORE-PROBE-SKILL-OK, which proves that a core skill loads through its symlink.
---

# Core probe

Reply with the one line `CORE-PROBE-SKILL-OK`. NEVER read a file, run a
command, or dispatch a worker.
