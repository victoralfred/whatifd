"""Parse a ``skill.md`` file into a ``(SkillManifest, body_str)`` tuple.

A ``skill.md`` file has the same structure as a Claude Code ``SKILL.md``:
YAML frontmatter fences by ``---`` lines, followed by markdown body text.

```
---
name: my_skill
description: "Does something useful."
kind: scorer
...
---

## What this skill does
<markdown prose>
```

The loader:
1. Reads the file (FileNotFoundError -> SkillManifestError with path hint).
2. Splits on the ``---`` fence (missing/malformed fence -> SkillManifestError).
3. Parses the YAML frontmatter via ``yaml.safe_load`` (YAML errors -> SkillManifestError).
4. Validates the parsed dict as ``SkillManifest`` (Pydantic errors -> SkillManifestError).
5. Returns ``(manifest, body)`` where ``body`` is the raw markdown string.

Cardinal #1: every failure surface is typed and carries an actionable message.

"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from whatifd.skills.errors import SkillManifestError
from whatifd.skills.schema import SkillManifest


def load_skill(skill_md_path: Path) -> tuple[SkillManifest, str]:
    """
    Loads a skill from a given markdown file path.

    This function reads the provided markdown file that contains skill information
    and processes it to extract the skill manifest and content string.

    :param skill_md_path: The path to the markdown file containing the skill definition.
    :type skill_md_path: Path

    :return: A tuple containing the skill manifest object and the content string.
    :raises: SkillManifestError if any step fails with a descriptive error message.
    :rtype: tuple[SkillManifest, str]
    """
    try:
        raw = skill_md_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SkillManifestError(
            f"Skill file not found: {skill_md_path}. "
            "Create the file with YAML frontmatter (see "
            ".claude/skills/capabilities/templates/skill-template.md)."
        )
    except OSError as exc:
        raise SkillManifestError(
            f"Error reading skill file: {skill_md_path}: {exc}. Check file permissions."
        ) from exc

    frontmatter_str, body = _split_frontmatter(raw, skill_md_path)
    frontmatter_dict = _parse_yaml(frontmatter_str, skill_md_path)
    manifest = _validate_manifest(frontmatter_dict, skill_md_path)
    return manifest, body


def _split_frontmatter(raw: str, path: Path) -> tuple[str, str]:
    """Split raw file content on the YAML ``---`` fence.

    The file must start with ``---`` (optional leading whitespace ignored),
    and have a second ``---`` line that closes the frontmatter block.

    :raises: (frontmatter_str, body_str) - both stripped of leading/trailing whitespace.

    """
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillManifestError(
            f"{path}: skill.md must begin with a YAML frontmatter block "
            "fenced by '---' lines. Example: \n"
            "---\n"
            "name: my_skill\n"
            "kind: scorer\n"
            "---\n"
        )
    close_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        raise SkillManifestError(
            f"{path}: YAML frontmatter block is not closed. "
            "Add a '---' line after the last frontmatter key."
        )
    frontmatter_str = "\n".join(lines[1:close_idx])
    body_str = "\n".join(lines[close_idx + 1:]).strip()
    return frontmatter_str, body_str


def _parse_yaml(frontmatter_str: str, path: Path) -> object:
    """Parse YAML frontmatter string into a Python object."""
    try:
        parsed = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as exc:
        raise SkillManifestError(
            f"{path}: YAML frontmatter parse error: {exc}. "
            "Ensure the frontmatter is valid YAML (no tabs, proper indentation)."
        ) from exc
    if not isinstance(parsed, dict):
        raise SkillManifestError(
            f"{path}: YAML frontmatter must be a mapping (key: value pairs). "
            f"Got {type(parsed).__name__!r}."
        )
    return parsed


def _validate_manifest(frontmatter_dict: object, path: Path) -> SkillManifest:
    """Validate a parsed YAML dict as a SkillManifest"""
    try:
        return SkillManifest.model_validate(frontmatter_dict)
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) if err["loc"] else "<root>"
            errors.append(f"    {loc}: {err['msg']}")
        raise SkillManifestError(
            f"{path}: skill manifest validation failed:\n"
            + "\n".join(errors)
            + "\nSee .claude/skills/capabilities/SKILL.md for the full schema."
        ) from exc


__all__ = ["load_skill"]