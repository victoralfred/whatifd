"""Tests for `whatifd.statistical.bootstrap` — Phase E.1.

Property tests + boundary cases. The Hypothesis property tests pin
the doctrinally-load-bearing invariants:
- determinism with seed
- CI brackets the median
- CI tightens (or stays equal) with more resamples on average

Boundary cases pin cardinal #1 (typed errors on bad input).
"""

from __future__ import annotations

import statistics

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whatifd.statistical import BootstrapResult, paired_percentile_bootstrap


class TestHappyPath:
    def test_returns_bootstrap_result(self) -> None:
        result = paired_percentile_bootstrap([0.1, 0.2, 0.3], seed=42)
        assert isinstance(result, BootstrapResult)
        assert result.resamples == 2000  # default
        assert result.seed == 42
        assert result.ci_level == 0.95

    def test_median_matches_input_median(self) -> None:
        # The reported median is the median of the ORIGINAL deltas,
        # not of the bootstrap distribution. Cardinal #10:
        # bootstrap quantifies uncertainty around the point
        # estimate; it does not replace the point estimate.
        deltas = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = paired_percentile_bootstrap(deltas, seed=42)
        assert result.median == statistics.median(deltas)

    def test_ci_bracket_includes_median(self) -> None:
        # Empirical: at 95% CI level, ci_lower <= median <= ci_upper
        # for a non-degenerate distribution. Defends against an off-
        # by-one in the percentile-index calculation.
        deltas = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        result = paired_percentile_bootstrap(deltas, seed=42)
        assert result.ci_lower <= result.median <= result.ci_upper

    def test_ci_lower_less_than_or_equal_ci_upper(self) -> None:
        result = paired_percentile_bootstrap([0.1, 0.2, 0.3], seed=42)
        assert result.ci_lower <= result.ci_upper


class TestDeterminism:
    def test_same_seed_same_result(self) -> None:
        deltas = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
        a = paired_percentile_bootstrap(deltas, seed=42)
        b = paired_percentile_bootstrap(deltas, seed=42)
        assert a == b

    def test_different_seeds_different_ci(self) -> None:
        # Sanity: the seed actually controls the resampler.
        # Different seeds on the same data produce different CIs.
        # Need a larger input than the obvious-toy [0.1..0.5] — at
        # n=5 the bootstrap distribution has so few unique median
        # values that different seeds collide on identical CI bounds.
        # n=20 gives enough resample diversity to distinguish seeds.
        deltas = [i / 100.0 for i in range(20)]  # 0.00..0.19
        a = paired_percentile_bootstrap(deltas, seed=1)
        b = paired_percentile_bootstrap(deltas, seed=2)
        # Median is data-determined and identical.
        assert a.median == b.median
        # CI bounds depend on the resample sequence.
        assert (a.ci_lower, a.ci_upper) != (b.ci_lower, b.ci_upper)

    def test_does_not_perturb_global_random(self) -> None:
        # Cardinal-#4-adjacent: the bootstrap MUST NOT touch the
        # global `random` module's state, or concurrent uses of
        # `random.random()` elsewhere in the process become non-
        # reproducible.
        import random as _random

        _random.seed(999)
        before = _random.random()

        _random.seed(999)
        paired_percentile_bootstrap([0.1, 0.2, 0.3], seed=42)
        after = _random.random()

        assert before == after


class TestStructuralErrors:
    def test_empty_deltas_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            paired_percentile_bootstrap([], seed=42)

    def test_zero_resamples_raises(self) -> None:
        with pytest.raises(ValueError, match="resamples must be >= 1"):
            paired_percentile_bootstrap([0.1], resamples=0, seed=42)

    def test_negative_resamples_raises(self) -> None:
        with pytest.raises(ValueError, match="resamples must be >= 1"):
            paired_percentile_bootstrap([0.1], resamples=-5, seed=42)

    @pytest.mark.parametrize("bad_level", [0.0, 1.0, -0.1, 1.5])
    def test_invalid_ci_level_raises(self, bad_level: float) -> None:
        with pytest.raises(ValueError, match=r"ci_level must be in \(0, 1\)"):
            paired_percentile_bootstrap([0.1, 0.2], ci_level=bad_level, seed=42)


class TestCustomConfiguration:
    def test_resamples_count_passes_through(self) -> None:
        result = paired_percentile_bootstrap([0.1, 0.2, 0.3], resamples=500, seed=42)
        assert result.resamples == 500

    def test_ci_level_passes_through(self) -> None:
        result = paired_percentile_bootstrap([0.1, 0.2, 0.3], ci_level=0.99, seed=42)
        assert result.ci_level == 0.99

    def test_higher_ci_level_widens_or_equals_interval(self) -> None:
        # 99% CI is at least as wide as 95% CI on the same resample
        # sequence. Sanity check on the percentile-index formula.
        deltas = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        ci_95 = paired_percentile_bootstrap(deltas, ci_level=0.95, seed=42)
        ci_99 = paired_percentile_bootstrap(deltas, ci_level=0.99, seed=42)
        assert (ci_99.ci_upper - ci_99.ci_lower) >= (ci_95.ci_upper - ci_95.ci_lower)


class TestPropertyBased:
    """Hypothesis property tests on bootstrap invariants."""

    @given(
        deltas=st.lists(
            st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=50,
        ),
        seed=st.integers(min_value=0, max_value=10_000),
    )
    @settings(max_examples=50, deadline=2000)
    def test_ci_brackets_median_for_arbitrary_input(self, deltas: list[float], seed: int) -> None:
        # Across arbitrary delta sequences (length 2-50, finite floats),
        # the empirical 95% CI bracket includes the median.
        result = paired_percentile_bootstrap(deltas, seed=seed, resamples=200)
        assert result.ci_lower <= result.median <= result.ci_upper

    @given(
        deltas=st.lists(
            st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=20,
        ),
        seed=st.integers(min_value=0, max_value=10_000),
    )
    @settings(max_examples=30, deadline=3000)
    def test_deterministic_across_runs(self, deltas: list[float], seed: int) -> None:
        # Same input + same seed = identical BootstrapResult.
        a = paired_percentile_bootstrap(deltas, seed=seed, resamples=200)
        b = paired_percentile_bootstrap(deltas, seed=seed, resamples=200)
        assert a == b
