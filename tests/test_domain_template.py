from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _new_domain import BASIC_ANSWERS, CORE_DIR, TEMPLATE_DIR, NewDomainRun, Outcome, PublishedCore, \
    isolated_environment
from _repository import REPOSITORY_ROOT

RENDERED_SUFFIX = ".template"
CONTRACT_NAMES = ("AGENTS.md", "CLAUDE.md")
LINKED_KINDS = ("skills", "agents", "workflows")
VENDORED_CORE = "vendor/agent-core"
HOME_PREFIX = "~/"
DECISION_GATE = Path(".github") / "workflows" / "decision-gate.yml"
CI_VARIABLE = "CI"
CI_VALUE = "true"
GITLEAKS_SCANS = ("git", "dir")
CI_WORKFLOW = Path(".github") / "workflows" / "ci.yml"
GITLEAKS_ACTION = Path(".github") / "actions" / "install-gitleaks" / "action.yml"
PIN_PATTERN = re.compile(r"^\s*((?:RUFF|GITLEAKS)_(?:VERSION|SHA256)): (\S+)$", re.MULTILINE)


class ToolOnPath:
    def __init__(self, case: unittest.TestCase, name: str) -> None:
        self._case = case
        self._name = name

    def path(self) -> str:
        found = shutil.which(self._name)
        if found is None:
            self._missing()
        return found

    def _missing(self) -> None:
        if os.environ.get(CI_VARIABLE) == CI_VALUE:
            self._case.fail(f"{self._name} is not on PATH; CI installs it before the suite runs")
        self._case.skipTest(f"{self._name} is not on PATH")


class ADomainMadeFromTheTemplate(unittest.TestCase):
    outcome: Outcome

    @classmethod
    def setUpClass(cls) -> None:
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        workspace = Path(directory.name)
        cls.outcome = NewDomainRun(workspace, PublishedCore(workspace).published()).create(BASIC_ANSWERS)
        cls.environment = isolated_environment(workspace / "home")

    def run_in_domain(self, *arguments: str) -> subprocess.CompletedProcess:
        return self.run_tool_in_domain(sys.executable, *arguments)

    def run_tool_in_domain(self, *command: str) -> subprocess.CompletedProcess:
        return subprocess.run(command, cwd=self.outcome.domain, capture_output=True, text=True, env=self.environment)

    def test_its_own_linter_passes(self) -> None:
        completed = self.run_tool_in_domain(ToolOnPath(self, "ruff").path(), "check", ".")
        self.assertEqual(0, completed.returncode, completed.stdout)

    def test_its_own_secret_scan_passes_over_the_tree_and_every_commit(self) -> None:
        gitleaks = ToolOnPath(self, "gitleaks").path()
        for scan in GITLEAKS_SCANS:
            with self.subTest(scan=scan):
                completed = self.run_tool_in_domain(gitleaks, scan, "--config", ".gitleaks.toml", "--redact",
                                                    "--exit-code", "1", ".")
                self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_its_decision_gate_is_the_gate_the_core_passes_on_every_pull_request(self) -> None:
        self.assertEqual((REPOSITORY_ROOT / DECISION_GATE).read_text(encoding="utf-8"),
                         (self.outcome.domain / DECISION_GATE).read_text(encoding="utf-8"))

    def test_its_own_suite_passes(self) -> None:
        completed = self.run_in_domain("-m", "unittest", "discover", "-s", "tests")
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_the_core_audit_lints_it_and_finds_no_path_missing_from_a_fresh_clone(self) -> None:
        completed = self.run_in_domain(".claude/skills/control-plane-audit/scripts/audit.py", "lint")
        self.assertEqual(0, completed.returncode, completed.stderr)
        pointers = json.loads(completed.stdout)["pointers"]
        self.assertEqual([], [finding for finding in pointers if self._belongs_in_a_clone(finding["detail"])])

    def _belongs_in_a_clone(self, path: str) -> bool:
        ignored = (self.outcome.domain / ".gitignore").read_text(encoding="utf-8").splitlines()
        return not path.startswith(HOME_PREFIX) and f"/{path}" not in ignored

    def test_it_links_every_core_unit_by_a_relative_path(self) -> None:
        expected = sorted(f"{kind}/{unit.name}" for kind in LINKED_KINDS for unit in (CORE_DIR / kind).iterdir()
                          if unit.name != ".gitkeep")
        linked = sorted(f"{kind}/{link.name}" for kind in LINKED_KINDS
                        for link in (self.outcome.domain / ".claude" / kind).iterdir()
                        if link.is_symlink() and not os.path.isabs(os.readlink(link)))
        self.assertEqual(expected, linked)

    def test_its_contract_and_claude_md_carry_their_names_without_the_template_suffix(self) -> None:
        present = [name for name in CONTRACT_NAMES if (self.outcome.domain / name).is_file()]
        rendered = [path.name for path in self.outcome.domain.rglob(f"*{RENDERED_SUFFIX}")
                    if not path.is_relative_to(self.outcome.domain / VENDORED_CORE)]
        self.assertEqual((list(CONTRACT_NAMES), []), (present, rendered))

    def test_its_contract_carries_the_mandate(self) -> None:
        contract = (self.outcome.domain / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(BASIC_ANSWERS["mandate"], contract)

    def test_its_working_tree_is_committed(self) -> None:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.outcome.domain, capture_output=True,
                                text=True, env=self.environment).stdout
        self.assertEqual("", status)


class TheTemplateHoldsNoFileThatBreaksTheCore(unittest.TestCase):
    def test_it_holds_no_user_file(self) -> None:
        self.assertEqual([], list(TEMPLATE_DIR.rglob("USER.md")))

    def test_its_vault_config_names_no_path_and_no_colour_group(self) -> None:
        graph = json.loads((TEMPLATE_DIR / "obsidian" / "graph.json").read_text(encoding="utf-8"))
        self.assertEqual(("", []), (graph["search"], graph["colorGroups"]))


class TheCoresCiInstallsTheToolVersionsTheDomainsCiPins(unittest.TestCase):
    def test_each_pinned_version_matches(self) -> None:
        domain_ci = PinnedVersions(TEMPLATE_DIR / CI_WORKFLOW).values()
        core_ci = {**PinnedVersions(REPOSITORY_ROOT / CI_WORKFLOW).values(),
                   **PinnedVersions(REPOSITORY_ROOT / GITLEAKS_ACTION).values()}
        self.assertEqual(domain_ci, {name: core_ci.get(name) for name in domain_ci})


class PinnedVersions:
    def __init__(self, workflow: Path) -> None:
        self._workflow = workflow

    def values(self) -> dict[str, str]:
        return dict(PIN_PATTERN.findall(self._workflow.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
