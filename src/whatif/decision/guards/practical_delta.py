"""`practical_delta_guard` — cardinal #10 *magnitude layer* (blocks_ship).

Cardinal rule #10 (statistical claims must match the design) is
enforced by two layers in v0.1:

1. The **primary endpoint** — a rate-based check ("did at least N% of
   the failure cohort improve?") implemented by
   `failure_improvement_below_threshold` / its guard. This is the
   load-bearing endpoint that drives the verdict per #10's "verdicts
   derive from predeclared cohort-level endpoints" doctrine. **Deferred
   to Phase 2.5b** (blocked on `CohortResult` rate-count fields; see
   cascade-catalog "Phase 2.5 deferred guards — dependency map").

2. The **magnitude layer** (this guard) — a supplementary defense that
   blocks Ship even if the primary endpoint passes, when the observed
   median delta is inside the practical-delta noise floor (`<= epsilon`).
   "Statistically observable but practically negligible" is the cardinal
   #10 framing; the magnitude check refuses to ship a noise-floor win
   regardless of how the primary endpoint scored.

Both layers are needed: rate-only could ship a 51% improvement of
+0.001 (technically met, practically meaningless); magnitude-only could
ship a +0.5 delta that only 5% of the cohort experienced (huge effect,
narrow base). v0.1 ships the magnitude layer first because it lands
without the rate-count dependency.

This guard reads the failure cohort only — that's where we evaluate
"the change rescued failures by enough to ship". The baseline
non-regression guard (separate, future PR) handles the symmetric check
on the baseline cohort.

Precondition: a `failure` cohort exists with a non-None `median_delta`.
When either is missing this guard emits no finding; the floor or
another guard catches the missing-cohort case. The floor's
`required_cohort_present` rule is the structural check; this guard
operates above the floor on quality.

TODO(phase-2.6): when `failure_improvement_below_threshold` (the
rate-based primary endpoint guard) lands in the same Phase 2.6 PR,
revisit this docstring and cross-link to that one so the magnitude-
vs-endpoint partition is sharp at both call sites. See cascade-catalog
"Phase 2.5 deferred guards — dependency map" → resolution plan #4
(framing cleanup sub-bullet).
"""

from __future__ import annotations

from collections.abc import Sequence

from whatif.decision.finding_codes import make_decision_finding
from whatif.serialization.decimal import FieldLabel, parse_decimal_string
from whatif.types.cohort import CohortResult
from whatif.types.finding import DecisionFinding
from whatif.types.policy import DecisionPolicy


def practical_delta_guard(
    cohort_results: Sequence[CohortResult],
    policy: DecisionPolicy,
) -> list[DecisionFinding]:
    """Emit `practical_delta_below_threshold` when the failure cohort's
    median delta is at or below `policy.practical_delta_epsilon`.

    Equality counts as below-threshold: the epsilon represents "the
    smallest meaningful effect"; a delta exactly at that level isn't
    above noise.
    """
    failure = next((c for c in cohort_results if c.name == "failure"), None)
    if failure is None or failure.median_delta is None:
        return []

    median_delta_str = failure.median_delta
    median_delta_float = parse_decimal_string(
        median_delta_str,
        field=FieldLabel(f"CohortResult.median_delta (cohort={failure.name!r})"),
    )

    threshold = policy.practical_delta_epsilon
    if median_delta_float > threshold:
        return []

    return [
        make_decision_finding(
            "practical_delta_below_threshold",
            message=(
                f"failure cohort median delta {median_delta_str} "
                f"<= practical-delta threshold {threshold:.3f}"
            ),
            details={
                "median_delta": median_delta_str,
                "threshold": format(threshold, ".3f"),
            },
        )
    ]
