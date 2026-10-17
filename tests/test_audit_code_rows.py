from __future__ import annotations

import tomllib
import unittest
from unittest import mock

from _audit_files import AuditRun, TemporaryFiles
from _repository import REPOSITORY_ROOT

from agent_core._audit import measures
from agent_core._audit.clones import RULE_CLONE, RULE_RESTATED, CloneCheck
from agent_core._audit.magic import MEASURE_MAGIC_NUMBER, MagicNumbers
from agent_core._audit.ruff import EXTRA_RULES, RuffMissing, RuffProgram, RuffRows

GATING_SET = ["E4", "E7", "E9", "F"]
FOUR_ARGUMENTS = "def joined(first, second, third, fourth):\n    return first\n"
THREE_ARGUMENTS = "class Joiner:\n    def joined(self, first, second, third):\n        return first + second + third\n"
FLAG = "def read(path, strict: bool):\n    return path if strict else None\n"
SWALLOWED = ("import os\n\n\ndef moved(partial, path):\n    try:\n        os.replace(partial, path)\n"
             "    except OSError:\n        pass\n")
HELPER = ("SEPARATOR = \"-\"\nSUFFIX = \".md\"\n\n\ndef name_of(title):\n    words = title.lower().split()\n"
          "    joined = SEPARATOR.join(words)\n    return joined + SUFFIX\n")
RESTATING = "def record_name(title):\n    return \"-\".join(title.lower().split()) + \".md\"\n"
CLONING = "def label_of(heading):\n    parts = heading.lower().split()\n    text = SEPARATOR.join(parts)\n" \
          "    return text + SUFFIX\n"
SLICED = "def first(paths):\n    return sorted(paths)[:50]\n"
COMPARED = "def is_full(paths):\n    return len(paths) > 50\n"


class CodeRoot:
    def __init__(self, case: unittest.TestCase) -> None:
        self.files = TemporaryFiles(case)
        self.files.written("AGENTS.md", "# Contract\n")

    def ruff_rules(self, name: str, source: str) -> list[str]:
        return [row["rule"] for row in RuffRows([self.files.written(name, source)], self.files.root).rows()]


class TestTheExtraRuffRules(unittest.TestCase):
    def setUp(self) -> None:
        self.root = CodeRoot(self)

    def test_the_lint_selects_the_extra_rules(self) -> None:
        self.assertEqual(("PLR0913", "PLR0915", "PLR2004", "C901", "FBT", "BLE", "S110", "ERA", "ARG"), EXTRA_RULES)

    def test_a_function_with_four_arguments_is_a_row(self) -> None:
        self.assertIn("PLR0913", self.root.ruff_rules("lib/four.py", FOUR_ARGUMENTS))

    def test_a_method_with_three_arguments_beside_self_is_no_row(self) -> None:
        self.assertEqual([], self.root.ruff_rules("lib/three.py", THREE_ARGUMENTS))

    def test_a_flag_argument_is_a_row(self) -> None:
        self.assertIn("FBT001", self.root.ruff_rules("lib/flag.py", FLAG))

    def test_a_swallowed_typed_exception_is_a_row(self) -> None:
        self.assertIn("S110", self.root.ruff_rules("lib/swallowed.py", SWALLOWED))

    def test_the_lint_reports_the_rows_under_code(self) -> None:
        self.root.files.written("lib/four.py", FOUR_ARGUMENTS)
        rules = [row["rule"] for row in AuditRun(self.root.files.root).payload("lint")["code"]]
        self.assertIn("PLR0913", rules)


class TestTheGatingSet(unittest.TestCase):
    def test_pyproject_gates_on_e4_e7_e9_and_f_alone(self) -> None:
        settings = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(GATING_SET, settings["tool"]["ruff"]["lint"]["select"])


class TestAMissingRuff(unittest.TestCase):
    def setUp(self) -> None:
        self.root = CodeRoot(self)
        self.root.files.written("lib/four.py", FOUR_ARGUMENTS)

    def test_the_lint_names_the_missing_ruff(self) -> None:
        with mock.patch.object(RuffProgram, "command", side_effect=RuffMissing("ruff is not installed")):
            payload = AuditRun(self.root.files.root).payload("lint")
        self.assertEqual("ruff is not installed", payload["skipped"]["code"])

    def test_the_lint_still_prints_every_other_row(self) -> None:
        with mock.patch.object(RuffProgram, "command", side_effect=RuffMissing("ruff is not installed")):
            payload = AuditRun(self.root.files.root).payload("lint")
        self.assertIn("prose", payload)

    def test_a_python_without_ruff_falls_back_to_the_path(self) -> None:
        missing = mock.Mock(returncode=1)
        with mock.patch("subprocess.run", return_value=missing), mock.patch("shutil.which", return_value=None):
            self.assertRaises(RuffMissing, RuffProgram().command)


class TestTheCloneDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)
        self.helper = self.files.written("lib/names.py", HELPER)

    def _rules(self, source: str) -> list[str]:
        caller = self.files.written(".claude/skills/one/scripts/run.py", source)
        return [row["rule"] for row in CloneCheck([self.helper, caller], self.files.root).rows()]

    def test_a_function_that_restates_a_helpers_constants_is_a_row(self) -> None:
        self.assertEqual([RULE_RESTATED], self._rules(RESTATING))

    def test_a_function_that_repeats_a_helpers_shape_is_a_row(self) -> None:
        self.assertEqual([RULE_CLONE], self._rules(CLONING))

    def test_a_function_that_calls_the_helper_is_no_row(self) -> None:
        self.assertEqual([], self._rules("def record_name(title):\n    return name_of(title)\n"))

    def test_a_helper_in_lib_is_never_its_own_clone(self) -> None:
        self.assertEqual([], CloneCheck([self.helper], self.files.root).rows())


class TestMagicNumbers(unittest.TestCase):
    def setUp(self) -> None:
        self.files = TemporaryFiles(self)

    def _rows(self, source: str) -> list[dict]:
        return MagicNumbers([self.files.written("lib/numbers.py", source)], self.files.root).findings()

    def test_a_bare_number_in_a_function_body_is_a_row(self) -> None:
        self.assertEqual([MEASURE_MAGIC_NUMBER], [row["rule"] for row in self._rows(SLICED)])

    def test_a_number_in_a_comparison_is_left_to_ruff(self) -> None:
        self.assertEqual([], self._rows(COMPARED))

    def test_a_named_argument_is_no_row(self) -> None:
        self.assertEqual([], self._rows("import json\n\n\ndef shown(value):\n    return json.dumps(value, indent=2)\n"))

    def test_a_module_constant_is_no_row(self) -> None:
        self.assertEqual([], self._rows("LIMIT = 50\n\n\ndef first(paths):\n    return paths[:LIMIT]\n"))


class TestTheCodeMeasuresRuffCannotCount(unittest.TestCase):
    def test_the_measures_hold_file_length_function_length_comments_and_docstrings(self) -> None:
        names = {name for name in vars(measures) if name.startswith("MEASURE_")}
        self.assertEqual({"MEASURE_LONG_FUNCTION", "MEASURE_LONG_FILE", "MEASURE_DOCSTRING", "MEASURE_COMMENT"},
                         names)


if __name__ == "__main__":
    unittest.main()
