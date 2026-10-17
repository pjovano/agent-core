from __future__ import annotations

from agent_core._audit.checks import DomainChecks
from agent_core._audit.contract import ContractLocations, ContractTables, DictKeys, HookList

CONTRACT = "AGENTS.md"
OPERATION_SECTION = "## 3. Operation"
HOOK_LIST_MARKER = "hook table"

DOMAIN = DomainChecks(contract=ContractLocations(
    operation_tables=ContractTables(CONTRACT, OPERATION_SECTION, ("Operation", "Skill")),
    hook_list=HookList(CONTRACT, HOOK_LIST_MARKER, DictKeys("lib/records.py", "HOOKS")),
))
