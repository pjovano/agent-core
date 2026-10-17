from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _domain_manifests import (
    DEVELOPER_FIXTURE,
    LEDGER_MANIFEST,
    PERSONAL_MANIFEST,
    RESEARCH_MANIFEST,
    DomainScript,
    ManifestDraft,
)

from agent_core._domain.manifest import DomainManifest
from agent_core._domain.settings import SettingsBlocks

DOCUMENTS_PREFIX = "~/Documents/"
GUARDED_FOLDERS = ["~/Documents/medical", "~/Documents/taxes"]


class ResearchSettings:
    def __init__(self, *neighbours: Path) -> None:
        neighbour_manifests = [DomainManifest.read(path) for path in neighbours]
        self._blocks = SettingsBlocks(DomainManifest.read(RESEARCH_MANIFEST), neighbour_manifests).as_dict()

    @property
    def blocks(self) -> dict:
        return self._blocks

    @property
    def permissions(self) -> dict:
        return self._blocks["permissions"]

    @property
    def sandbox(self) -> dict:
        return self._blocks["sandbox"]

    def denied_reads(self) -> list[str]:
        return self.sandbox["filesystem"].get("denyRead", [])

    def denied_read_rules(self) -> list[str]:
        return self.permissions.get("deny", [])

    def documents_writes(self) -> list[str]:
        return [path for path in self.sandbox["filesystem"]["allowWrite"] if path.startswith(DOCUMENTS_PREFIX)]

    def strings(self) -> list[str]:
        return StringLeaves(self._blocks).all()


class StringLeaves:
    def __init__(self, value: object) -> None:
        self._value = value

    def all(self) -> list[str]:
        if isinstance(self._value, str):
            return [self._value]
        return [leaf for child in self._children() for leaf in StringLeaves(child).all()]

    def _children(self) -> list:
        if isinstance(self._value, dict):
            return list(self._value.values())
        return self._value if isinstance(self._value, list) else []


class TheGeneratorGrantsWritesToTheWriteFoldersAlone(unittest.TestCase):
    def test_sandbox_writes_in_documents_are_the_write_folders_narrowed_by_write_within(self) -> None:
        expected = ["~/Documents/library", "~/Documents/research vault/corpus", "~/Documents/research vault/writing"]
        self.assertEqual(expected, ResearchSettings().documents_writes())

    def test_a_read_folder_gains_no_sandbox_write(self) -> None:
        self.assertFalse(any("recipes" in path for path in ResearchSettings().documents_writes()))

    def test_the_policy_write_paths_follow_the_folders(self) -> None:
        allowed = ResearchSettings().sandbox["filesystem"]["allowWrite"]
        self.assertEqual(["~/Desktop/inbox", "~/.cache/torch"], allowed[-2:])

    def test_the_sandbox_is_always_enabled(self) -> None:
        self.assertIs(True, ResearchSettings().sandbox["enabled"])


class TheGeneratorGuardsEverySensitiveFolderOfAnotherManifest(unittest.TestCase):
    def test_each_guarded_folder_gets_a_sandbox_read_denial(self) -> None:
        settings = ResearchSettings(PERSONAL_MANIFEST, LEDGER_MANIFEST)
        self.assertEqual(GUARDED_FOLDERS, settings.denied_reads())

    def test_each_guarded_folder_gets_a_read_rule_in_the_permission_denials(self) -> None:
        settings = ResearchSettings(PERSONAL_MANIFEST, LEDGER_MANIFEST)
        self.assertEqual([f"Read({path}/**)" for path in GUARDED_FOLDERS], settings.denied_read_rules())

    def test_a_sensitive_folder_the_domain_lists_itself_stays_readable(self) -> None:
        settings = ResearchSettings(LEDGER_MANIFEST)
        self.assertNotIn("~/Documents/library", settings.denied_reads())

    def test_a_folder_no_manifest_marks_sensitive_stays_readable(self) -> None:
        settings = ResearchSettings(PERSONAL_MANIFEST)
        self.assertFalse(any("recipes" in path for path in settings.denied_reads() + settings.denied_read_rules()))

    def test_the_domain_own_manifest_among_the_neighbours_adds_no_denial(self) -> None:
        settings = ResearchSettings(RESEARCH_MANIFEST)
        self.assertEqual(([], []), (settings.denied_reads(), settings.denied_read_rules()))

    def test_without_a_guarded_folder_no_empty_denial_list_is_written(self) -> None:
        settings = ResearchSettings()
        self.assertEqual((False, False), ("deny" in settings.permissions, "denyRead" in settings.sandbox["filesystem"]))


class TheGeneratorCopiesThePolicy(unittest.TestCase):
    def test_the_allow_rules_become_the_permission_allowances(self) -> None:
        self.assertEqual(list(DomainManifest.read(RESEARCH_MANIFEST).policy.allow),
                         ResearchSettings().permissions["allow"])

    def test_the_network_hosts_and_local_binding_become_the_sandbox_network(self) -> None:
        self.assertEqual({"allowedDomains": ["localhost", "api.crossref.org"], "allowLocalBinding": True},
                         ResearchSettings().sandbox["network"])

    def test_the_excluded_commands_become_the_sandbox_exclusions(self) -> None:
        self.assertEqual(["gh *", "git push *"], ResearchSettings().sandbox["excludedCommands"])

    def test_the_prompt_on_patterns_stay_with_the_hook_that_reads_them(self) -> None:
        self.assertFalse(any("--replace" in leaf for leaf in ResearchSettings().strings()))

    def test_no_generated_string_names_a_path_beginning_with_a_slash(self) -> None:
        settings = ResearchSettings(PERSONAL_MANIFEST, LEDGER_MANIFEST)
        self.assertEqual([], [leaf for leaf in settings.strings() if leaf.startswith("/") or "(/" in leaf])

    def test_a_manifest_without_policy_or_folders_gets_an_enabled_sandbox_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = DomainManifest.read(ManifestDraft(Path(directory)).with_folders())
        self.assertEqual({"permissions": {}, "sandbox": {"enabled": True}}, SettingsBlocks(manifest, []).as_dict())


class TheSettingsCommand(unittest.TestCase):
    def test_it_prints_the_blocks_over_every_manifest_under_the_developer_root(self) -> None:
        completed = DomainScript.run("settings", "--domain", str(RESEARCH_MANIFEST), "--developer",
                                     str(DEVELOPER_FIXTURE))
        expected = ResearchSettings(PERSONAL_MANIFEST, LEDGER_MANIFEST).blocks
        self.assertEqual(expected, json.loads(completed.stdout), completed.stderr)


if __name__ == "__main__":
    unittest.main()
