from __future__ import annotations

import unittest

from _audit_files import TemporaryFiles

from agent_core._audit.measures import (
    MEASURE_ARGUMENTS,
    MEASURE_COMMENT,
    MEASURE_DOCSTRING,
    MEASURE_LONG_FUNCTION,
    CodeMeasures,
)

LONG_FUNCTION = "def counted():\n" + "".join(f"    step_{number} = {number}\n" for number in range(25))
FOUR_ARGUMENTS = "def joined(first, second, third, fourth):\n    return first\n"
COMMENTED = "# a note to the reader\nvalue = 1\n"
DOCUMENTED = "class Work:\n    def run(self):\n        \"\"\"Run it.\"\"\"\n        return 1\n"
CLEAN = "class Work:\n    def run(self):\n        return 1\n"


class TestCodeMeasures(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)

    def _measures(self, name: str, source: str) -> list[str]:
        findings = CodeMeasures([self.files.written(name, source)], self.files.root).findings()
        return [finding["measure"] for finding in findings]

    def test_a_function_over_twenty_lines_is_measured(self) -> None:
        self.assertIn(MEASURE_LONG_FUNCTION, self._measures("long.py", LONG_FUNCTION))

    def test_a_function_with_four_arguments_is_measured(self) -> None:
        self.assertIn(MEASURE_ARGUMENTS, self._measures("arguments.py", FOUR_ARGUMENTS))

    def test_a_comment_is_measured(self) -> None:
        self.assertIn(MEASURE_COMMENT, self._measures("commented.py", COMMENTED))

    def test_a_docstring_is_measured(self) -> None:
        self.assertIn(MEASURE_DOCSTRING, self._measures("documented.py", DOCUMENTED))

    def test_code_that_meets_the_standard_measures_nothing(self) -> None:
        self.assertEqual([], self._measures("clean.py", CLEAN))

    def test_a_finding_is_labelled_by_its_path_under_the_root(self) -> None:
        findings = CodeMeasures([self.files.written("lib/commented.py", COMMENTED)], self.files.root).findings()
        self.assertEqual(["lib/commented.py"], [finding["file"] for finding in findings])


if __name__ == "__main__":
    unittest.main()
