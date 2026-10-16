from __future__ import annotations

import subprocess
from collections.abc import Callable

from agent_core._ports.host import Notice, NoticeHeading

REMINDER_LEAD_SECONDS = 60
OSASCRIPT_TIMEOUT_SECONDS = 30
DISPLAY_SCRIPT = ("on run arguments", "display notification (item 1 of arguments) with title (item 2 of arguments)",
                  "end run")
REMINDER_SCRIPT = (
    "on run arguments",
    "set listName to item 2 of arguments",
    'tell application "Reminders"',
    "if not (exists list listName) then make new list with properties {name:listName}",
    "tell list listName to make new reminder with properties "
    "{name:(item 1 of arguments), remind me date:((current date) + (item 3 of arguments as integer))}",
    "end tell",
    "end run",
)

Runner = Callable[[list[str]], object]


def run_osascript(command: list[str]) -> object:
    return subprocess.run(command, capture_output=True, timeout=OSASCRIPT_TIMEOUT_SECONDS)


class AppleScript:
    def __init__(self, lines: tuple[str, ...], run: Runner = run_osascript) -> None:
        self._lines = lines
        self._run = run

    def run(self, *arguments: str) -> None:
        try:
            self._run(self._command(*arguments))
        except (OSError, subprocess.SubprocessError):
            return

    def _command(self, *arguments: str) -> list[str]:
        script = [part for line in self._lines for part in ("-e", line)]
        return ["osascript", *script, *arguments]


class DesktopNotifier:
    def __init__(self, heading: NoticeHeading, run: Runner = run_osascript) -> None:
        self._heading = heading
        self._script = AppleScript(DISPLAY_SCRIPT, run)

    def notify(self, alert: Notice) -> None:
        self._script.run(alert.message, self._heading.title)


class RemindersNotifier:
    def __init__(self, heading: NoticeHeading, run: Runner = run_osascript) -> None:
        self._heading = heading
        self._script = AppleScript(REMINDER_SCRIPT, run)

    def notify(self, alert: Notice) -> None:
        self._script.run(alert.message, self._heading.reminder_list, str(REMINDER_LEAD_SECONDS))
