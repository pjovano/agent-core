from __future__ import annotations

import unittest

from _core_path import CoreModulePath

CoreModulePath.activate()

from _host_fakes import FakeNotice, RecordingRunner

from agent_core._adapters.host.macos_notifiers import DesktopNotifier, RemindersNotifier
from agent_core._ports.host import NoticeHeading

ALERT = FakeNotice("memory pressure critical, 300 MB available")
HEADING = NoticeHeading("Example machine health", "Example list")
SCRIPT_FLAG = "-e"


def osascript_command(notifier_class) -> list[str]:
    runner = RecordingRunner()
    notifier_class(HEADING, runner).notify(ALERT)
    return runner.commands[0]


def script_arguments(command: list[str]) -> list[str]:
    last_script_line = max(index for index, part in enumerate(command) if part == SCRIPT_FLAG) + 1
    return command[last_script_line + 1:]


class TestTheRemindersNotifier(unittest.TestCase):
    def test_files_the_alert_in_the_list_its_heading_names_due_in_a_minute(self) -> None:
        self.assertEqual([ALERT.message, "Example list", "60"], script_arguments(osascript_command(RemindersNotifier)))

    def test_tells_the_reminders_app(self) -> None:
        self.assertIn('tell application "Reminders"', osascript_command(RemindersNotifier))


class TestTheDesktopNotifier(unittest.TestCase):
    def test_displays_the_alert_under_the_title_its_heading_names(self) -> None:
        self.assertEqual([ALERT.message, "Example machine health"], script_arguments(osascript_command(DesktopNotifier)))


if __name__ == "__main__":
    unittest.main()
