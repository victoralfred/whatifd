"""`whatifd.statistical` — Phase E statistical layer.

Houses the real bootstrap implementation and (in later sub-phases)
Holm correction + observed-MDE power warnings. v0.1 / v0.2 baseline
ships an empirical-percentile shortcut in `whatifd.pipeline`; this
module's `paired_percentile_bootstrap` is the doctrinally-correct
replacement.

Phase E.1 (this module's first delivery): bootstrap algorithm +
property tests. The pipeline-side disclosure flip and the
walkthrough-fixture regeneration are deferred to Phase E.2 — that
PR's focus IS the regeneration churn, kept separate so the
algorithm review and the documentation churn are independently
reviewable.
"""

from whatifd.statistical.bootstrap import (
    BootstrapResult,
    paired_percentile_bootstrap,
)

__all__ = [
    "BootstrapResult",
    "paired_percentile_bootstrap",
]
