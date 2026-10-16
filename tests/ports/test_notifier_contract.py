from __future__ import annotations

import unittest

from _core_path import CoreModulePath

CoreModulePath.activate()

from _host_fakes import FakeNotice, RecordingNotifier, RecordingRunner

from agent_core._adapters.host.macos_notifiers import DesktopNotifier, RemindersNotifier
from agent_core._ports.host import NoticeHeading, Notifier

ALERT = FakeNotice("Memory pressure is critical")
HEADING = NoticeHeading("Example machine health", "Example list")


class NotifierContract:
    def notifier(self) -> Notifier:
        raise NotImplementedError

    def test_an_alert_is_accepted_without_an_answer(self) -> None:
        self.assertIsNone(self.notifier().notify(ALERT))

    def test_the_same_alert_is_accepted_again(self) -> None:
        notifier = self.notifier()
        notifier.notify(ALERT)
        self.assertIsNone(notifier.notify(ALERT))


class TestRecordingNotifierKeepsTheContract(NotifierContract, unittest.TestCase):
    def notifier(self) -> Notifier:
        return RecordingNotifier()


class TestTheDesktopNotifierKeepsTheContract(NotifierContract, unittest.TestCase):
    def notifier(self) -> Notifier:
        return DesktopNotifier(HEADING, RecordingRunner())


class TestTheRemindersNotifierKeepsTheContract(NotifierContract, unittest.TestCase):
    def notifier(self) -> Notifier:
        return RemindersNotifier(HEADING, RecordingRunner())


class TestANotifierWhoseScriptCannotRunKeepsTheContract(NotifierContract, unittest.TestCase):
    def notifier(self) -> Notifier:
        return RemindersNotifier(HEADING, RecordingRunner(OSError("no osascript")))


if __name__ == "__main__":
    unittest.main()
