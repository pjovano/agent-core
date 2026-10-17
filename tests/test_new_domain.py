from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _new_domain import BASIC_ANSWERS, CORE_BRANCH, DOMAIN_NAME, TEMPLATE_DIR, NewDomainRun, Outcome, PublishedCore

VAULT_CONFIG = Path(".obsidian") / "graph.json"
SHARED_FOLDER = "library"
NEW_FOLDER = "recipes"
DOMAIN_BRANCH = "new-domain"
TRAILER_KEYS = ("Change-class: ", "Defect-class: ")
VENDORED_CORE = "vendor/agent-core"
LATER_CORE_FILE = "later.md"
EXISTING_FILE = "README.md"


class Workspace:
    def __init__(self, case: type[unittest.TestCase]) -> None:
        directory = tempfile.TemporaryDirectory()
        case.addClassCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def run(self) -> NewDomainRun:
        return NewDomainRun(self.root, PublishedCore(self.root).published())


class ADomainMadeWithEveryDefault(unittest.TestCase):
    outcome: Outcome

    @classmethod
    def setUpClass(cls) -> None:
        cls.outcome = Workspace(cls).run().create(BASIC_ANSWERS)

    def test_the_command_succeeds(self) -> None:
        self.assertEqual(0, self.outcome.returncode, self.outcome.payload)

    def test_the_vault_names_the_domains_own_folder_listed_with_write_access(self) -> None:
        manifest = self.outcome.manifest()
        self.assertEqual((DOMAIN_NAME, [{"name": DOMAIN_NAME, "access": "write"}]),
                         (manifest["vault"], manifest["folders"]))

    def test_the_folder_step_makes_the_folder_a_vault_with_the_default_config(self) -> None:
        written = (self.outcome.documents / DOMAIN_NAME / VAULT_CONFIG).read_bytes()
        self.assertEqual((TEMPLATE_DIR / "obsidian" / "graph.json").read_bytes(), written)

    def test_an_unattended_run_is_read_only(self) -> None:
        self.assertEqual("read-only", self.outcome.manifest()["unattended"])

    def test_the_printed_settings_blocks_are_what_domain_py_settings_prints(self) -> None:
        completed = subprocess.run([sys.executable, "vendor/agent-core/domain.py", "settings"],
                                   cwd=self.outcome.domain, capture_output=True, text=True)
        self.assertEqual(json.loads(completed.stdout), self.outcome.payload["settings"])


class TheNewDomainsHistory(unittest.TestCase):
    outcome: Outcome
    run_in: NewDomainRun

    @classmethod
    def setUpClass(cls) -> None:
        cls.run_in = Workspace(cls).run()
        cls.outcome = cls.run_in.create(BASIC_ANSWERS, cloud=True)

    def test_the_domain_waits_on_its_own_branch(self) -> None:
        self.assertEqual((DOMAIN_BRANCH, DOMAIN_BRANCH),
                         (self.run_in.git("branch", "--show-current"), self.outcome.payload["branch"]))

    def test_main_holds_only_an_empty_root_commit(self) -> None:
        commits = self.run_in.git("rev-list", "main").split()
        self.assertEqual((1, ""), (len(commits), self.run_in.git("ls-tree", "main")))

    def test_every_commit_ends_with_a_change_class_or_defect_class_trailer(self) -> None:
        messages = self.run_in.git("log", "--format=%B%x00", DOMAIN_BRANCH).split("\0")
        last_lines = [message.strip().splitlines()[-1] for message in messages if message.strip()]
        self.assertEqual([], [line for line in last_lines if not line.startswith(TRAILER_KEYS)])


class TheVendoredCoreOfANewDomain(unittest.TestCase):
    def setUp(self) -> None:
        self.run_in = Workspace(type(self)).run()
        self.outcome = self.run_in.create(BASIC_ANSWERS, cloud=True)

    def test_a_later_subtree_pull_finds_it(self) -> None:
        self.run_in.core.add_file(LATER_CORE_FILE)
        self.run_in.git("subtree", "pull", "--prefix", VENDORED_CORE, str(self.run_in.core.directory), CORE_BRANCH,
                        "--squash", "--message", "Pull the core")
        self.assertTrue((self.outcome.domain / VENDORED_CORE / LATER_CORE_FILE).is_file())


class ADomainMadeInAnExistingRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.run_in = Workspace(type(self)).run()
        self.run_in.domain.mkdir()
        self.run_in.git("init", "--quiet", "--initial-branch", "main")

    def test_a_repository_with_commits_on_main_keeps_main_as_it_was(self) -> None:
        (self.run_in.domain / EXISTING_FILE).write_text("existing\n", encoding="utf-8")
        self.run_in.git("add", EXISTING_FILE)
        self.run_in.git("commit", "--quiet", "--message", "Start")
        before = self.run_in.git("rev-parse", "main")
        outcome = self.run_in.create(BASIC_ANSWERS, cloud=True)
        self.assertEqual((0, before), (outcome.returncode, self.run_in.git("rev-parse", "main")))

    def test_a_repository_with_commits_but_no_main_is_refused(self) -> None:
        self.run_in.git("switch", "--quiet", "--orphan", "trunk")
        self.run_in.git("commit", "--quiet", "--allow-empty", "--message", "Start")
        outcome = self.run_in.create(BASIC_ANSWERS, cloud=True)
        self.assertEqual((1, True), (outcome.returncode, "no branch main" in outcome.payload["error"]))


class ADomainThatDeclinesTheVault(unittest.TestCase):
    outcome: Outcome

    @classmethod
    def setUpClass(cls) -> None:
        cls.outcome = Workspace(cls).run().create({**BASIC_ANSWERS, "vault": False})

    def test_the_manifest_names_no_vault_no_folder_and_no_entry_skill(self) -> None:
        manifest = self.outcome.manifest()
        self.assertEqual((False, [], []), ("vault" in manifest, manifest["folders"], manifest["entry_skills"]))

    def test_the_folder_step_creates_no_folder(self) -> None:
        self.assertFalse(self.outcome.documents.exists())


class ADomainWithSensitiveData(unittest.TestCase):
    outcome: Outcome

    @classmethod
    def setUpClass(cls) -> None:
        answers = {**BASIC_ANSWERS, "sensitive": True, "folders": [{"name": SHARED_FOLDER, "access": "read"}]}
        cls.outcome = Workspace(cls).run().create(answers)

    def test_an_unattended_run_does_nothing(self) -> None:
        self.assertEqual("none", self.outcome.manifest()["unattended"])

    def test_the_policy_names_no_network_host(self) -> None:
        self.assertEqual([], self.outcome.manifest()["policy"].get("network_hosts", []))

    def test_every_folder_is_sensitive(self) -> None:
        self.assertEqual([True, True], [folder.get("sensitive") for folder in self.outcome.manifest()["folders"]])


class TheFolderStepOnThePrimary(unittest.TestCase):
    outcome: Outcome

    @classmethod
    def setUpClass(cls) -> None:
        run = Workspace(cls).run()
        cls.kept_file = run.home / "Documents" / SHARED_FOLDER / "kept.md"
        cls.kept_file.parent.mkdir(parents=True)
        cls.kept_file.write_text("kept\n", encoding="utf-8")
        folders = [{"name": SHARED_FOLDER, "access": "read"}, {"name": NEW_FOLDER, "access": "write"}]
        cls.outcome = run.create({**BASIC_ANSWERS, "folders": folders})

    def test_it_reuses_an_existing_folder_and_leaves_its_files(self) -> None:
        self.assertEqual("kept\n", self.kept_file.read_text(encoding="utf-8"))

    def test_it_creates_a_new_folder(self) -> None:
        self.assertTrue((self.outcome.documents / NEW_FOLDER).is_dir())

    def test_only_the_vault_receives_the_vault_config(self) -> None:
        configured = sorted(path.name for path in self.outcome.documents.iterdir() if (path / VAULT_CONFIG).exists())
        self.assertEqual([DOMAIN_NAME], configured)

    def test_the_manifest_lists_each_folder_with_the_access_given(self) -> None:
        access = {folder["name"]: folder["access"] for folder in self.outcome.manifest()["folders"]}
        self.assertEqual({DOMAIN_NAME: "write", SHARED_FOLDER: "read", NEW_FOLDER: "write"}, access)


class TheFolderStepInACloudSession(unittest.TestCase):
    outcome: Outcome

    @classmethod
    def setUpClass(cls) -> None:
        cls.run_in = Workspace(cls).run()
        cls.outcome = cls.run_in.create(BASIC_ANSWERS, cloud=True)

    def test_it_writes_the_manifest_with_the_vault(self) -> None:
        self.assertEqual(DOMAIN_NAME, self.outcome.manifest()["vault"])

    def test_it_creates_no_folder_and_says_why(self) -> None:
        self.assertEqual((False, []), (self.outcome.documents.exists(), self.outcome.payload["folders"]["created"]))
        self.assertIn("refused", self.outcome.payload["folders"])

    def test_the_folders_command_on_the_primary_creates_the_listed_vault(self) -> None:
        later = self.run_in.folders({"vault": False})
        self.assertEqual(0, later.returncode, later.payload)
        self.assertTrue((later.documents / DOMAIN_NAME / VAULT_CONFIG).is_file())


class TheFoldersCommandOnAnExistingDomain(unittest.TestCase):
    def setUp(self) -> None:
        self.run_in = Workspace(type(self)).run()

    def test_it_adds_the_default_vault_to_a_domain_that_declined_it(self) -> None:
        self.run_in.create({**BASIC_ANSWERS, "vault": False})
        outcome = self.run_in.folders({})
        self.assertEqual(DOMAIN_NAME, outcome.manifest()["vault"])
        self.assertIn(f"~/Documents/{DOMAIN_NAME}", outcome.payload["settings"]["sandbox"]["filesystem"]["allowWrite"])

    def test_it_refuses_a_second_vault(self) -> None:
        self.run_in.create(BASIC_ANSWERS)
        outcome = self.run_in.folders({})
        self.assertEqual((1, True), (outcome.returncode, "already names its vault" in outcome.payload["error"]))


class TheCommandRefusesBadInput(unittest.TestCase):
    def setUp(self) -> None:
        self.run_in = Workspace(type(self)).run()

    def test_a_directory_holding_files_outside_git_is_refused(self) -> None:
        self.run_in.domain.mkdir()
        (self.run_in.domain / "notes.md").write_text("notes\n", encoding="utf-8")
        outcome = self.run_in.create(BASIC_ANSWERS)
        self.assertEqual((1, True), (outcome.returncode, "is no git repository" in outcome.payload["error"]))

    def test_an_empty_vault_name_is_refused_naming_the_answers_file(self) -> None:
        outcome = self.run_in.create({**BASIC_ANSWERS, "vault": ""})
        self.assertEqual((1, True), (outcome.returncode, "answers.json" in outcome.payload["error"]))

    def test_a_vault_also_listed_among_the_other_folders_is_refused_before_anything_is_written(self) -> None:
        answers = {**BASIC_ANSWERS, "vault": SHARED_FOLDER, "folders": [{"name": SHARED_FOLDER, "access": "read"}]}
        outcome = self.run_in.create(answers)
        self.assertEqual((1, True, False, False), (outcome.returncode, "answers.json" in outcome.payload["error"],
                                                   outcome.domain.exists(), outcome.documents.exists()))


if __name__ == "__main__":
    unittest.main()
