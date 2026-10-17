from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = CORE_DIR / "templates" / "domain"
RENDERED_SUFFIX = ".template"
SKIPPED_DIRECTORIES = ("__pycache__",)


@dataclass(frozen=True)
class TemplateFile:
    source: Path
    relative_target: Path

    @property
    def is_rendered(self) -> bool:
        return self.source.name.endswith(RENDERED_SUFFIX)

    def written_into(self, root: Path, values: dict[str, str]) -> None:
        target = root / self.relative_target
        target.parent.mkdir(parents=True, exist_ok=True)
        if self.is_rendered:
            target.write_text(Rendering(values).of(self.source.read_text(encoding="utf-8")), encoding="utf-8")
        else:
            shutil.copy2(self.source, target)


class Rendering:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def of(self, text: str) -> str:
        for key, value in self._values.items():
            text = text.replace("{{" + key + "}}", value)
        return text


class DomainTemplate:
    def __init__(self, directory: Path = TEMPLATE_DIR) -> None:
        self._directory = directory

    def files(self) -> list[TemplateFile]:
        return [TemplateFile(source, self._target_of(source)) for source in sorted(self._directory.rglob("*"))
                if source.is_file() and not self._is_skipped(source)]

    def written_into(self, root: Path, values: dict[str, str]) -> None:
        for template_file in self.files():
            template_file.written_into(root, values)

    def _target_of(self, source: Path) -> Path:
        relative = source.relative_to(self._directory)
        return relative.with_name(relative.name.removesuffix(RENDERED_SUFFIX))

    def _is_skipped(self, source: Path) -> bool:
        return any(part in SKIPPED_DIRECTORIES for part in source.relative_to(self._directory).parts)
