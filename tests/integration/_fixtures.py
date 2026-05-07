"""Shared fixtures for Phase 9A integration tests.

Each scenario builder produces a `(StubTraceSource, delta_fn,
RunManifest, MethodologyDisclosure, CacheSummary)` tuple ready to
feed into `whatif.pipeline.run_pipeline`. Future sub-phases (9A.2)
extend this module with the remaining walkthrough scenarios; the
current module ships scenario 1 (Clean Ship) only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from whatif.adapters.protocols import RawTrace
from whatif.adapters.stub import StubTraceSource, StubTraceSpec
from whatif.cache.summary import CachePolicySnapshot, CacheSummary
from whatif.types.manifest import EnvironmentFingerprint, RunManifest
from whatif.types.policy import DecisionPolicy, TrustFloor
from whatif.types.statistical import (
    BootstrapMethodDisclosure,
    EffectSizeDisclosure,
    JudgeMethodDisclosure,
    MethodologyDisclosure,
    MultiplicityDisclosure,
)


@dataclass(frozen=True, slots=True)
class IntegrationFixture:
    trace_source: StubTraceSource
    delta_fn: Callable[[RawTrace], float]
    runtime: RunManifest
    methodology: MethodologyDisclosure
    cache_summary: CacheSummary


def _default_runtime(*, floor: TrustFloor, policy: DecisionPolicy) -> RunManifest:
    return RunManifest(
        experiment_id="integration-test",
        started_at="2026-05-07T00:00:00Z",
        finished_at="2026-05-07T00:00:01Z",
        duration_ms=1000,
        whatif_version="0.1.0",
        config_hash="0" * 64,
        selection_seed=42,
        source="stub",
        target="stub",
        trust_floor=floor,
        decision_policy=policy,
        environment=EnvironmentFingerprint(
            python="3.13.0",
            platform="linux",
            whatif_version="0.1.0",
        ),
    )


def _default_methodology() -> MethodologyDisclosure:
    return MethodologyDisclosure(
        unit_of_analysis="paired_trace_delta",
        primary_metric="faithfulness",
        primary_endpoints=("failure.faithfulness", "baseline.faithfulness"),
        cohorts=("failure", "baseline"),
        bootstrap=BootstrapMethodDisclosure(
            method="paired_percentile_bootstrap",
            resamples=0,
            seed=42,
            sample_unit="paired_trace_delta",
            ci_level="0.950",
            cluster_key=None,
            assumptions=("trace_independence",),
            unavailable_reason=None,
        ),
        multiplicity=MultiplicityDisclosure(
            primary_endpoint_count=2,
            correction="none",
            reason="single primary metric per cohort; no correction applied",
        ),
        judge=JudgeMethodDisclosure(
            scorer="stub",
            scorer_version="0.1.0",
            judge_provider="stub",
            judge_model="stub-judge",
            judge_model_version=None,
            rendered_prompt_hash="0" * 16,
            rubric_hash="0" * 16,
            scorer_cache_enabled=False,
            scorer_cache_mode="off",
            scorer_cache_hits=0,
            scorer_cache_misses=0,
            reproducibility_addressed=True,
            reliability_measured=False,
            validity_measured=False,
            calibration_measured=False,
            bias_audit_measured=False,
        ),
        effect_size=EffectSizeDisclosure(
            practical_delta="0.050",
            practical_delta_source="policy",
            judge_noise_floor=None,
        ),
        per_trace_inference="descriptive_only",
        causal_claim_scope="associated_under_cached_tool_replay",
    )


def _default_cache_summary() -> CacheSummary:
    return CacheSummary(
        schema_version="v1",
        key_version="v1",
        mode="off",
        storage_profile="normalized_result_only",
        storage_path=".whatif/cache",
        hits=0,
        misses=0,
        writes=0,
        stale_hits=0,
        corrupted_entries=0,
        policy=CachePolicySnapshot(
            mode="off",
            warn_after_days=30,
            block_after_days=90,
            storage_profile="normalized_result_only",
        ),
        policy_violations=(),
        oldest_hit_age_days=None,
        models_distribution=MappingProxyType({}),
    )


def scenario_clean_ship() -> IntegrationFixture:
    """Walkthrough scenario 1 — Clean Ship.

    Failure cohort: 20 traces, 14 improved (delta > epsilon),
    6 unchanged. Baseline cohort: 20 traces, all near-zero delta.
    """
    failures = [
        StubTraceSpec(
            trace_id=f"f-{i:02d}",
            user_message=f"failure prompt {i}",
            original_response=f"failure response {i}",
            cohort="failure",
        )
        for i in range(20)
    ]
    baselines = [
        StubTraceSpec(
            trace_id=f"b-{i:02d}",
            user_message=f"baseline prompt {i}",
            original_response=f"baseline response {i}",
            cohort="baseline",
        )
        for i in range(20)
    ]
    source = StubTraceSource(specs=[*failures, *baselines])

    def delta_fn(rt: RawTrace) -> float:
        # Failure cohort: 14 of 20 improved by 0.20; 6 unchanged at 0.0.
        # Baseline cohort: all near-zero (0.01 — under epsilon=0.05).
        if rt.cohort == "failure":
            idx = int(rt.trace_id.split("-")[1])
            return 0.20 if idx < 14 else 0.0
        return 0.01

    floor = TrustFloor()
    policy = DecisionPolicy()
    return IntegrationFixture(
        trace_source=source,
        delta_fn=delta_fn,
        runtime=_default_runtime(floor=floor, policy=policy),
        methodology=_default_methodology(),
        cache_summary=_default_cache_summary(),
    )
