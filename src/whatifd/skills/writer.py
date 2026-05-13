"""Writer generated skill code to disk and surface patch instructions.

``write_skill`` takes the output of ``generate_skill`` and:
1. Writes ``<skill_dir/__init__.py`` (fails if already exists unless
   ``overwrite=True`` is passed).
2. Returns the path of the written file and the printed patch instructions.

Config and factory patches are NOT applied automatically (v0.1 policy).
The caller (CLI or scaffold) is responsible for printing ``config_patch_hint``
and ``factory_patch_hint`` to the operator. Auto-patching is a v0.2 feature.

Cardinal #1: all OS-level errors are caught and re-raised as ``SkillGenerationError``
with actionable messages.

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from whatifd.skills.errors import SkillGenerationError
from whatifd.skills.generator import GeneratedSkill


@dataclass(frozen=True, slots=True)
class WriteResult:
    """Result of a successful ``write_skill`` call."""

    path_written: Path
    config_patch_hint: str
    factory_patch_hint: str


def write_skill(
        skill_dir: Path,
        generated: GeneratedSkill,
        *,
        overwrite: bool = False,
) -> WriteResult:
    """Write ``__init__.py`` into ``skill_dir`` and surface patch instructions.

    :param skill_dir: The directory containing the ``skill.md`` file. The
                      generated ``__init__.py`` is written here.

    :param generated: Output from ``generate_skill``.

    :param overwrite: When ``True``, overwrite an existing ``__init__.py``.
                      Default ``False`` raises ``SkillGenerationError`` if the file
                      already exists, protecting against accidental overwrites.

    :returns: ``WriteResult`` containing the path written and patch hints.

    :raises:
        SkillGenerationError: if ``skill_dir/__init__.py`` already exists and
            ``overwrite=False``. or if any OS-level errors occur during file writing.
    """
    out_path = skill_dir / "__init__.py"

    if out_path.exists() and not overwrite:
        raise SkillGenerationError(
            f"{out_path} already exists. Pass --overwrite to replace it. "
            "Inspect the existing file before overwriting to avoid losing"
            " manual implementation work."
        )

    try:
        out_path.write_text(generated.skill_code, encoding="utf-8")
    except OSError as exc:
        raise SkillGenerationError(
            f"Failed to write {out_path}: {exc}."
            "Check that the directory exists and is writable."
        ) from exc


    return WriteResult(
        path_written=out_path,
        config_patch_hint=generated.config_patch_hint,
        factory_patch_hint=generated.factory_patch_hint,
    )


__all__ = ["WriteResult", "write_skill"]