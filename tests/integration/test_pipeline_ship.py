"""Phase 9A.1 integration test — Clean Ship scenario.

Drives the synthetic stub adapter through `run_pipeline` end-to-end
and pins:
- The verdict resolves to Ship.
- Floor passed on both required cohorts.
- Cohort counts match the fixture's delta function.
- Median delta and CI bounds are populated as DecimalString.

This is the architectural-proof test for cardinal #2 floor +
projection in Phase 9A.1. Phase 9A.2 adds the remaining five
walkthrough scenarios; Phase 9A.3 adds determinism byte-equality;
Phase 9A.4 adds failure injection.
"""

from __future__ import annotations

from whatif.pipeline import run_pipeline
from whatif.types.policy import DecisionPolicy, TrustFloor

from ._fixtures import scenario_clean_ship


class TestCleanShipScenario:
    def test_verdict_is_ship(self) -> None:
        fx = scenario_clean_ship()
        report = run_pipeline(
            fx.trace_source,
            delta_fn=fx.delta_fn,
            floor=TrustFloor(),
            policy=DecisionPolicy(),
            runtime=fx.runtime,
            methodology=fx.methodology,
            cache_summary=fx.cache_summary,
        )
        assert report.verdict_state == "ship"

    def test_cohort_counts_match_fixture(self) -> None:
        fx = scenario_clean_ship()
        report = run_pipeline(
            fx.trace_source,
            delta_fn=fx.delta_fn,
            floor=TrustFloor(),
            policy=DecisionPolicy(),
            runtime=fx.runtime,
            methodology=fx.methodology,
            cache_summary=fx.cache_summary,
        )
        cohorts = {c.name: c for c in report.cohort_results}
        assert cohorts["failure"].selected == 20
        assert cohorts["failure"].scored == 20
        assert cohorts["failure"].improved_count == 14
        assert cohorts["failure"].unchanged_count == 6
        assert cohorts["failure"].regressed_count == 0
        assert cohorts["baseline"].selected == 20
        assert cohorts["baseline"].regressed_count == 0
        # All 20 baseline deltas are 0.01 < epsilon=0.05 — unchanged.
        assert cohorts["baseline"].unchanged_count == 20

    def test_floor_passed_on_required_cohorts(self) -> None:
        fx = scenario_clean_ship()
        report = run_pipeline(
            fx.trace_source,
            delta_fn=fx.delta_fn,
            floor=TrustFloor(),
            policy=DecisionPolicy(),
            runtime=fx.runtime,
            methodology=fx.methodology,
            cache_summary=fx.cache_summary,
        )
        for c in report.cohort_results:
            assert c.floor_passed, f"cohort {c.name} did not pass the floor"
            assert c.floor_failures == []

    def test_ci_bounds_populated(self) -> None:
        fx = scenario_clean_ship()
        report = run_pipeline(
            fx.trace_source,
            delta_fn=fx.delta_fn,
            floor=TrustFloor(),
            policy=DecisionPolicy(),
            runtime=fx.runtime,
            methodology=fx.methodology,
            cache_summary=fx.cache_summary,
        )
        for c in report.cohort_results:
            assert c.ci_computable, f"cohort {c.name} CI not computed"
            assert c.median_delta is not None
            assert c.ci_lower is not None
            assert c.ci_upper is not None
