from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

from _core_path import CoreModulePath

CoreModulePath.activate()

from _host_fakes import FakeLaunchctl

from agent_core._adapters.host.launchd import Launchctl, LaunchdPlist, LaunchdRefusal, LaunchdScheduler
from agent_core._ports.host import Job

LABEL = "local.example.watcher"
COMMAND = ("python", "watch.py", "sample")
BARE_JOB = Job(LABEL, COMMAND)


def keys(job: Job) -> dict:
    return plistlib.loads(LaunchdPlist(job).contents())


class TestThePlistOfAJob(unittest.TestCase):
    def test_a_bare_job_carries_its_label_and_command_alone(self) -> None:
        self.assertEqual({"Label": LABEL, "ProgramArguments": list(COMMAND)}, keys(BARE_JOB))

    def test_a_periodic_job_starts_at_its_interval(self) -> None:
        self.assertEqual(60, keys(Job(LABEL, COMMAND, interval_seconds=60))["StartInterval"])

    def test_a_kept_alive_job_restarts_after_its_throttle(self) -> None:
        plist = keys(Job(LABEL, COMMAND, keep_alive=True, run_at_load=True, restart_throttle_seconds=30))
        self.assertEqual((True, True, 30), (plist["KeepAlive"], plist["RunAtLoad"], plist["ThrottleInterval"]))

    def test_a_job_runs_in_its_directory_with_its_environment(self) -> None:
        plist = keys(Job(LABEL, COMMAND, working_directory=Path("work"), environment=(("PATH", "bin"),)))
        self.assertEqual(("work", {"PATH": "bin"}), (plist["WorkingDirectory"], plist["EnvironmentVariables"]))

    def test_a_background_job_runs_at_low_priority(self) -> None:
        plist = keys(Job(LABEL, COMMAND, background=True))
        self.assertEqual(("Background", True, 10), (plist["ProcessType"], plist["LowPriorityIO"], plist["Nice"]))

    def test_a_logged_job_writes_both_streams_to_its_log(self) -> None:
        plist = keys(Job(LABEL, COMMAND, log=Path("logs") / "job.log"))
        self.assertEqual(("logs/job.log", "logs/job.log"), (plist["StandardOutPath"], plist["StandardErrorPath"]))


class SchedulerCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.plist_directory = directory / "LaunchAgents"
        self.job = Job(LABEL, COMMAND, interval_seconds=60, log=directory / "logs" / "job.log")
        self.plist = self.plist_directory / f"{LABEL}.plist"

    def scheduler(self, launchctl: FakeLaunchctl) -> LaunchdScheduler:
        return LaunchdScheduler(self.plist_directory, Launchctl(launchctl.run))

    def write_current_plist(self) -> None:
        self.plist_directory.mkdir(parents=True)
        self.plist.write_bytes(LaunchdPlist(self.job).contents())


class TestAnInstalledJob(SchedulerCase):
    def test_reads_as_installed(self) -> None:
        self.write_current_plist()
        self.assertTrue(self.scheduler(FakeLaunchctl(loaded=(LABEL,))).installed(self.job))

    def test_installing_it_again_only_asks_launchd(self) -> None:
        self.write_current_plist()
        launchctl = FakeLaunchctl(loaded=(LABEL,))
        self.scheduler(launchctl).install(self.job)
        self.assertEqual(["print"], launchctl.verbs())


class TestAStaleJob(SchedulerCase):
    def setUp(self) -> None:
        super().setUp()
        self.plist_directory.mkdir(parents=True)
        self.plist.write_bytes(b"stale")

    def test_reads_as_not_installed_though_loaded(self) -> None:
        self.assertFalse(self.scheduler(FakeLaunchctl(loaded=(LABEL,))).installed(self.job))

    def test_installing_rewrites_and_reloads_it(self) -> None:
        launchctl = FakeLaunchctl(loaded=(LABEL,))
        scheduler = self.scheduler(launchctl)
        scheduler.install(self.job)
        self.assertEqual(["bootout", "print", "bootstrap"], launchctl.verbs())
        self.assertTrue(scheduler.installed(self.job))


class TestAWrittenJobLaunchdHasNotLoaded(SchedulerCase):
    def test_reads_as_not_installed(self) -> None:
        self.write_current_plist()
        self.assertFalse(self.scheduler(FakeLaunchctl()).installed(self.job))

    def test_installing_loads_it_without_rewriting_it(self) -> None:
        self.write_current_plist()
        launchctl = FakeLaunchctl()
        self.scheduler(launchctl).install(self.job)
        self.assertEqual(["print", "bootstrap"], launchctl.verbs())


class TestANewJob(SchedulerCase):
    def test_installing_writes_its_plist_and_log_directory_and_loads_it(self) -> None:
        launchctl = FakeLaunchctl()
        self.scheduler(launchctl).install(self.job)
        self.assertEqual(LaunchdPlist(self.job).contents(), self.plist.read_bytes())
        self.assertTrue(self.job.log.parent.is_dir())
        self.assertIn(LABEL, launchctl.loaded)

    def test_a_refused_bootstrap_raises_naming_the_plist(self) -> None:
        with self.assertRaisesRegex(LaunchdRefusal, f"{LABEL}.plist failed: refused"):
            self.scheduler(FakeLaunchctl(bootstrap_refused=True)).install(self.job)


class TestRemovingAJob(SchedulerCase):
    def test_a_loaded_job_is_booted_out_and_its_plist_deleted(self) -> None:
        self.write_current_plist()
        launchctl = FakeLaunchctl(loaded=(LABEL,))
        self.scheduler(launchctl).remove(self.job)
        self.assertEqual((["bootout"], set(), False), (launchctl.verbs(), launchctl.loaded, self.plist.exists()))

    def test_an_absent_job_is_removed_without_error_or_trace(self) -> None:
        self.scheduler(FakeLaunchctl()).remove(self.job)
        self.assertFalse(self.plist_directory.exists())

    def test_another_jobs_plist_is_left_alone(self) -> None:
        self.write_current_plist()
        other = self.plist_directory / "local.example.other.plist"
        other.write_bytes(b"other")
        self.scheduler(FakeLaunchctl(loaded=(LABEL,))).remove(self.job)
        self.assertEqual(b"other", other.read_bytes())


class TestTheReadOnlyForms(SchedulerCase):
    def test_the_definition_is_the_plist_and_writes_nothing(self) -> None:
        definition = self.scheduler(FakeLaunchctl()).definition(self.job)
        self.assertEqual(LaunchdPlist(self.job).contents().decode(), definition)
        self.assertFalse(self.plist_directory.exists())

    def test_the_manual_install_bootstraps_the_plist_by_hand(self) -> None:
        manual = self.scheduler(FakeLaunchctl()).manual_install(self.job)
        self.assertEqual(f"launchctl bootstrap gui/$(id -u) '{self.plist}'", manual)


if __name__ == "__main__":
    unittest.main()
