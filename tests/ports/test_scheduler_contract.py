from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _core_path import CoreModulePath

CoreModulePath.activate()

from _host_fakes import FakeLaunchctl, FakeScheduler

from agent_core._adapters.host.launchd import Launchctl, LaunchdScheduler
from agent_core._ports.host import Job, Scheduler

JOB = Job("local.example.sample", ("true",), interval_seconds=60)


class SchedulerContract:
    def scheduler(self) -> Scheduler:
        raise NotImplementedError

    def test_an_installed_job_reads_as_installed(self) -> None:
        scheduler = self.scheduler()
        scheduler.install(JOB)
        self.assertTrue(scheduler.installed(JOB))

    def test_a_job_never_installed_reads_as_not_installed(self) -> None:
        self.assertFalse(self.scheduler().installed(JOB))

    def test_a_removed_job_reads_as_not_installed(self) -> None:
        scheduler = self.scheduler()
        scheduler.install(JOB)
        scheduler.remove(JOB)
        self.assertFalse(scheduler.installed(JOB))

    def test_installing_twice_leaves_one_job_that_one_removal_removes(self) -> None:
        scheduler = self.scheduler()
        scheduler.install(JOB)
        scheduler.install(JOB)
        scheduler.remove(JOB)
        self.assertFalse(scheduler.installed(JOB))

    def test_removing_a_job_never_installed_is_harmless(self) -> None:
        scheduler = self.scheduler()
        scheduler.remove(JOB)
        self.assertFalse(scheduler.installed(JOB))

    def test_a_jobs_location_definition_and_manual_install_name_its_label(self) -> None:
        scheduler = self.scheduler()
        self.assertIn(JOB.label, scheduler.location(JOB))
        self.assertIn(JOB.label, scheduler.definition(JOB))
        self.assertIn(JOB.label, scheduler.manual_install(JOB))

    def test_reading_a_definition_installs_nothing(self) -> None:
        scheduler = self.scheduler()
        scheduler.location(JOB)
        scheduler.definition(JOB)
        scheduler.manual_install(JOB)
        self.assertFalse(scheduler.installed(JOB))


class TestFakeSchedulerKeepsTheContract(SchedulerContract, unittest.TestCase):
    def scheduler(self) -> Scheduler:
        return FakeScheduler()


class TestTheLaunchdSchedulerKeepsTheContract(SchedulerContract, unittest.TestCase):
    def scheduler(self) -> Scheduler:
        plist_directory = Path(self.enterContext(tempfile.TemporaryDirectory())) / "LaunchAgents"
        return LaunchdScheduler(plist_directory, Launchctl(FakeLaunchctl().run))


if __name__ == "__main__":
    unittest.main()
