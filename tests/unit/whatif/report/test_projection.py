"""Tests for `whatif.report.projection` — Phase 5.2 wire-format projection.

The load-bearing properties:

1. **Each Verdict variant projects to its expected `verdict_state`** —
   Ship → "ship", DontShip → "dont_ship", Inconclusive → "inconclusive".
2. **Cardinal #2 chokepoint**: the function takes `Verdict` (sealed
   union); a caller cannot synthesize `verdict_state="ship"` without
   first obtaining a `Ship` instance, which requires a
   `FloorPassedProof` from `evaluate_floor()`. The signature itself
   IS the enforcement.
3. **Findings flatten cleanly**: `decision_findings` contains the
   verdict's own `findings` list (NOT the derived `blocking_findings`
   subset; consumers compute that view from severity).
4. **Manifest fields propagate**: `trust_floor` and `decision_policy`
   are read from `runtime` (single source of truth) — drift between
   manifest content and report top-level fields is structurally
   prevented.
5. **Inputs are passed-through unmodified**: `cache_summary`,
   `methodology`, `failures`, and `runtime` appear in the output as
   the same instance the caller supplied. Projection is field-
   copying, not transformation.
"""

from __future__ import annotations

import pytest

from tests.unit.whatif.report._fixtures import (
    cache_summary,
    cohort,
    methodology,
    runtime,
    trust_floor,
)
from whatif.decision.failure_codes import make_failure_record
from whatif.decision.finding_codes import make_decision_finding
from whatif.decision.floor import evaluate_floor
from whatif.report.models_v01 import REPORT_SCHEMA_URI, REPORT_SCHEMA_VERSION
from whatif.report.projection import _flatten_verdict, project_to_report_v01
from whatif.types.verdict import DontShip, Inconclusive, Ship

# ---------------------------------------------------------------------------
# Verdict construction helpers
# ---------------------------------------------------------------------------


def _ship() -> Ship:
    """Construct a real `Ship` via the witness-token chain.

    Routes through `evaluate_floor()` so the resulting `Ship` carries
    a real `FloorPassedProof`. Tests that exercise the projection
    surface MUST go through this path — that's the cardinal #2
    enforcement we're testing.
    """
    cohorts = [cohort("failure"), cohort("baseline")]
    proof_or_failures = evaluate_floor(
        cohorts,
        trust_floor(),
        required_cohorts=("failure", "baseline"),
    )
    # _ship() asserts the floor-pass branch: with healthy cohorts and
    # default trust floor, evaluate_floor returns FloorPassedProof.
    # If this ever flakes, the cohort fixture or floor defaults need
    # adjustment, not a try/except.
    assert not isinstance(proof_or_failures, type(evaluate_floor.__annotations__).__mro__[0]), (  # type: ignore[misc]
        "test fixture invariant: cohort() must produce a floor-passing cohort"
    )
    # Use isinstance against the actual returned class.
    from whatif.decision.floor import FloorFailureSet

    assert not isinstance(proof_or_failures, FloorFailureSet), (
        f"expected FloorPassedProof from evaluate_floor; got {proof_or_failures!r}"
    )
    return Ship(
        proof=proof_or_failures,  # type: ignore[arg-type]  # narrowed by assert above
        cohort_results=cohorts,
        findings=[],
    )


def _dont_ship() -> DontShip:
    blocking = make_decision_finding(
        "baseline_regression_above_threshold",
        message="baseline cohort regressed",
        details={"observed": "0.150", "threshold": "0.100"},
    )
    return DontShip(
        cohort_results=[cohort("failure"), cohort("baseline")],
        findings=[blocking],
        blocking_findings=[blocking],
    )


def _inconclusive() -> Inconclusive:
    # `ci_unavailable_for_required_cohort` requires non-empty
    # derived_from_failures per its registry spec — the finding wraps
    # the underlying operational failure. The placeholder string
    # matches the pattern used by ci_availability_guard.
    blocking = make_decision_finding(
        "ci_unavailable_for_required_cohort",
        message="CI uncomputable on baseline",
        details={"cohort": "baseline", "reason": "sample_too_small"},
        derived_from_failures=["fail-ci-unavailable-1"],
    )
    return Inconclusive(
        cohort_results=[cohort("failure")],
        findings=[blocking],
        blocking_findings=[blocking],
    )


# ---------------------------------------------------------------------------
# Verdict-state mapping
# ---------------------------------------------------------------------------


class TestVerdictStateMapping:
    def test_ship_projects_to_ship_state(self) -> None:
        ship = _ship()
        report = project_to_report_v01(
            ship,
            failures=[],
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=runtime(),
        )
        assert report.verdict_state == "ship"

    def test_dont_ship_projects_to_dont_ship_state(self) -> None:
        report = project_to_report_v01(
            _dont_ship(),
            failures=[],
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=runtime(),
        )
        assert report.verdict_state == "dont_ship"

    def test_inconclusive_projects_to_inconclusive_state(self) -> None:
        report = project_to_report_v01(
            _inconclusive(),
            failures=[],
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=runtime(),
        )
        assert report.verdict_state == "inconclusive"


# ---------------------------------------------------------------------------
# _flatten_verdict direct coverage
# ---------------------------------------------------------------------------


class TestFlattenVerdict:
    def test_ship_produces_findings_not_blocking_subset(self) -> None:
        ship = _ship()
        state, cohorts, findings = _flatten_verdict(ship)
        assert state == "ship"
        assert cohorts == ship.cohort_results
        assert findings == ship.findings

    def test_dont_ship_produces_full_findings_not_blocking_only(self) -> None:
        # Verdict carries findings + blocking_findings (subset). The wire
        # format only includes findings; consumers derive blocking via
        # severity filter.
        ds = _dont_ship()
        state, _cohorts, findings = _flatten_verdict(ds)
        assert state == "dont_ship"
        # findings holds the full list (which here happens to equal
        # blocking_findings because the test fixture has only one
        # blocks_ship finding); the contract is "wire = findings, not
        # blocking_findings."
        assert findings == ds.findings

    def test_inconclusive_state(self) -> None:
        inc = _inconclusive()
        state, _, _ = _flatten_verdict(inc)
        assert state == "inconclusive"


# ---------------------------------------------------------------------------
# Manifest single-source-of-truth pin
# ---------------------------------------------------------------------------


class TestManifestSourceOfTruth:
    """`trust_floor` and `decision_policy` are read from `runtime` (the
    `RunManifest`) so the report's top-level fields can't drift from
    what the manifest records.
    """

    def test_trust_floor_matches_runtime(self) -> None:
        rt = runtime()
        report = project_to_report_v01(
            _ship(),
            failures=[],
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=rt,
        )
        assert report.trust_floor is rt.trust_floor

    def test_decision_policy_matches_runtime(self) -> None:
        rt = runtime()
        report = project_to_report_v01(
            _ship(),
            failures=[],
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=rt,
        )
        assert report.decision_policy is rt.decision_policy


# ---------------------------------------------------------------------------
# Pass-through pins
# ---------------------------------------------------------------------------


class TestPassThrough:
    """Inputs flow through unmodified — projection is field-copying,
    not transformation.
    """

    def test_cache_summary_is_same_instance(self) -> None:
        cs = cache_summary()
        report = project_to_report_v01(
            _ship(),
            failures=[],
            cache_summary=cs,
            methodology=methodology(),
            runtime=runtime(),
        )
        assert report.cache_summary is cs

    def test_methodology_is_same_instance(self) -> None:
        m = methodology()
        report = project_to_report_v01(
            _ship(),
            failures=[],
            cache_summary=cache_summary(),
            methodology=m,
            runtime=runtime(),
        )
        assert report.methodology is m

    def test_runtime_is_same_instance(self) -> None:
        rt = runtime()
        report = project_to_report_v01(
            _ship(),
            failures=[],
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=rt,
        )
        assert report.runtime is rt

    def test_failures_passed_as_list(self) -> None:
        # The function signature accepts Sequence[FailureRecord]; the
        # output is list[FailureRecord]. A tuple input must produce a
        # list output (defensive copy, not aliasing). Pin here.
        failure = make_failure_record(
            "cache_lock_unavailable",
            id="fail-1",
            message="lock held",
            scope="run",
            details={
                "hostname": "ci-runner-7",
                "lock_pid": 12345,
                "lock_path": ".whatif/cache/.lock",
            },
        )
        report = project_to_report_v01(
            _ship(),
            failures=(failure,),  # tuple input
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=runtime(),
        )
        assert isinstance(report.failures, list)
        assert report.failures == [failure]


# ---------------------------------------------------------------------------
# Schema constants stamped
# ---------------------------------------------------------------------------


class TestSchemaConstants:
    def test_schema_version_stamped(self) -> None:
        report = project_to_report_v01(
            _ship(),
            failures=[],
            cache_summary=cache_summary(),
            methodology=methodology(),
            runtime=runtime(),
        )
        assert report.schema_version == REPORT_SCHEMA_VERSION
        assert report.schema_uri == REPORT_SCHEMA_URI


# ---------------------------------------------------------------------------
# Cardinal #2 enforcement at the type level
# ---------------------------------------------------------------------------


class TestCardinalTwoChokepoint:
    """The signature of `project_to_report_v01` IS the cardinal #2
    enforcement. There is no path to call it with `verdict_state="ship"`
    without first obtaining a `Ship` instance, which requires
    `FloorPassedProof`. Pin this with an inspection of the function's
    type annotations so a future refactor that loosened the signature
    (e.g., to `verdict_state: str`) fails this test.
    """

    def test_first_argument_is_typed_verdict(self) -> None:
        import typing

        hints = typing.get_type_hints(project_to_report_v01)
        # The annotation is `Verdict` which is a Union alias; mypy
        # narrows to Ship | DontShip | Inconclusive. At runtime,
        # typing.get_type_hints resolves it to the underlying union.
        verdict_hint = hints["verdict"]
        # Verdict is `Ship | DontShip | Inconclusive`. typing.get_args
        # on a UnionType returns the variants.
        args = set(typing.get_args(verdict_hint))
        assert args == {Ship, DontShip, Inconclusive}, (
            f"project_to_report_v01's `verdict` parameter must be the sealed "
            f"`Verdict` union (Ship | DontShip | Inconclusive); got "
            f"args={args!r}. Loosening this signature (e.g., to "
            "`verdict_state: str`) would re-open the cardinal #2 bypass."
        )

    def test_no_verdict_state_string_parameter(self) -> None:
        # Defends against a refactor that added `verdict_state: str` as
        # a parallel input — that would be a cardinal #2 bypass.
        import inspect

        sig = inspect.signature(project_to_report_v01)
        assert "verdict_state" not in sig.parameters, (
            "project_to_report_v01 must NOT take a verdict_state string; "
            "the verdict argument (sealed Verdict union) is the only "
            "verdict-related input."
        )


# Suppress unused-import warning; pytest collects via parametrize
# decorators in some tests indirectly.
_ = pytest
