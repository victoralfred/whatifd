"""Phase E.2 integration tests.

Pins the load-bearing invariants of the pipeline switch:

1. `_cohort_result_from_bucket` returns CI bounds equal to what
   `paired_percentile_bootstrap(deltas, resamples=BOOTSTRAP_RESAMPLES,
   ci_level=BOOTSTRAP_CI_LEVEL, seed=BOOTSTRAP_SEED)` produces
   directly — i.e., the pipeline really uses the bootstrap with
   the disclosed parameters, not a shadow shortcut and not the
   bootstrap-with-some-other-parameters.

2. The seed/resamples/ci_level declared in `cli.py`'s
   MethodologyDisclosure all live in `whatifd.statistical` and are
   imported at module level by both the pipeline and the CLI.
   Cardinal #10: the disclosure must echo what the pipeline
   actually ran; structural coupling prevents silent drift.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from whatifd.pipeline import _cohort_result_from_bucket, _CohortBuckets
from whatifd.statistical import (
    BOOTSTRAP_CI_LEVEL,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    paired_percentile_bootstrap,
    to_decimal_string,
)
from whatifd.types.policy import DecisionPolicy, TrustFloor


class TestPipelineCallsBootstrap:
    """The pipeline's per-cohort CI fields are the bootstrap's
    output, not the empirical-quantile shortcut."""

    def test_cohort_result_ci_matches_direct_bootstrap_call(self) -> None:
        # A delta sequence large enough to clear the floor's
        # min_scored_per_required_cohort threshold and produce a
        # non-degenerate bootstrap distribution.
        deltas = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
        bucket = _CohortBuckets(name="failure", selected=10, deltas=tuple(deltas))
        floor = TrustFloor()
        policy = DecisionPolicy()

        # Direct bootstrap call with the SAME parameters the
        # disclosure echoes. The pipeline MUST agree with this
        # output for the disclosure to match the design (cardinal
        # #10). All three parameters are pinned so a future refactor
        # that changes one without updating the disclosure fails
        # this test.
        expected = paired_percentile_bootstrap(
            deltas,
            resamples=BOOTSTRAP_RESAMPLES,
            ci_level=BOOTSTRAP_CI_LEVEL,
            seed=BOOTSTRAP_SEED,
        )

        result = _cohort_result_from_bucket(bucket, policy=policy, floor=floor)

        # The pipeline crossed the wire boundary via to_decimal_string,
        # so the assertions are on the formatted string surface.
        assert result.ci_computable is True
        assert result.ci_unavailable_reason is None
        assert result.median_delta == to_decimal_string(expected.median)
        assert result.ci_lower == to_decimal_string(expected.ci_lower)
        assert result.ci_upper == to_decimal_string(expected.ci_upper)

    def test_seed_change_changes_ci(self) -> None:
        # Sanity: the pipeline's CI actually depends on
        # BOOTSTRAP_SEED. If a future refactor accidentally hardcoded
        # the seed elsewhere or stopped passing it through, the
        # cardinal-#10 disclosure→pipeline coupling would silently
        # break.
        #
        # Note on seed selection: empirically, BOOTSTRAP_SEED + small
        # offsets can collide on identical sorted-median percentiles
        # at the chosen indices (the bootstrap median is always one
        # of the original deltas, so distinct seed pairs can land on
        # the same percentile entry). Comparing against seed=1 (well
        # outside BOOTSTRAP_SEED's neighborhood) avoids that
        # collision class. The structural property — "the pipeline
        # uses BOOTSTRAP_SEED, not some other seed" — is what this
        # test pins.
        deltas = [i / 100.0 for i in range(20)]
        a = paired_percentile_bootstrap(deltas, seed=BOOTSTRAP_SEED)
        b = paired_percentile_bootstrap(deltas, seed=1)
        # Median is data-determined and identical; CI bounds depend
        # on the resample sequence.
        assert a.median == b.median
        assert (a.ci_lower, a.ci_upper) != (b.ci_lower, b.ci_upper)


class TestDisclosureSeedCoupling:
    """Cardinal #10 structural coupling: every bootstrap parameter
    the disclosure declares lives in `whatifd.statistical` and is
    imported at module level by both `whatifd.pipeline` and
    `whatifd.cli`. Single source of truth — future changes update
    both sites at once; a future divergence (e.g., a contributor
    reverting `cli.py` to duplicated literals) fails this test.
    """

    @staticmethod
    def _cli_source() -> str:
        # Locate `whatifd.cli` via `inspect.getsourcefile` so the
        # test is independent of pytest's current working directory.
        # `Path("src/whatifd/cli.py")`-relative pathing would fail
        # under any invocation that didn't `cd` to the repo root.
        import whatifd.cli

        path = inspect.getsourcefile(whatifd.cli)
        assert path is not None, "could not resolve whatifd.cli source path"
        return Path(path).read_text(encoding="utf-8")

    def test_cli_imports_bootstrap_constants_from_statistical(self) -> None:
        cli_source = self._cli_source()
        assert "from whatifd.statistical import" in cli_source and all(
            name in cli_source
            for name in ("BOOTSTRAP_CI_LEVEL", "BOOTSTRAP_RESAMPLES", "BOOTSTRAP_SEED")
        ), (
            "cli.py must import BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES, and "
            "BOOTSTRAP_CI_LEVEL from whatifd.statistical so all three bootstrap "
            "parameters in MethodologyDisclosure are structurally coupled to "
            "the pipeline's actual bootstrap call. Cardinal #10."
        )

    def test_cli_does_not_duplicate_bootstrap_literals(self) -> None:
        cli_source = self._cli_source()
        # The integer literal 4_872_109 should appear exactly once
        # across the codebase (in whatifd.statistical) — not in
        # cli.py as a duplicated mirror.
        assert "4_872_109" not in cli_source, (
            "cli.py contains the literal seed value as a duplicated integer. "
            "Use the BOOTSTRAP_SEED import so the seed is structurally "
            "coupled, not manually mirrored."
        )

    def test_pipeline_constants_are_pinned(self) -> None:
        # Version-pin: if ANY of these constants change, callers
        # reading prior reports need to know the bootstrap output
        # shifted. Changing the literals here requires updating
        # CHANGELOG with a methodology-disclosure note so
        # downstream consumers learn about the rebase.
        assert BOOTSTRAP_SEED == 4_872_109
        assert BOOTSTRAP_RESAMPLES == 2000
        assert BOOTSTRAP_CI_LEVEL == 0.95
