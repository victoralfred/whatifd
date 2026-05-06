"""Shared fixture builders for `tests/unit/whatif/report/`.

`test_models_v01.py` (Phase 5.1) and `test_projection.py` (Phase 5.2)
both need fully-typed instances of the dependent sub-shapes
(`CohortResult`, `CacheSummary`, `MethodologyDisclosure`, `RunManifest`,
etc.). Centralizing the builders here:

- Avoids drift between the two test files' fixture shapes.
- Gives a single place to update when a sub-shape adds a required
  field (one builder edit, not N).
- Keeps individual test files focused on the assertion they're
  pinning, not on the construction boilerplate.

Each builder is a no-arg factory returning a known-good instance,
matching the pattern Phase 3.x test files used internally
(`_components()` in `test_v1.py`, `_summary()` in `test_summary.py`).
"""

from __future__ import annotations

from whatif.cache.summary import CachePolicySnapshot, CacheSummary
from whatif.types.cohort import CohortResult
from whatif.types.manifest import EnvironmentFingerprint, RunManifest
from whatif.types.policy import DecisionPolicy, PrimaryEndpoint, TrustFloor
from whatif.types.primitives import DecimalString
from whatif.types.statistical import (
    BootstrapMethodDisclosure,
    EffectSizeDisclosure,
    JudgeMethodDisclosure,
    MethodologyDisclosure,
    MultiplicityDisclosure,
)


def trust_floor() -> TrustFloor:
    return TrustFloor()


def decision_policy() -> DecisionPolicy:
    return DecisionPolicy(
        primary_endpoints=(
            PrimaryEndpoint(
                cohort="failure",
                direction="improvement_above_threshold",
            ),
        ),
    )


def cohort(name: str = "failure") -> CohortResult:
    return CohortResult(
        name=name,
        selected=10,
        replayed=10,
        scored=10,
        ci_computable=True,
        ci_unavailable_reason=None,
        median_delta=DecimalString("0.250"),
        ci_lower=DecimalString("0.150"),
        ci_upper=DecimalString("0.350"),
        floor_passed=True,
    )


def cache_summary() -> CacheSummary:
    return CacheSummary(
        schema_version="v1",
        key_version="v1",
        mode="on",
        storage_profile="normalized_result_only",
        storage_path=".whatif/cache",
        hits=8,
        misses=2,
        writes=2,
        stale_hits=0,
        corrupted_entries=0,
        policy=CachePolicySnapshot(
            mode="on",
            warn_after_days=30,
            block_after_days=90,
            storage_profile="normalized_result_only",
        ),
    )


def methodology() -> MethodologyDisclosure:
    return MethodologyDisclosure(
        unit_of_analysis="paired_trace_delta",
        primary_metric="faithfulness",
        primary_endpoints=("failure_improvement_above_0.50",),
        cohorts=("failure", "baseline"),
        bootstrap=BootstrapMethodDisclosure(
            method="paired_percentile_bootstrap",
            resamples=10000,
            seed=42,
            sample_unit="paired_trace_delta",
            ci_level=DecimalString("0.95"),
            cluster_key=None,
            assumptions=("trace_independence",),
        ),
        multiplicity=MultiplicityDisclosure(
            primary_endpoint_count=1,
            correction="none",
            reason="single primary metric per cohort; no correction applied",
        ),
        judge=JudgeMethodDisclosure(
            scorer="inspect_ai.Faithfulness",
            scorer_version="0.3.5",
            judge_provider="anthropic",
            judge_model="claude-sonnet-4-6",
            judge_model_version="20251001",
            rendered_prompt_hash="aa" * 32,
            rubric_hash="bb" * 32,
            scorer_cache_enabled=True,
            scorer_cache_mode="on",
            scorer_cache_hits=8,
            scorer_cache_misses=2,
            reproducibility_addressed=True,
            reliability_measured=False,
            validity_measured=False,
            calibration_measured=False,
            bias_audit_measured=False,
        ),
        effect_size=EffectSizeDisclosure(
            practical_delta=DecimalString("0.050"),
            practical_delta_source="policy",
            judge_noise_floor=None,
        ),
        per_trace_inference="descriptive_only",
        causal_claim_scope="associated_under_cached_tool_replay",
    )


def runtime() -> RunManifest:
    return RunManifest(
        experiment_id="exp-001",
        started_at="2026-05-06T10:00:00Z",
        finished_at="2026-05-06T10:01:00Z",
        duration_ms=60000,
        whatif_version="0.0.1",
        config_hash="cc" * 32,
        selection_seed=42,
        source="langfuse://test",
        target="my_agent.replay:run",
        trust_floor=trust_floor(),
        decision_policy=decision_policy(),
        environment=EnvironmentFingerprint(
            python="3.13.0",
            platform="linux-x86_64",
            whatif_version="0.0.1",
        ),
    )
