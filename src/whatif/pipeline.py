"""Programmatic integration entry point — Phase 9A.1.

`run_pipeline(trace_source, *, delta_fn, floor, policy, runtime,
methodology, cache_summary) -> ReportV01` stitches the adapter →
cohort aggregation → verdict → projection path end-to-end.

## Phase 9A.1 scope and shortcuts

This sub-phase establishes the architectural plumbing. Two
deliberate shortcuts that follow-up sub-phases close:

- **Per-trace deltas come from a caller-supplied `delta_fn`**, not
  from running a real `Scorer` over (original, replayed) pairs.
  The stub's faithfulness is fixture-driven and the integration
  test controls the delta function. Phase 9A.2+ wires real paired
  scoring through the stub's `Scorer` once a Runner is available
  in scope.
- **CI bounds use empirical 5th/95th percentiles of the deltas**,
  not stratified bootstrap. Adequate for cardinal-#2 floor-passing
  Ship/Don't-Ship verdicts in tests; Phase 9A.3 (determinism) +
  the broader stats layer replace this with proper bootstrap.

Both shortcuts are documented at the call sites; the function
signature is the stable contract.

## What this function does NOT do

- Read the cache. The cache subsystem is exercised by
  `whatif.cache` unit tests; integration tests pass a pre-built
  `CacheSummary`.
- Build the manifest. Manifest construction (timestamps, env
  fingerprint, sensitive-unwrap drain) is the CLI's responsibility;
  integration tests pass a pre-built `RunManifest`.
- Run a real two-affirmation. Tests construct fixtures directly;
  the CLI surface enforces cardinal #7.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from whatif.adapters.protocols import RawTrace, TraceSource
from whatif.cache.summary import CacheSummary
from whatif.decision.verdict import compute_verdict
from whatif.report.models_v01 import ReportV01
from whatif.report.projection import project_to_report_v01
from whatif.types.cohort import CohortResult
from whatif.types.failure import FailureRecord
from whatif.types.manifest import RunManifest
from whatif.types.policy import DecisionPolicy, TrustFloor
from whatif.types.statistical import MethodologyDisclosure


@dataclass(frozen=True, slots=True)
class _CohortBuckets:
    """Per-cohort accumulator. Internal."""

    name: str
    selected: int
    deltas: tuple[float, ...]


def run_pipeline(
    trace_source: TraceSource,
    *,
    delta_fn: Callable[[RawTrace], float],
    floor: TrustFloor,
    policy: DecisionPolicy,
    runtime: RunManifest,
    methodology: MethodologyDisclosure,
    cache_summary: CacheSummary,
) -> ReportV01:
    """Drive the pipeline end-to-end and return a `ReportV01`.

    The entry point is adapter-agnostic: any concrete `TraceSource`
    that satisfies the Phase 4A.1 protocol works. v0.1 callers pass
    the synthetic stub from `whatif.adapters.stub`; Phase 9B will
    pass real Langfuse / Inspect AI adapters through the same
    function.
    """
    raw_traces = list(trace_source.iter_traces())
    buckets = _bucket_by_cohort(raw_traces, delta_fn=delta_fn)
    cohort_results = tuple(
        _cohort_result_from_bucket(b, policy=policy, floor=floor) for b in buckets
    )
    verdict = compute_verdict(cohort_results, floor, policy)
    failures: list[FailureRecord] = []
    return project_to_report_v01(
        verdict,
        failures=failures,
        cache_summary=cache_summary,
        methodology=methodology,
        runtime=runtime,
    )


def _bucket_by_cohort(
    traces: Iterable[RawTrace],
    *,
    delta_fn: Callable[[RawTrace], float],
) -> tuple[_CohortBuckets, ...]:
    """Group traces by `cohort` field and compute the per-trace
    delta for each. Skipped traces (`skip_reason is not None`) are
    counted toward `selected` but excluded from `deltas`."""
    by_name: dict[str, tuple[int, list[float]]] = {}
    for rt in traces:
        sel, deltas = by_name.setdefault(rt.cohort, (0, []))
        new_sel = sel + 1
        new_deltas = list(deltas)
        if rt.skip_reason is None:
            new_deltas.append(delta_fn(rt))
        by_name[rt.cohort] = (new_sel, new_deltas)
    return tuple(
        _CohortBuckets(name=name, selected=sel, deltas=tuple(deltas))
        for name, (sel, deltas) in sorted(by_name.items())
    )


def _cohort_result_from_bucket(
    bucket: _CohortBuckets,
    *,
    policy: DecisionPolicy,
    floor: TrustFloor,
) -> CohortResult:
    """Build a `CohortResult` from a per-cohort bucket. Counts
    improved / unchanged / regressed per `practical_delta_epsilon`;
    median + percentile CI from the deltas."""
    eps = policy.practical_delta_epsilon
    improved = sum(1 for d in bucket.deltas if d > eps)
    regressed = sum(1 for d in bucket.deltas if d < -eps)
    unchanged = len(bucket.deltas) - improved - regressed
    scored = len(bucket.deltas)
    replayed = scored  # 9A.1 shortcut: stub treats every selected trace as replayed

    median: str | None = None
    ci_lower: str | None = None
    ci_upper: str | None = None
    ci_computable = False
    ci_unavailable_reason: object = "sample_too_small"
    if scored >= floor.min_scored_per_required_cohort:
        median = f"{statistics.median(bucket.deltas):.3f}"
        # Empirical percentile CI — Phase 9A.1 shortcut. Real
        # stratified bootstrap lands later in the stats layer.
        sorted_deltas = sorted(bucket.deltas)
        lo_idx = max(0, int(0.05 * len(sorted_deltas)))
        hi_idx = min(len(sorted_deltas) - 1, int(0.95 * len(sorted_deltas)))
        ci_lower = f"{sorted_deltas[lo_idx]:.3f}"
        ci_upper = f"{sorted_deltas[hi_idx]:.3f}"
        ci_computable = True
        ci_unavailable_reason = None

    cohort = CohortResult(
        name=bucket.name,
        selected=bucket.selected,
        replayed=replayed,
        scored=scored,
        ci_computable=ci_computable,
        ci_unavailable_reason=ci_unavailable_reason,  # type: ignore[arg-type]
        median_delta=median,  # type: ignore[arg-type]
        ci_lower=ci_lower,  # type: ignore[arg-type]
        ci_upper=ci_upper,  # type: ignore[arg-type]
        floor_passed=True,
        floor_failures=[],
        improved_count=improved,
        unchanged_count=unchanged,
        regressed_count=regressed,
    )
    # Floor evaluation runs at compute_verdict time via
    # compute_cohort_floor_failures, but the CohortResult on the
    # input must already carry floor_passed correctly. Re-evaluate
    # against the floor here so the verdict sees the right state.
    from whatif.decision.floor import compute_cohort_floor_failures

    failures = compute_cohort_floor_failures(cohort, floor)
    return CohortResult(
        name=cohort.name,
        selected=cohort.selected,
        replayed=cohort.replayed,
        scored=cohort.scored,
        ci_computable=cohort.ci_computable,
        ci_unavailable_reason=cohort.ci_unavailable_reason,
        median_delta=cohort.median_delta,
        ci_lower=cohort.ci_lower,
        ci_upper=cohort.ci_upper,
        floor_passed=not failures,
        floor_failures=failures,
        improved_count=cohort.improved_count,
        unchanged_count=cohort.unchanged_count,
        regressed_count=cohort.regressed_count,
        ci_meaningful=cohort.ci_meaningful,
    )


__all__ = ["run_pipeline"]
