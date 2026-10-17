from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from agent_core._domain.fields import ManifestError
from agent_core._domain.manifest import MANIFEST_NAME

VENDOR_PREFIX = "vendor/agent-core"
SETTINGS_PATH = Path(".claude") / "settings.json"
GENERATED_BLOCKS = ("permissions", "sandbox")
JSON_INDENT = 2


class VendoredDomainScript:
    def __init__(self, domain_root: Path) -> None:
        self._domain_root = domain_root

    def settings(self, manifest: Path) -> dict:
        completed = subprocess.run([sys.executable, str(self._domain_root / VENDOR_PREFIX / "domain.py"), "settings",
                                    "--domain", str(manifest)], cwd=self._domain_root, capture_output=True, text=True)
        payload = json.loads(completed.stdout)
        if completed.returncode != 0:
            raise ManifestError(payload["error"])
        return payload


class DomainSettings:
    def __init__(self, domain_root: Path) -> None:
        self._domain_root = domain_root

    def refuse_if_invalid(self, manifest: dict) -> None:
        self.blocks(manifest)

    def blocks_of_domain_json(self) -> dict:
        return VendoredDomainScript(self._domain_root).settings(self._domain_root / MANIFEST_NAME)

    def blocks(self, manifest: dict) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / MANIFEST_NAME
            candidate.write_text(JsonText(manifest).text(), encoding="utf-8")
            return VendoredDomainScript(self._domain_root).settings(candidate)


class ManifestFile:
    def __init__(self, domain_root: Path) -> None:
        self._path = domain_root / MANIFEST_NAME

    def write(self, manifest: dict) -> None:
        self._path.write_text(JsonText(manifest).text(), encoding="utf-8")


class SettingsFile:
    def __init__(self, domain_root: Path) -> None:
        self._path = domain_root / SETTINGS_PATH

    def write_blocks(self, blocks: dict) -> None:
        settings = json.loads(self._path.read_text(encoding="utf-8"))
        settings.update({key: blocks[key] for key in GENERATED_BLOCKS})
        self._path.write_text(JsonText(settings).text(), encoding="utf-8")


class JsonText:
    def __init__(self, values: object) -> None:
        self._values = values

    def text(self) -> str:
        return json.dumps(self._values, indent=JSON_INDENT, ensure_ascii=False) + "\n"
