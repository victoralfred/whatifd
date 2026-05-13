"""Typed errors for the skill scaffolding system.

All expected failures in the skill loader, generator, and writer surface
as one of these typed exceptions with an actionable message.

Cardinal #1: no raw exceptions escape the skill scaffolding boundary.
"""

from __future__ import annotations

class SkillError(Exception):
    """Base class for all skill-scaffolding errors."""


class SkillManifestError(SkillError):
    """Raised when a skill.md file cannot be parsed or validated.

        The message names the file, the specific field or section that failed,
        and what to fix. The CLI converts this to a stderr message + exit 2.
        """

class SkillGenerationError(SkillError):
    """Raised when code generation or file writing fails.

        Covers template rendering failures, output-path conflicts, and OS-level
        write errors. The message names the skill, the step that failed and the
        corrective action.
        """


__all__ = [
    "SkillError",
    "SkillManifestError",
    "SkillGenerationError",
]