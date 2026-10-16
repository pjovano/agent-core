from __future__ import annotations

import unittest
from pathlib import Path

from _repository import REPOSITORY_ROOT

SKILLS_DIR = REPOSITORY_ROOT / "core" / "skills"
SKILL_FILE = "SKILL.md"
FRONTMATTER_FENCE = "---"
NAME_KEY = "name:"


def frontmatter_name(skill_file: Path) -> str | None:
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != FRONTMATTER_FENCE:
        return None
    for line in lines[1:]:
        if line == FRONTMATTER_FENCE:
            return None
        if line.startswith(NAME_KEY):
            return line.removeprefix(NAME_KEY).strip()
    return None


def skill_directories() -> list[Path]:
    return sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir())


class EveryCoreSkillNamesItsDirectory(unittest.TestCase):
    def test_every_skill_directory_holds_a_skill_file(self) -> None:
        missing = [path.name for path in skill_directories() if not (path / SKILL_FILE).is_file()]
        self.assertEqual([], missing)

    def test_every_skill_file_names_its_directory(self) -> None:
        mismatched = [f"{path.name}: {frontmatter_name(path / SKILL_FILE)}" for path in skill_directories()
                      if (path / SKILL_FILE).is_file() and frontmatter_name(path / SKILL_FILE) != path.name]
        self.assertEqual([], mismatched)


if __name__ == "__main__":
    unittest.main()
