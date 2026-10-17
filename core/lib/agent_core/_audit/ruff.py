from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from agent_core._audit.rows import Row
from agent_core._audit.scope import ENCODING, RepositoryPath

EXTRA_RULES = ("PLR0913", "PLR0915", "PLR2004", "C901", "FBT", "BLE", "S110", "ERA", "ARG")
MAX_ARGUMENTS = 3
RUFF = "ruff"
RUFF_SETTINGS = ("check", "--isolated", "--no-cache", "--exit-zero", "--output-format", "json",
                 "--target-version", "py312", "--select", ",".join(EXTRA_RULES),
                 "--config", f"lint.pylint.max-args = {MAX_ARGUMENTS}",
                 "--config", "lint.flake8-bandit.check-typed-exception = true")
FILES_PER_RUN = 400


class RuffMissing(LookupError):
    pass


class RuffProgram:
    def command(self) -> list[str]:
        module = subprocess.run([sys.executable, "-m", RUFF, "--version"], capture_output=True, check=False)
        if module.returncode == 0:
            return [sys.executable, "-m", RUFF]
        found = shutil.which(RUFF)
        if found is None:
            raise RuffMissing("ruff is not installed: install the version the CI workflow pins, and run the lint "
                              "again; the code rows of the extra ruff rules are absent")
        return [found]


class RuffRows:
    def __init__(self, paths: list[Path], root: Path, program: RuffProgram | None = None) -> None:
        self._paths = paths
        self._root = root
        self._program = RuffProgram() if program is None else program

    def rows(self) -> list[dict]:
        if not self._paths:
            return []
        command = self._program.command()
        diagnostics = []
        for start in range(0, len(self._paths), FILES_PER_RUN):
            diagnostics += self._checked(command, self._paths[start:start + FILES_PER_RUN])
        return [self._row(diagnostic) for diagnostic in diagnostics]

    def _checked(self, command: list[str], paths: list[Path]) -> list[dict]:
        run = subprocess.run([*command, *RUFF_SETTINGS, "--", *(str(path) for path in paths)], cwd=self._root,
                             capture_output=True, encoding=ENCODING, errors="replace", check=False)
        try:
            return json.loads(run.stdout or "[]")
        except json.JSONDecodeError as error:
            raise RuffMissing(f"ruff printed no JSON ({error}): {run.stderr.strip()}") from error

    def _row(self, diagnostic: dict) -> dict:
        label = RepositoryPath(Path(diagnostic["filename"]), self._root).label()
        return Row(diagnostic["code"] or "", label, diagnostic["location"]["row"], diagnostic["message"]).as_dict()
