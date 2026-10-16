from __future__ import annotations

import subprocess
import sys
import unittest
from dataclasses import dataclass

from _repository import REPOSITORY_ROOT

REMEMBER_DIR = REPOSITORY_ROOT / "core" / "skills" / "remember"
CHECK_SCRIPT = REMEMBER_DIR / "scripts" / "check_user_file.py"
SKELETON = REMEMBER_DIR / "skeleton.md"
FIXTURES_DIR = REPOSITORY_ROOT / "tests" / "fixtures" / "remember"
EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
BOUNDARY_SENTENCE = "An item that would still hold for another person using the domain is a rule"
SECTION_HEADINGS = ["## Standing", "## Recent"]


@dataclass(frozen=True)
class CheckRun:
    exit_code: int
    output: str


class UserFileCheck:
    def run(self, *arguments: str) -> CheckRun:
        completed = subprocess.run([sys.executable, str(CHECK_SCRIPT), *arguments], capture_output=True, text=True)
        return CheckRun(completed.returncode, completed.stdout + completed.stderr)

    def of_fixture(self, name: str) -> CheckRun:
        return self.run(str(FIXTURES_DIR / name))


class TheCheckPassesAWellFormedUserFile(unittest.TestCase):
    def test_a_file_with_dated_recent_entries_passes(self) -> None:
        self.assertEqual(EXIT_PASSED, UserFileCheck().of_fixture("well-formed.md").exit_code)

    def test_a_file_of_exactly_one_hundred_fifty_lines_passes(self) -> None:
        self.assertEqual(EXIT_PASSED, UserFileCheck().of_fixture("at-cap.md").exit_code)

    def test_the_skeleton_passes(self) -> None:
        self.assertEqual(EXIT_PASSED, UserFileCheck().run(str(SKELETON)).exit_code)


class TheCheckFailsAUserFilePastItsCap(unittest.TestCase):
    def test_a_file_of_more_than_one_hundred_fifty_lines_fails(self) -> None:
        run = UserFileCheck().of_fixture("past-cap.md")
        self.assertEqual(EXIT_FAILED, run.exit_code)
        self.assertIn("past its cap of 150", run.output)


class TheCheckFailsAnUndatedRecentEntry(unittest.TestCase):
    def test_a_recent_entry_that_opens_with_no_date_fails(self) -> None:
        run = UserFileCheck().of_fixture("undated-recent.md")
        self.assertEqual(EXIT_FAILED, run.exit_code)
        self.assertIn("undated-recent.md:16: the recent entry does not open with a date", run.output)


class TheCheckRefusesAMissingOrUnnamedFile(unittest.TestCase):
    def test_a_missing_file_fails(self) -> None:
        self.assertEqual(EXIT_FAILED, UserFileCheck().of_fixture("absent.md").exit_code)

    def test_no_argument_is_a_usage_error(self) -> None:
        self.assertEqual(EXIT_USAGE, UserFileCheck().run().exit_code)


class TheSkeletonOpensWithTheSortingTest(unittest.TestCase):
    def test_the_skeleton_states_the_sorting_test_before_its_first_section(self) -> None:
        text = SKELETON.read_text(encoding="utf-8")
        opening = text.split(SECTION_HEADINGS[0], 1)[0]
        self.assertIn(BOUNDARY_SENTENCE, " ".join(opening.split()))

    def test_the_skeleton_holds_the_standing_and_recent_sections_in_order(self) -> None:
        lines = SKELETON.read_text(encoding="utf-8").splitlines()
        self.assertEqual(SECTION_HEADINGS, [line for line in lines if line.startswith("## ")])


if __name__ == "__main__":
    unittest.main()
