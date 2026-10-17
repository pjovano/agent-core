from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _domain_manifests import (
    DEVELOPER_FIXTURE,
    LEDGER_MANIFEST,
    MINIMAL_MANIFEST,
    RESEARCH_MANIFEST,
    DomainScript,
    ManifestDraft,
)

from agent_core._domain.fields import ManifestError
from agent_core._domain.manifest import DomainManifest
from agent_core._domain.shelf import ManifestShelf

WRITE_FOLDER = {"name": "notes", "access": "write"}
READ_FOLDER = {"name": "notes", "access": "read"}


class TheReaderFindsTheManifests(unittest.TestCase):
    def test_it_reads_every_manifest_one_level_under_the_developer_root(self) -> None:
        names = [manifest.name for manifest in ManifestShelf([], DEVELOPER_FIXTURE).manifests()]
        self.assertEqual(["ledger", "personal", "research"], names)

    def test_it_reads_only_the_named_manifests_when_some_are_named(self) -> None:
        manifests = ManifestShelf([LEDGER_MANIFEST], DEVELOPER_FIXTURE).manifests()
        self.assertEqual(["ledger"], [manifest.name for manifest in manifests])

    def test_an_absent_developer_root_holds_no_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual([], ManifestShelf([], Path(empty) / "Developer").manifests())

    def test_it_reads_each_folder_with_its_access_and_sensitivity(self) -> None:
        folders = {folder.name: (folder.access, folder.sensitive) for folder in
                   DomainManifest.read(LEDGER_MANIFEST).folders}
        self.assertEqual({"taxes": ("read", True), "library": ("read", True)}, folders)

    def test_it_reads_each_section_of_the_policy(self) -> None:
        policy = DomainManifest.read(RESEARCH_MANIFEST).policy
        self.assertEqual(({"--replace": "rewrites a corpus file's body"}, ("gh *", "git push *"), True),
                         (policy.prompt_on, policy.excluded_commands, policy.allow_local_binding))


class TheReaderRefusesAMalformedManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.draft = ManifestDraft(Path(self.enterContext(tempfile.TemporaryDirectory())))

    def assert_refused(self, path: Path) -> None:
        with self.assertRaises(ManifestError) as refusal:
            DomainManifest.read(path)
        self.assertIn(str(path), str(refusal.exception))

    def test_a_file_that_is_not_json_is_refused(self) -> None:
        path = self.draft.written({})
        path.write_text("{not json", encoding="utf-8")
        self.assert_refused(path)

    def test_a_manifest_without_a_name_is_refused(self) -> None:
        self.assert_refused(self.draft.written({"summary": "Holds nothing."}))

    def test_an_access_other_than_read_or_write_is_refused(self) -> None:
        self.assert_refused(self.draft.with_folders({"name": "notes", "access": "admin"}))

    def test_an_unknown_folder_key_is_refused_so_a_misspelt_sensitive_never_drops_the_guard(self) -> None:
        self.assert_refused(self.draft.with_folders({**READ_FOLDER, "sensative": True}))

    def test_a_folder_listed_twice_is_refused(self) -> None:
        self.assert_refused(self.draft.with_folders(WRITE_FOLDER, READ_FOLDER))

    def test_a_folder_name_holding_a_slash_is_refused(self) -> None:
        self.assert_refused(self.draft.with_folders({"name": "notes/private", "access": "read"}))

    def test_write_within_on_a_read_folder_is_refused(self) -> None:
        self.assert_refused(self.draft.with_folders({**READ_FOLDER, "write_within": ["drafts"]}))

    def test_write_within_that_leaves_the_folder_is_refused(self) -> None:
        self.assert_refused(self.draft.with_folders({**WRITE_FOLDER, "write_within": ["../taxes"]}))

    def test_an_unknown_policy_key_is_refused(self) -> None:
        self.assert_refused(self.draft.with_policy({"allowed": ["Bash(ls)"]}))

    def test_a_write_path_inside_documents_is_refused_because_folders_grants_those(self) -> None:
        self.assert_refused(self.draft.with_policy({"write_paths": ["~/Documents/taxes"]}))

    def test_a_write_path_not_under_the_home_directory_is_refused(self) -> None:
        self.assert_refused(self.draft.with_policy({"write_paths": ["Desktop/inbox"]}))

    def test_a_policy_rule_naming_a_machine_path_is_refused(self) -> None:
        self.assert_refused(self.draft.with_policy({"allow": ["Read(/Users/someone/**)"]}))

    def test_an_edit_rule_in_a_folder_not_listed_as_write_is_refused(self) -> None:
        self.assert_refused(self.draft.with_policy({"allow": ["Edit(~/Documents/notes/**)"]}, READ_FOLDER))

    def test_an_edit_rule_in_a_write_folder_is_read(self) -> None:
        path = self.draft.with_policy({"allow": ["Edit(~/Documents/notes/**)"]}, WRITE_FOLDER)
        self.assertEqual(("Edit(~/Documents/notes/**)",), DomainManifest.read(path).policy.allow)


class TheReaderReadsTheVault(unittest.TestCase):
    def setUp(self) -> None:
        self.draft = ManifestDraft(Path(self.enterContext(tempfile.TemporaryDirectory())))

    def assert_refused(self, path: Path) -> None:
        with self.assertRaises(ManifestError) as refusal:
            DomainManifest.read(path)
        self.assertIn(str(path), str(refusal.exception))

    def test_a_manifest_without_a_vault_reads_as_having_none(self) -> None:
        self.assertIsNone(DomainManifest.read(self.draft.with_folders(WRITE_FOLDER)).vault)

    def test_a_vault_naming_a_write_folder_is_read(self) -> None:
        path = self.draft.written({**MINIMAL_MANIFEST, "folders": [WRITE_FOLDER], "vault": "notes"})
        self.assertEqual("notes", DomainManifest.read(path).vault)

    def test_a_vault_naming_a_read_folder_is_refused(self) -> None:
        self.assert_refused(self.draft.written({**MINIMAL_MANIFEST, "folders": [READ_FOLDER], "vault": "notes"}))

    def test_a_vault_naming_a_folder_the_manifest_does_not_list_is_refused(self) -> None:
        self.assert_refused(self.draft.written({**MINIMAL_MANIFEST, "folders": [WRITE_FOLDER], "vault": "taxes"}))

    def test_a_vault_that_is_not_a_non_empty_string_is_refused(self) -> None:
        for malformed in (["notes"], True, "", None):
            with self.subTest(vault=malformed):
                self.assert_refused(self.draft.written({**MINIMAL_MANIFEST, "folders": [WRITE_FOLDER],
                                                        "vault": malformed}))


class TheManifestsCommand(unittest.TestCase):
    def test_it_prints_every_manifest_under_the_developer_root(self) -> None:
        completed = DomainScript.run("manifests", "--developer", str(DEVELOPER_FIXTURE))
        listed = [manifest["name"] for manifest in json.loads(completed.stdout)]
        self.assertEqual(["ledger", "personal", "research"], listed, completed.stderr)

    def test_it_lists_each_domains_vault_or_none(self) -> None:
        completed = DomainScript.run("manifests", "--developer", str(DEVELOPER_FIXTURE))
        vaults = {manifest["name"]: manifest["vault"] for manifest in json.loads(completed.stdout)}
        self.assertEqual({"ledger": None, "personal": None, "research": "research vault"}, vaults, completed.stderr)

    def test_a_malformed_manifest_fails_the_command_naming_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = ManifestDraft(Path(directory)).with_folders({"name": "notes", "access": "admin"})
            completed = DomainScript.run("manifests", str(path))
        self.assertEqual((1, True), (completed.returncode, str(path) in json.loads(completed.stdout)["error"]))


if __name__ == "__main__":
    unittest.main()
