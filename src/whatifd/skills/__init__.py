"""whatifd skills - adapter scaffolding from declarative skill.md files.

Public API:

   from whatifd.skills import scaffold_skill

   result = scaffold_skill(Path("src/whatifd/skills/my_skill"))
   print(result.path_written)
   print(result.config_patch_hint)
   print(result.factory_patch_hint)

See ``whatifd skill generate <name>`` for the CLI entry point.
"""

from whatifd.skills.errors import SkillError, SkillGenerationError, SkillManifestError
from whatifd.skills.scaffold import ScaffoldResult, scaffold_skill
from whatifd.skills.schema import EnvVarSpec, ParameterSpec, SkillManifest


__all__ = [
    "SkillError",
    "SkillGenerationError",
    "SkillManifestError",
    "ScaffoldResult",
    "scaffold_skill",
    "EnvVarSpec",
    "ParameterSpec",
    "SkillManifest",
]