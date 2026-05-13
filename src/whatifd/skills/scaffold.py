"""Orchestrate the full skill scaffolding pipeline.

``scaffold_skill(skill_dir)`` runs:
  loader -> generator -> writer


and returns a ``ScaffoldResult``. All typed errors from the sub-layers
(``SkillManifestError``, ``SkillGenerationError``) propagate unchanged so the
CLI can present them with consistent formatting and exit codes.

This module is the public entry point for programmatic use (tests, scripts).
The CLI in ``whatifd.cli`` calls this function.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from whatifd.skills.generator import generate_skill
from whatifd.skills.loader import load_skill
from whatifd.skills.schema import SkillManifest
from whatifd.skills.writer import write_skill, WriteResult


@dataclass(frozen=True, slots=True)
class ScaffoldResult:
    """Result of a skill scaffolding ``scaffold_skill`` call."""

    manifest: SkillManifest
    write_result: WriteResult

    @property
    def path_written(self) -> Path:
        return self.write_result.path_written

    @property
    def config_patch_hint(self) -> str:
        return self.write_result.config_patch_hint

    @property
    def factory_patch_hint(self) -> str:
        return self.write_result.factory_patch_hint


def scaffold_skill(
        skill_dir: Path,
        *,
        overwrite: bool = False,
) -> ScaffoldResult:
    """Generate adapter code from ``<skill_dir>/skill.md``.
    Scaffold a new skill at the specified directory location.

    Steps:
    1. Load and validate the manifest from ``<skill_dir>/skill.md``.
    2. Generate adapter code and patch hints.
    3. Write ``<skill_dir>/__init__.py`` (unless it exists and ``overwrite`` is ``False``).

    :param skill_dir: The target directory for the skill scaffold. The provided
        path should point to where the new skill folder structure should
        be created.
    :type skill_dir: Path
    :param overwrite: A boolean flag indicating whether to overwrite existing
        content in the target directory. If set to `False` and the directory
        is not empty, the function will not proceed with creating the skill.
    :type overwrite: bool
    :return: A result object containing information about the scaffolding
            operation, such as success status and any relevant details.
    :rtype: ScaffoldResult
    :raises: SkillManifestError: On parse/validation failure in the loader.
             SkillGenerationError: On template rendering or file-write failure.
    """
    manifest, body = load_skill(skill_dir / "skill.md")
    generated = generate_skill(manifest, body)
    result = write_skill(skill_dir, generated, overwrite=overwrite)
    return ScaffoldResult(manifest=manifest, write_result=result)


__all__ = ["ScaffoldResult", "scaffold_skill"]