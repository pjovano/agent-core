from __future__ import annotations

import json
import subprocess
import sys
import unittest

from _repository import REPOSITORY_ROOT, VENDORED_CORE

GENERATED_BLOCKS = ("permissions", "sandbox")


class TheSettingsBlocksAreTheGeneratorsOutput(unittest.TestCase):
    def test_the_permissions_and_sandbox_blocks_equal_what_domain_py_settings_prints(self) -> None:
        completed = subprocess.run([sys.executable, str(VENDORED_CORE / "domain.py"), "settings"],
                                   cwd=REPOSITORY_ROOT, capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        settings = json.loads((REPOSITORY_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(completed.stdout), {key: settings.get(key) for key in GENERATED_BLOCKS})


if __name__ == "__main__":
    unittest.main()
