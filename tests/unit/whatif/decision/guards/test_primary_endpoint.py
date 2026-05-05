"""Tests for `primary_endpoint_guard` — Phase 2.6b consolidation.

Replaces `test_failure_improvement.py` + `test_baseline_regression.py`
with a single test surface parametrized over the two endpoint
directions. The hardcoded boundary semantics (strict `<` for
improvement, strict `>` for regression) are preserved; the dispatcher
test class exercises the configurable surface.
"""

from __future__ import annotations

from whatif.decision.guards.primary_endpoint import primary_endpoint_guard
from whatif.types.policy import DecisionPolicy, PrimaryEndpoint

from ._helpers import baseline_cohort, failure_cohort

# ---------------------------------------------------------------------------
# Default-policy behavior — must match the Phase 2.5b hardcoded guards
# ---------------------------------------------------------------------------


class TestPrimaryEndpointDefaultPolicyImprovement:
    """`improvement_above_threshold` direction (default for `failure` cohort)."""

    def test_emits_when_rate_below_threshold(self) -> None:
        # 4/20 = 0.200 < default 0.500 → emit
        cohort = failure_cohort(improved=4, unchanged=10, regressed=6)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "failure_improvement_below_threshold"
        assert f.severity == "blocks_ship"
        assert f.details["observed"] == "0.200"
        assert f.details["threshold"] == "0.500"

    def test_silent_at_exactly_threshold(self) -> None:
        # 5/10 = 0.500 == threshold → meets policy "at least 50%" promise
        cohort = failure_cohort(improved=5, unchanged=3, regressed=2)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        # No improvement emit; baseline endpoint also doesn't fire because
        # baseline cohort isn't present.
        assert findings == []

    def test_silent_above_threshold(self) -> None:
        cohort = failure_cohort(improved=8, unchanged=2, regressed=0)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        assert findings == []

    def test_silent_when_zero_scored(self) -> None:
        cohort = failure_cohort(improved=0, unchanged=0, regressed=0)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        assert findings == []

    def test_message_includes_count_breakdown(self) -> None:
        cohort = failure_cohort(improved=4, unchanged=10, regressed=6)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        assert "4/20" in findings[0].message


class TestPrimaryEndpointDefaultPolicyNonRegression:
    """`non_regression_below_threshold` direction (default for `baseline` cohort)."""

    def test_emits_when_rate_above_threshold(self) -> None:
        # 3/20 = 0.150 > default 0.10 → emit
        cohort = baseline_cohort(improved=10, unchanged=7, regressed=3)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "baseline_regression_above_threshold"
        assert f.severity == "blocks_ship"
        assert f.details["observed"] == "0.150"
        assert f.details["threshold"] == "0.100"

    def test_silent_at_exactly_threshold(self) -> None:
        # 1/10 = 0.100 == threshold → meets policy "at most 10%" promise
        cohort = baseline_cohort(improved=5, unchanged=4, regressed=1)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        assert findings == []

    def test_silent_below_threshold(self) -> None:
        cohort = baseline_cohort(improved=8, unchanged=11, regressed=1)
        findings = primary_endpoint_guard([cohort], DecisionPolicy())
        assert findings == []

    def test_silent_when_no_baseline_cohort(self) -> None:
        # Only failure cohort (improvement endpoint applies); baseline
        # endpoint silently abstains because cohort is missing.
        findings = primary_endpoint_guard(
            [failure_cohort(improved=10, regressed=2)], DecisionPolicy()
        )
        # failure_cohort with improved=10 (rate 0.833 above threshold) → no emit
        assert findings == []


class TestPrimaryEndpointDefaultPolicyBothCohorts:
    """Both endpoints active simultaneously."""

    def test_both_endpoints_pass_no_findings(self) -> None:
        cohorts = [
            failure_cohort(improved=8, unchanged=2, regressed=0),
            baseline_cohort(improved=2, unchanged=8, regressed=0),
        ]
        findings = primary_endpoint_guard(cohorts, DecisionPolicy())
        assert findings == []

    def test_both_endpoints_fail_two_findings(self) -> None:
        cohorts = [
            failure_cohort(improved=2, unchanged=4, regressed=4),  # rate too low
            baseline_cohort(improved=4, unchanged=3, regressed=3),  # regression too high
        ]
        findings = primary_endpoint_guard(cohorts, DecisionPolicy())
        assert len(findings) == 2
        codes = [f.code for f in findings]
        # Order matches policy.primary_endpoints (failure first by default).
        assert codes == [
            "failure_improvement_below_threshold",
            "baseline_regression_above_threshold",
        ]

    def test_findings_in_policy_order_not_cohort_order(self) -> None:
        # Cohort list order: baseline first, failure second.
        cohorts = [
            baseline_cohort(improved=4, unchanged=3, regressed=3),
            failure_cohort(improved=2, unchanged=4, regressed=4),
        ]
        # Default policy: failure endpoint first.
        findings = primary_endpoint_guard(cohorts, DecisionPolicy())
        codes = [f.code for f in findings]
        assert codes == [
            "failure_improvement_below_threshold",
            "baseline_regression_above_threshold",
        ]


# ---------------------------------------------------------------------------
# Custom-policy behavior — the configurable surface this guard adds
# ---------------------------------------------------------------------------


class TestPrimaryEndpointCustomPolicy:
    def test_only_failure_endpoint_declared(self) -> None:
        """Policy with a single endpoint: only that one fires; the other
        cohort is ignored even if it would have triggered the default."""
        policy = DecisionPolicy(
            primary_endpoints=(
                PrimaryEndpoint(cohort="failure", direction="improvement_above_threshold"),
            ),
            required_cohorts=("failure",),
        )
        cohorts = [
            failure_cohort(improved=2, unchanged=4, regressed=4),
            # Baseline regression that would normally fire — but no
            # baseline endpoint declared, so silent.
            baseline_cohort(improved=4, unchanged=3, regressed=3),
        ]
        findings = primary_endpoint_guard(cohorts, policy)
        assert len(findings) == 1
        assert findings[0].code == "failure_improvement_below_threshold"

    def test_custom_threshold_strict(self) -> None:
        policy = DecisionPolicy(min_failure_improvement_ratio=0.80)
        # 5/10 = 0.500 < 0.800 → emit
        cohort = failure_cohort(improved=5, unchanged=3, regressed=2)
        findings = primary_endpoint_guard([cohort], policy)
        assert len(findings) == 1
        assert findings[0].details["threshold"] == "0.800"

    def test_custom_threshold_lenient(self) -> None:
        policy = DecisionPolicy(min_failure_improvement_ratio=0.10)
        # 2/10 = 0.200 > 0.100 → no emit (strict <)
        cohort = failure_cohort(improved=2, unchanged=4, regressed=4)
        findings = primary_endpoint_guard([cohort], policy)
        assert findings == []

    def test_unknown_cohort_in_endpoint_silently_skipped(self) -> None:
        # Policy declares an endpoint for a cohort that isn't in the
        # results — this guard skips silently. The floor's
        # required_cohort_present rule catches missing required cohorts;
        # this guard is policy-level.
        policy = DecisionPolicy(
            primary_endpoints=(
                PrimaryEndpoint(cohort="failure", direction="improvement_above_threshold"),
                PrimaryEndpoint(cohort="exploratory", direction="improvement_above_threshold"),
            ),
        )
        cohorts = [failure_cohort(improved=8, unchanged=2, regressed=0)]
        findings = primary_endpoint_guard(cohorts, policy)
        assert findings == []  # failure passes; exploratory missing is silent
