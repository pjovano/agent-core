from __future__ import annotations

import json
import unittest

from _audit_files import AuditRun, TemporaryFiles

CONTRACT = """# Contract

## 3. Operation

| Operation | Skill | Run by | Model |
| --- | --- | --- | --- |
| File | `file-records` | the `record-filer` worker | Sonnet |
| Check | `check-records` | the orchestrator; the session's | the session's |

**The hook table in `lib/records.py` names one hook, `pre-write`.**
"""
SKILL = """---
name: file-records
description: "File records."
---

# file-records

Every command is `python3 .claude/skills/file-records/scripts/file_records.py <subcommand>`.

| Subcommand | Does |
| --- | --- |
| `list` | prints each record |
| `file <title>` | writes one record |
"""
CHECK_SKILL = ("---\nname: check-records\ndescription: \"Check records.\"\n---\n\n# check-records\n\n"
               "Run `file_records.py list`.\n")
WORKER = "---\nname: record-filer\ndescription: \"Record filer.\"\nmodel: sonnet\n---\n\n# record-filer\n"
SCRIPT = """import argparse


def parser():
    program = argparse.ArgumentParser()
    commands = program.add_subparsers()
    commands.add_parser("list")
    commands.add_parser("file")
    return program
"""
HOOKS = "def refuse(path):\n    return path\n\n\nHOOKS = {\"pre-write\": refuse}\n"
SCRIPT_ENTRY = "Bash(python3 .claude/skills/file-records/scripts/file_records.py {}:*)"
CHECKS = """from agent_core._audit.checks import DomainChecks
from agent_core._audit.contract import ContractLocations, ContractTables, DictKeys, HookList

DOMAIN = DomainChecks(contract=ContractLocations(
    operation_tables=ContractTables("AGENTS.md", "## 3. Operation", ("Operation", "Skill")),
    hook_list=HookList("AGENTS.md", "hook table", DictKeys("lib/records.py", "HOOKS")),
))
"""
SCRIPT_PATH = ".claude/skills/file-records/scripts/file_records.py"
SKILL_PATH = ".claude/skills/file-records/SKILL.md"


class XrefPlane:
    def __init__(self, case: unittest.TestCase) -> None:
        self.files = TemporaryFiles(case)
        written = {"AGENTS.md": CONTRACT, SKILL_PATH: SKILL, ".claude/skills/check-records/SKILL.md": CHECK_SKILL,
                   ".claude/agents/record-filer.md": WORKER, SCRIPT_PATH: SCRIPT, "lib/records.py": HOOKS,
                   "audit/checks.py": CHECKS}
        for name, text in written.items():
            self.files.written(name, text)
        self.allowed(["list", "file"])

    def allowed(self, subcommands: list[str]) -> None:
        entries = [SCRIPT_ENTRY.format(name) for name in subcommands]
        self.files.written(".claude/settings.json", json.dumps({"permissions": {"allow": entries}}, indent=2))

    def changed(self, name: str, old: str, new: str) -> None:
        path = self.files.root / name
        path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")

    def rows(self) -> list[tuple[str, str]]:
        return [(row["rule"], row["file"]) for row in AuditRun(self.files.root).payload("lint")["xref"]]


class TestAConsistentPlane(unittest.TestCase):
    def test_a_consistent_plane_yields_no_xref_row(self) -> None:
        self.assertEqual([], XrefPlane(self).rows())


class TestSubcommands(unittest.TestCase):
    def setUp(self) -> None:
        self.plane = XrefPlane(self)

    def test_a_subcommand_in_prose_but_not_in_the_parser_is_a_row(self) -> None:
        self.plane.changed(SKILL_PATH, "| `list` |", "| `purge` | deletes |\n| `list` |")
        self.assertIn(("subcommand-not-in-parser", SKILL_PATH), self.plane.rows())

    def test_a_script_call_naming_an_absent_subcommand_is_a_row(self) -> None:
        self.plane.changed(".claude/skills/check-records/SKILL.md", "file_records.py list", "file_records.py lsit")
        self.assertIn(("subcommand-not-in-parser", ".claude/skills/check-records/SKILL.md"), self.plane.rows())

    def test_a_subcommand_in_the_parser_but_not_in_prose_is_a_row(self) -> None:
        self.plane.changed(SCRIPT_PATH, "    return program", "    commands.add_parser(\"export\")\n    return program")
        self.plane.allowed(["list", "file", "export"])
        self.assertEqual([("subcommand-not-in-prose", SCRIPT_PATH)], self.plane.rows())

    def test_a_subcommand_named_after_its_parent_in_a_code_span_is_named(self) -> None:
        self.plane.changed(SCRIPT_PATH, "    return program", "    commands.add_parser(\"learn\")\n    return program")
        self.plane.allowed(["list", "file", "learn"])
        self.plane.changed(SKILL_PATH, "| `list` | prints each record |", "| `list` | prints; `fonts learn` records a font |")
        self.assertEqual([], self.plane.rows())

    def test_a_parser_with_a_computed_name_is_never_read_as_complete(self) -> None:
        self.plane.changed(SCRIPT_PATH, "    return program", "    commands.add_parser(NAME)\n    return program")
        self.plane.changed(SKILL_PATH, "| `list` |", "| `purge` | deletes |\n| `list` |")
        self.assertNotIn(("subcommand-not-in-parser", SKILL_PATH), self.plane.rows())


class TestTheAllowList(unittest.TestCase):
    def setUp(self) -> None:
        self.plane = XrefPlane(self)

    def test_an_entry_naming_no_subcommand_of_its_script_is_a_row(self) -> None:
        self.plane.allowed(["list", "file", "rebuild"])
        self.assertEqual([("entry-without-subcommand", ".claude/settings.json")], self.plane.rows())

    def test_a_subcommand_no_entry_names_is_a_row(self) -> None:
        self.plane.allowed(["list"])
        self.assertEqual([("subcommand-without-entry", SCRIPT_PATH)], self.plane.rows())

    def test_an_entry_for_the_whole_script_covers_every_subcommand(self) -> None:
        entry = "Bash(python3 .claude/skills/file-records/scripts/file_records.py:*)"
        self.plane.files.written(".claude/settings.json", json.dumps({"permissions": {"allow": [entry]}}))
        self.assertEqual([], self.plane.rows())


class TestWorkersAndModels(unittest.TestCase):
    def setUp(self) -> None:
        self.plane = XrefPlane(self)

    def test_a_worker_in_prose_without_instructions_is_a_row(self) -> None:
        self.plane.changed(SKILL_PATH, "# file-records\n", "# file-records\n\nThe `record-sorter` worker sorts.\n")
        self.assertEqual([("worker-missing", SKILL_PATH)], self.plane.rows())

    def test_a_worker_model_the_model_column_does_not_name_is_a_row(self) -> None:
        self.plane.changed(".claude/agents/record-filer.md", "model: sonnet", "model: opus")
        self.assertEqual([("model-contradicts-table", ".claude/agents/record-filer.md")], self.plane.rows())

    def test_a_full_model_identifier_of_the_named_family_is_no_row(self) -> None:
        self.plane.changed(".claude/agents/record-filer.md", "model: sonnet", "model: claude-sonnet-5")
        self.assertEqual([], self.plane.rows())

    def test_an_inherited_model_under_the_sessions_model_is_no_row(self) -> None:
        self.plane.changed("AGENTS.md", "| Sonnet |", "| the session's |")
        self.plane.changed(".claude/agents/record-filer.md", "model: sonnet", "model: inherit")
        self.assertEqual([], self.plane.rows())


class TestHooksAndSkills(unittest.TestCase):
    def setUp(self) -> None:
        self.plane = XrefPlane(self)

    def test_a_hook_the_contract_names_but_the_module_lacks_is_a_row(self) -> None:
        self.plane.changed("AGENTS.md", "one hook, `pre-write`.", "two hooks, `pre-write` and `post-write`.")
        self.assertEqual([("hook-not-in-module", "AGENTS.md")], self.plane.rows())

    def test_a_hook_the_module_holds_but_the_contract_omits_is_a_row(self) -> None:
        self.plane.changed("lib/records.py", "refuse}", "refuse, \"post-write\": refuse}")
        self.assertEqual([("hook-not-in-contract", "lib/records.py")], self.plane.rows())

    def test_an_operation_table_skill_without_a_skill_directory_is_a_row(self) -> None:
        self.plane.changed("AGENTS.md", "| `check-records` |", "| `sort-records` |")
        self.assertEqual([("skill-missing", "AGENTS.md")], self.plane.rows())


class TestTheEnginesOwnSubcommands(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.files.written("AGENTS.md", "# Contract\n")
        self.files.written(".claude/skills/control-plane-audit/scripts/audit.py", "print('engine')\n")

    def _rows(self, prose: str) -> list[str]:
        self.files.written(".claude/skills/audit-notes/SKILL.md", prose)
        return [row["rule"] for row in AuditRun(self.files.root).payload("lint")["xref"]]

    def test_a_subcommand_of_the_engine_in_prose_is_no_row(self) -> None:
        self.assertEqual([], self._rows("Run `audit.py acknowledge` and `audit.py ratchet`.\n"))

    def test_a_subcommand_the_engine_lacks_is_a_row(self) -> None:
        self.assertEqual(["subcommand-not-in-parser"], self._rows("Run `audit.py forgive`.\n"))


if __name__ == "__main__":
    unittest.main()
