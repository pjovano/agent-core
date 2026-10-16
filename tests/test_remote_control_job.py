from __future__ import annotations

import contextlib
import io
import json
import plistlib
import tempfile
import unittest
from pathlib import Path

from _core_path import CoreModulePath

CoreModulePath.activate()

from _host_fakes import FakeLaunchctl

from agent_core._adapters.host.launchd import Launchctl, LaunchdScheduler
from remote_control import LABEL, RemoteControlCli, RemoteControlJob

HAND_WRITTEN_LABEL = "local.claude-remote-control"
HAND_WRITTEN_BYTES = b"the hand-written plist, which the rollback reloads"
CLAUDE_DIRECTORY = "tools/claude/bin"
HOMEBREW_DIRECTORY = "homebrew/bin"
PROGRAMS = {"claude": f"{CLAUDE_DIRECTORY}/claude", "caffeinate": "system/caffeinate",
            "brew": f"{HOMEBREW_DIRECTORY}/brew"}
REFUSED_EXIT_CODE = 1


class RemoteControlCase(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.plist_directory = self.home / "Library" / "LaunchAgents"
        self.plist_directory.mkdir(parents=True)
        self.hand_written = self.plist_directory / f"{HAND_WRITTEN_LABEL}.plist"
        self.hand_written.write_bytes(HAND_WRITTEN_BYTES)
        self.launchctl = FakeLaunchctl(loaded=(HAND_WRITTEN_LABEL,))
        self.programs = dict(PROGRAMS)

    def job(self) -> RemoteControlJob:
        return RemoteControlJob(self.home, self.programs.get)

    def plist(self) -> dict:
        return plistlib.loads(LaunchdScheduler(self.plist_directory).definition(self.job().job()).encode())

    def run_cli(self, *argv: str) -> tuple[int, dict]:
        cli = RemoteControlCli(self.job(), LaunchdScheduler(self.plist_directory, Launchctl(self.launchctl.run)))
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = cli.run(list(argv))
        return code, json.loads(printed.getvalue())

    def own_plist(self) -> Path:
        return self.plist_directory / f"{LABEL}.plist"


class TestTheRemoteControlPlist(RemoteControlCase):
    def test_keeps_the_machine_awake_while_remote_control_spawns_in_the_same_directory(self) -> None:
        self.assertEqual([PROGRAMS["caffeinate"], "-i", PROGRAMS["claude"], "remote-control", "--spawn", "same-dir",
                          "--no-create-session-in-dir"], self.plist()["ProgramArguments"])

    def test_passes_no_session_name(self) -> None:
        self.assertNotIn("--name", self.plist()["ProgramArguments"])

    def test_takes_a_label_of_its_own(self) -> None:
        self.assertEqual(LABEL, self.plist()["Label"])
        self.assertNotEqual(HAND_WRITTEN_LABEL, LABEL)

    def test_is_kept_alive_from_load_and_restarted_after_thirty_seconds(self) -> None:
        plist = self.plist()
        self.assertEqual((True, True, 30), (plist["KeepAlive"], plist["RunAtLoad"], plist["ThrottleInterval"]))

    def test_works_in_the_dispatcher_checkout(self) -> None:
        self.assertEqual(str(self.home / "Developer" / "agent-core"), self.plist()["WorkingDirectory"])

    def test_its_path_reaches_claude_then_homebrew(self) -> None:
        directories = self.plist()["EnvironmentVariables"]["PATH"].split(":")
        self.assertEqual([CLAUDE_DIRECTORY, HOMEBREW_DIRECTORY], directories[:2])

    def test_logs_under_the_users_logs(self) -> None:
        plist = self.plist()
        log = Path(plist["StandardOutPath"])
        self.assertEqual((self.home / "Library" / "Logs", log), (log.parent, Path(plist["StandardErrorPath"])))

    def test_resolves_claude_where_it_is_installed_at_install_time(self) -> None:
        self.programs["claude"] = "elsewhere/claude"
        self.assertEqual("elsewhere/claude", self.plist()["ProgramArguments"][2])


class TestInstall(RemoteControlCase):
    def test_the_read_only_form_writes_and_loads_nothing(self) -> None:
        code, report = self.run_cli("install")
        self.assertEqual((0, True, False), (code, report["needed"], report["installed"]))
        self.assertEqual(set(), set(self.launchctl.verbs()) - {"print"})
        self.assertFalse(self.own_plist().exists())

    def test_the_read_only_form_prints_the_plist_it_would_write(self) -> None:
        _code, report = self.run_cli("install")
        self.assertEqual(LABEL, plistlib.loads(report["definition"].encode())["Label"])

    def test_apply_writes_and_loads_the_job(self) -> None:
        code, report = self.run_cli("install", "--apply")
        self.assertEqual((0, True), (code, report["installed"]))
        self.assertTrue(self.own_plist().exists())
        self.assertIn(LABEL, self.launchctl.loaded)

    def test_apply_refuses_while_claude_cannot_be_found(self) -> None:
        del self.programs["claude"]
        code, report = self.run_cli("install", "--apply")
        self.assertEqual((REFUSED_EXIT_CODE, ["claude"], False), (code, report["unresolved"], report["installed"]))
        self.assertFalse(self.own_plist().exists())


class TestStatus(RemoteControlCase):
    def test_reports_an_absent_job(self) -> None:
        self.assertFalse(self.run_cli("status")[1]["installed"])

    def test_reports_an_installed_job(self) -> None:
        self.run_cli("install", "--apply")
        self.assertTrue(self.run_cli("status")[1]["installed"])


class TestUninstall(RemoteControlCase):
    def setUp(self) -> None:
        super().setUp()
        self.run_cli("install", "--apply")

    def test_the_read_only_form_names_its_own_job_and_removes_nothing(self) -> None:
        code, report = self.run_cli("uninstall")
        self.assertEqual((0, LABEL, True, False), (code, report["label"], report["installed"], report["removed"]))
        self.assertTrue(self.own_plist().exists())
        self.assertIn(LABEL, self.launchctl.loaded)

    def test_apply_boots_out_the_job_and_deletes_its_plist(self) -> None:
        self.run_cli("uninstall", "--apply")
        self.assertFalse(self.own_plist().exists())
        self.assertNotIn(LABEL, self.launchctl.loaded)


class TestTheHandWrittenJob(RemoteControlCase):
    def setUp(self) -> None:
        super().setUp()
        for argv in (("install",), ("install", "--apply"), ("status",), ("uninstall",), ("uninstall", "--apply")):
            self.run_cli(*argv)

    def test_its_plist_is_never_rewritten_or_removed(self) -> None:
        self.assertEqual(HAND_WRITTEN_BYTES, self.hand_written.read_bytes())

    def test_launchd_is_never_asked_about_it(self) -> None:
        self.assertEqual([], [argument for argument in self.launchctl.addressed() if HAND_WRITTEN_LABEL in argument])
        self.assertIn(HAND_WRITTEN_LABEL, self.launchctl.loaded)


class TestTheCommandLine(RemoteControlCase):
    def test_no_command_prints_the_usage(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            code = RemoteControlCli(self.job(), LaunchdScheduler(self.plist_directory)).run([])
        self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
