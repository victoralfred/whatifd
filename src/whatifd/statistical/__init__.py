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

## Wire-boundary pattern (read this before calling)

`BootstrapResult` carries plain Python `float` values for `median`,
`ci_lower`, and `ci_upper`. The wire-canonical view of those
quantities is `DecimalString` (cardinal #4 determinism — only the
wire shape is byte-stable across platforms; in-memory floats are
not). Callers wiring this into `whatifd.types.cohort.CohortResult`
or `whatifd.report.models_v01.ReportV01` MUST format the float to
`DecimalString` at the boundary, e.g.:

```python
from whatifd.types.primitives import DecimalString

result = paired_percentile_bootstrap(deltas, seed=42)
median = DecimalString(f"{result.median:.3f}")
ci_lower = DecimalString(f"{result.ci_lower:.3f}")
```

Phase E.2 wires this into `_cohort_result_from_bucket` directly;
direct external callers follow the same pattern.
"""

from whatifd.statistical.bootstrap import (
    BootstrapResult,
    paired_percentile_bootstrap,
)

__all__ = [
    "BootstrapResult",
    "paired_percentile_bootstrap",
]
