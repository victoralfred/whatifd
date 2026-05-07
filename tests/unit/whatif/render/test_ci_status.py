"""Tests for `whatif.render.ci_status.render_ci_status` — Phase 7.3.

Pin properties:

1. Each verdict gets the right glyph + label prefix.
2. Length budget: every produced string ≤ 80 visible chars.
3. Truncation uses `…` and preserves the verdict prefix intact.
4. Ship reason carries the failure / baseline cohort summary.
5. Don't Ship / Inconclusive reason comes from the highest-
   severity decision finding.
6. Inconclusive with no findings but a floor failure surfaces the
   floor rule.
"""

from __future__ import annotations

import dataclasses

import pytest

from whatif.decision.finding_codes import make_decision_finding
from whatif.render import render_ci_status
from whatif.report.projection import project_to_report_v01
from whatif.types.cohort import FloorFailure

from ..report._fixtures import (
    cache_summary,
    cohort,
    dont_ship,
    inconclusive,
    methodology,
    runtime,
    ship,
)


def _report_for(verdict, *, failures=None, decision_findings=None):
    """Project to a ReportV01 with optional finding override.

    The fixtures' verdict factories carry their own findings; for
    the CI-status tests we sometimes want to inject a specific
    finding to pin the reason path. project_to_report_v01 reads
    the verdict's findings field directly, so override the verdict
    via dataclasses.replace where needed.
    """
    return project_to_report_v01(
        verdict,
        failures=failures or [],
        cache_summary=cache_summary(),
        methodology=methodology(),
        runtime=runtime(),
    )


# ---------------------------------------------------------------------------
# Verdict glyph + label
# ---------------------------------------------------------------------------


class TestVerdictPrefix:
    def test_ship_glyph_and_label(self) -> None:
        line = render_ci_status(_report_for(ship()))
        assert line.startswith("✓ whatif: Ship —")

    def test_dont_ship_glyph_and_label(self) -> None:
        line = render_ci_status(_report_for(dont_ship()))
        assert line.startswith("✗ whatif: Don't Ship —")

    def test_inconclusive_glyph_and_label(self) -> None:
        line = render_ci_status(_report_for(inconclusive()))
        assert line.startswith("⚠ whatif: Inconclusive —")


# ---------------------------------------------------------------------------
# Length budget (≤ 80 chars)
# ---------------------------------------------------------------------------


class TestLengthBudget:
    def test_ship_within_budget(self) -> None:
        line = render_ci_status(_report_for(ship()))
        assert len(line) <= 80, f"Ship line {len(line)} chars: {line!r}"

    def test_dont_ship_within_budget(self) -> None:
        line = render_ci_status(_report_for(dont_ship()))
        assert len(line) <= 80, f"Don't Ship line {len(line)} chars: {line!r}"

    def test_inconclusive_within_budget(self) -> None:
        line = render_ci_status(_report_for(inconclusive()))
        assert len(line) <= 80, f"Inconclusive line {len(line)} chars: {line!r}"

    def test_long_finding_message_truncated_with_ellipsis(self) -> None:
        # A finding with a giant message must produce a within-
        # budget line. Verdict prefix stays intact; reason is
        # truncated with `…`. Severity comes from the registry
        # (cohort_systemic_failure → blocks_all).
        long_message = "x" * 200
        long_finding = make_decision_finding(
            code="cohort_systemic_failure",
            message=long_message,
            details={"cohort": "failure", "percent": 60, "code": "runner_timeout"},
            derived_from_failures=["failure_001"],
        )
        verdict = dataclasses.replace(dont_ship(), findings=(long_finding,))
        line = render_ci_status(_report_for(verdict))

        assert len(line) <= 80
        assert line.startswith("✗ whatif: Don't Ship — ")
        assert line.endswith("…")


# ---------------------------------------------------------------------------
# Reason source
# ---------------------------------------------------------------------------


class TestReasonSource:
    def test_ship_reason_summarizes_cohorts(self) -> None:
        line = render_ci_status(_report_for(ship()))
        # The ship() fixture's cohorts produce a "failures X/Y ↑,
        # baseline Z/Y stable" tail. Pin the structural shape, not
        # exact numbers (which are fixture-dependent).
        assert " ↑, baseline " in line
        assert "stable" in line

    def test_dont_ship_reason_uses_highest_severity_finding(self) -> None:
        # Two findings: one info (lowest) and one blocks_ship
        # (higher). Renderer must pick the blocks_ship message.
        # Severity is registry-driven; we pick codes for their
        # registered severity, not pass severity directly.
        f_low = make_decision_finding(
            code="improvement_observed",  # severity=info
            message="LOW-SEVERITY MESSAGE",
            details={"median_delta": "0.250", "threshold": "0.05"},
        )
        f_high = make_decision_finding(
            code="baseline_regression_above_threshold",  # severity=blocks_ship
            message="HIGH",
            details={"observed": "0.150", "threshold": "0.10"},
        )
        verdict = dataclasses.replace(dont_ship(), findings=(f_low, f_high))
        line = render_ci_status(_report_for(verdict))
        assert "HIGH" in line
        assert "LOW-SEVERITY MESSAGE" not in line


# ---------------------------------------------------------------------------
# Floor-failure fallback
# ---------------------------------------------------------------------------


class TestFloorFailureFallback:
    def test_inconclusive_with_floor_failure_surfaces_rule(self) -> None:
        # An Inconclusive whose findings list is empty must surface
        # the top floor-failure rule. Build a cohort with a floor
        # failure and inject it into an inconclusive verdict that
        # has no findings.
        floor_failure = FloorFailure(
            rule="min_scored_per_required_cohort",
            observed=3,
            threshold=5,
            severity="blocks_all",
        )
        c = dataclasses.replace(
            cohort("baseline"),
            floor_passed=False,
            floor_failures=[floor_failure],
        )
        verdict = dataclasses.replace(
            inconclusive(),
            cohort_results=(c,),
            findings=(),
        )
        line = render_ci_status(_report_for(verdict))
        # The floor-failure path produces a "<cohort> cohort below
        # floor (...)" reason. The exact rule name may be truncated
        # by the 80-char budget; assert the structural prefix +
        # observed/threshold numbers (which are short and survive).
        assert "baseline cohort below floor" in line
        assert "(3 < 5" in line


# ---------------------------------------------------------------------------
# Defensive boundary
# ---------------------------------------------------------------------------


class TestDefensiveBoundary:
    def test_unknown_verdict_state_raises_keyerror(self) -> None:
        # A `verdict_state` outside the closed Literal would have
        # been rejected at projection time, but pin the renderer's
        # behavior under direct mutation to ensure we don't
        # silently emit a bogus glyph. The KeyError surfaces the
        # contract violation rather than producing a garbage line.
        report = _report_for(ship())
        report = dataclasses.replace(report, verdict_state="bogus")  # type: ignore[arg-type]
        with pytest.raises(KeyError):
            render_ci_status(report)
