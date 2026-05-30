"""Tests for `whatifd.cache.keying.v2` — F-2.1 fix.

v2 adds `original_output_hash` and `replayed_output_hash` to
`CacheKeyComponents`. The load-bearing F-2.1 property is the new
test_replayed_output_change_changes_key — pre-fix, two scoring calls
with identical input but different replayed outputs hashed to the same
key and silently returned stale results.
"""

from __future__ import annotations

import dataclasses

import pytest

from whatifd.cache.keying.v2 import (
    CACHE_KEY_VERSION,
    CacheKeyComponents,
    build_cache_key,
)
from whatifd.exceptions import InvariantViolationError

_HEX = "ab" * 16

_SAMPLE = CacheKeyComponents(
    whatif_schema_version="0.2",
    whatif_scorer_adapter_version="0.2.1",
    scorer_type="inspect_ai.Faithfulness",
    scorer_package_version="0.3.5",
    judge_provider="anthropic",
    judge_model_id="claude-sonnet-4-6",
    judge_model_snapshot="20251001",
    rendered_prompt_hash="aa" * 16,
    rubric_hash="bb" * 16,
    scoring_parameters_hash="cc" * 16,
    score_case_serialization_version="v1",
    score_case_hash="dd" * 16,
    original_output_hash="ee" * 16,
    replayed_output_hash="ff" * 16,
)


class TestBuildCacheKey:
    def test_returns_versioned_format(self) -> None:
        key = build_cache_key(_SAMPLE)
        assert key.startswith(f"{CACHE_KEY_VERSION}:")
        assert len(key) == len(CACHE_KEY_VERSION) + 1 + 64

    def test_version_prefix_is_v2(self) -> None:
        assert CACHE_KEY_VERSION == "v2"

    def test_v1_and_v2_keys_never_collide(self) -> None:
        """The version prefix guarantees v1 and v2 keys are
        distinguishable even when their digests coincidentally
        match — storage code splits entries by prefix."""
        from whatifd.cache.keying.v1 import CACHE_KEY_VERSION as V1

        assert V1 != CACHE_KEY_VERSION
        v2_key = build_cache_key(_SAMPLE)
        assert not v2_key.startswith(f"{V1}:")


class TestF21RegressionOutputHashesInKey:
    """F-2.1: same scorer config, same trace_id/cohort/input, but
    DIFFERENT outputs must produce DISTINCT keys. v1 omitted output
    hashes and produced silent wrong deltas when the cache was
    enabled."""

    def test_replayed_output_change_changes_key(self) -> None:
        a = build_cache_key(_SAMPLE)
        b = build_cache_key(dataclasses.replace(_SAMPLE, replayed_output_hash="11" * 16))
        assert a != b, (
            "F-2.1: changing replayed_output_hash MUST change the cache "
            "key. Pre-fix this collision silently returned stale "
            "JudgeResult on re-run."
        )

    def test_original_output_change_changes_key(self) -> None:
        a = build_cache_key(_SAMPLE)
        b = build_cache_key(dataclasses.replace(_SAMPLE, original_output_hash="22" * 16))
        assert a != b

    def test_both_output_hashes_are_required_hex(self) -> None:
        # Cardinal #5: hash fields must be hex digests, never raw text.
        with pytest.raises(InvariantViolationError, match="original_output_hash"):
            dataclasses.replace(_SAMPLE, original_output_hash="not a hex digest")
        with pytest.raises(InvariantViolationError, match="replayed_output_hash"):
            dataclasses.replace(_SAMPLE, replayed_output_hash="ZZZZ")


class TestSensitivityToEveryComponent:
    """Mirror of v1's parametrized sensitivity test, widened to the two
    new v2 fields. Any field change must produce a different key — a
    future 'optimization' that dropped a field from the canonical-JSON
    input would surface here."""

    @pytest.mark.parametrize(
        "field_name,new_value",
        [
            ("whatif_schema_version", "9.9"),
            ("whatif_scorer_adapter_version", "9.9.9"),
            ("scorer_type", "different"),
            ("scorer_package_version", "9.9.9"),
            ("judge_provider", "different"),
            ("judge_model_id", "different"),
            ("judge_model_snapshot", "different-snapshot"),
            ("rendered_prompt_hash", "11" * 16),
            ("rubric_hash", "11" * 16),
            ("scoring_parameters_hash", "11" * 16),
            ("score_case_serialization_version", "v9"),
            ("score_case_hash", "11" * 16),
            ("original_output_hash", "11" * 16),
            ("replayed_output_hash", "11" * 16),
        ],
    )
    def test_every_field_affects_key(self, field_name: str, new_value: str | None) -> None:
        base = build_cache_key(_SAMPLE)
        mutated = build_cache_key(dataclasses.replace(_SAMPLE, **{field_name: new_value}))
        assert base != mutated, (
            f"Mutating {field_name} did NOT change the cache key. "
            "Either the field is missing from canonical_json_bytes "
            "input or the v2 component set is not aligned with the "
            "hash inputs."
        )
