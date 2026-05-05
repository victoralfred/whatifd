"""In-diff spot-check that Phase 2.5b's new blocking finding codes
have registered fix-suggestion templates (cardinal rule #8).

The Phase 2.4 cross-registry coverage gate at
`tests/unit/whatif/decision/test_fix_suggestions.py::TestCrossRegistryCoverage`
already enumerates every `blocks_ship` and `blocks_all` finding code
and asserts coverage. This file is a localized targeted assertion that
makes the cardinal-#8 spot-check visible in the diff of every PR that
adds a blocking finding code, so reviewers don't have to chase the
gate test to confirm coverage.

Pattern: any PR that adds a `blocks_ship` or `blocks_all` finding code
to `FINDING_CODE_REGISTRY` should add an assertion here for that
specific code. The Phase 2.4 gate is the canonical enforcement; this
file is the in-PR breadcrumb.
"""

from __future__ import annotations

from whatif.decision.fix_suggestions import FIX_SUGGESTION_REGISTRY


def test_failure_improvement_below_threshold_has_fix_suggestion() -> None:
    # PR #24 added the rate-based primary endpoint guard. Cardinal #8
    # requires the blocks_ship finding to be actionable.
    assert "failure_improvement_below_threshold" in FIX_SUGGESTION_REGISTRY


def test_baseline_regression_above_threshold_has_fix_suggestion() -> None:
    # PR #24 added the symmetric non-regression endpoint guard.
    assert "baseline_regression_above_threshold" in FIX_SUGGESTION_REGISTRY
