from __future__ import annotations

import contextlib
import io
import json
import unittest

from _git_files import DEFECT, FEATURE, REFACTOR, GitFiles, message

from agent_core._audit.cli import CommandLine

CONTRACT = "# Contract\n\nRun the checks after every change.\n"
SKILL = "---\nname: one\ndescription: \"One skill.\"\n---\n\n# one\n\nRun the step.\n"
GROWN_SKILL = SKILL + "\nReport the step's outcome.\n"
CUT_SKILL = "---\nname: one\ndescription: \"One skill.\"\n---\n\n# one\n"
SKILL_PATH = ".claude/skills/one/SKILL.md"
STATED = "## Summary\n\nAdds a rule.\n\n## Words added\n\n- `.claude/skills/one/SKILL.md`: +4 — report every outcome\n"


class RatchetRun:
    def __init__(self, case: unittest.TestCase) -> None:
        self.git = GitFiles(case)
        self.base = self.git.committed(message("Add the plane", FEATURE), {"AGENTS.md": CONTRACT, SKILL_PATH: SKILL})

    def verdict(self, body: str = "") -> tuple[dict, int]:
        body_file = self.git.written("pull-request-body.md", body)
        captured, code = io.StringIO(), 0
        with contextlib.redirect_stdout(captured):
            try:
                CommandLine().run(["--root", str(self.git.root), "ratchet", "--base", self.base,
                                   "--body-file", str(body_file)])
            except SystemExit as exit_:
                code = exit_.code
        return json.loads(captured.getvalue()), code


class TestAPullRequestThatGrowsTheText(unittest.TestCase):
    def setUp(self) -> None:
        self.run = RatchetRun(self)

    def test_a_refactor_that_grows_the_text_fails(self) -> None:
        self.run.git.committed(message("Restate the step", REFACTOR), {SKILL_PATH: GROWN_SKILL})
        verdict, code = self.run.verdict(STATED)
        self.assertEqual((1, True), (code, "(refactor) grows the instruction text" in verdict["failures"][0]))

    def test_a_feature_that_grows_the_text_and_states_the_words_passes(self) -> None:
        self.run.git.committed(message("Report the outcome", FEATURE), {SKILL_PATH: GROWN_SKILL})
        self.assertEqual(([], 0), (self.run.verdict(STATED)[0]["failures"], self.run.verdict(STATED)[1]))

    def test_a_defect_fix_that_grows_the_text_and_states_the_words_passes(self) -> None:
        self.run.git.committed(message("Report the outcome", DEFECT), {SKILL_PATH: GROWN_SKILL})
        self.assertEqual([], self.run.verdict(STATED)[0]["failures"])

    def test_a_feature_that_grows_the_text_without_stating_the_words_fails(self) -> None:
        self.run.git.committed(message("Report the outcome", FEATURE), {SKILL_PATH: GROWN_SKILL})
        verdict, code = self.run.verdict("## Summary\n\nAdds a rule.\n")
        self.assertEqual((1, [SKILL_PATH]), (code, [failure.split(":")[0] for failure in verdict["failures"]]))

    def test_a_statement_of_the_wrong_count_fails(self) -> None:
        self.run.git.committed(message("Report the outcome", FEATURE), {SKILL_PATH: GROWN_SKILL})
        self.assertEqual(1, self.run.verdict(STATED.replace("+4", "+3"))[1])

    def test_a_commit_without_a_trailer_that_grows_the_text_fails(self) -> None:
        self.run.git.committed("Report the outcome", {SKILL_PATH: GROWN_SKILL})
        self.assertIn("(none) grows the instruction text", self.run.verdict(STATED)[0]["failures"][0])

    def test_the_verdict_names_the_always_loaded_growth_first(self) -> None:
        self.run.git.committed(message("Grow the contract", FEATURE), {"AGENTS.md": CONTRACT + "Read the skill.\n"})
        self.assertEqual(3, self.run.verdict()[0]["always_loaded_first"])


class TestAPullRequestThatCutsTheText(unittest.TestCase):
    def setUp(self) -> None:
        self.run = RatchetRun(self)
        self.run.git.committed(message("Cut the step", REFACTOR), {SKILL_PATH: CUT_SKILL})
        self.verdict, self.code = self.run.verdict()

    def test_a_cut_passes_without_a_statement(self) -> None:
        self.assertEqual(([], 0), (self.verdict["failures"], self.code))

    def test_a_cut_lowers_the_counts_the_next_pull_request_is_held_to(self) -> None:
        self.assertEqual(-3, self.verdict["growth"]["rest"])


class TestALinkedSkill(unittest.TestCase):
    def setUp(self) -> None:
        self.run = RatchetRun(self)
        self.run.git.written("core/skills/two/SKILL.md", SKILL)
        self.run.git.linked(".claude/skills/two", "../../core/skills/two")

    def test_a_skill_reached_through_a_link_into_the_tree_is_weighed(self) -> None:
        self.run.git.committed(message("Link a core skill", REFACTOR), {})
        self.assertIn("(refactor) grows the instruction text", self.run.verdict()[0]["failures"][0])

    def test_a_skill_reached_through_a_link_into_the_vendored_core_is_not_weighed(self) -> None:
        self.run.git.written("vendor/agent-core/skills/three/SKILL.md", SKILL)
        self.run.git.linked(".claude/skills/three", "../../vendor/agent-core/skills/three")
        self.run.git.committed(message("Vendor a core skill", REFACTOR), {"core/skills/two/SKILL.md": ""})
        self.assertEqual([], self.run.verdict()[0]["failures"])


if __name__ == "__main__":
    unittest.main()
