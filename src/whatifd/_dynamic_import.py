"""Shared helper for the `python:<module>:<attr>` loaders.

`runner_loader` and `scorer_loader` resolve user-supplied references
(`target.runner`, `scorer.score_fn`, `source.spans_provider`) by importing a
dotted module path. An installed `whatifd` console script does NOT put the
invocation directory on `sys.path` — unlike `python script.py` or `python -m`
— so a developer's OWN runner/scorer/provider living in their project root
(e.g. `python:my_agent.replay:run` → `./my_agent/replay.py`) would fail to
import with "No module named 'my_agent'".

These references ARE user-supplied code that whatifd loads and calls by
contract (the runner is the documented extension point), so resolving them
from the project root is the expected, conventional behavior — the same thing
`python -m` / pytest / most CLI plugin loaders do. This helper makes that
true.
"""

from __future__ import annotations

import os
import sys


def ensure_cwd_importable() -> None:
    """Put the current working directory on `sys.path` (idempotent).

    Inserts the absolute cwd at the front so a `python:<module>:<attr>`
    reference resolves modules in the user's project root. Safe to call
    repeatedly — a no-op if the cwd is already present.
    """
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


__all__ = ["ensure_cwd_importable"]
