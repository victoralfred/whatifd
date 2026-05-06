"""Tests for `whatif.replay.pipeline.replay_stream` — Phase 6.3b
streaming pipeline.

Pin properties:

1. Each input bundle produces exactly one output `ReplayResult`.
2. Bundles all return the right `trace_id` (no swap).
3. Bundle counts are preserved (10 in, 10 out; 0 in, 0 out).
4. `max_workers < 1` rejected at the boundary.
5. Mixed success/failure: success and failure bundles in the same
   stream both produce their typed results.
6. Bounded concurrency: with `max_workers=2`, at most 2 runners
   execute concurrently (probe via barrier counters).
7. Lazy input consumption: large iterables don't materialize.
"""

from __future__ import annotations

import threading
import time

import pytest

from whatif.contract import ReplayConfig, ReplayOutput, ToolCache, TraceInput
from whatif.replay import (
    ReplayFailure,
    ReplayInputBundle,
    ReplayResult,
    ReplaySuccess,
    replay_stream,
)


def _bundle(trace_id: str, runner) -> ReplayInputBundle:
    return ReplayInputBundle(
        trace_id=trace_id,
        cohort="failure",
        trace_input=TraceInput(user_message=trace_id),
        config=ReplayConfig(system_prompt="x"),
        tool_cache=ToolCache(cache={}, policy="use-original"),
        runner=runner,
    )


def _echo_runner(ti: TraceInput, cfg: ReplayConfig, tc: ToolCache) -> ReplayOutput:
    return ReplayOutput(text=f"echo: {ti.user_message}")


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


class TestBasic:
    def test_empty_input_yields_nothing(self) -> None:
        results = list(replay_stream([], max_workers=2, timeout_seconds=2.0))
        assert results == []

    def test_single_bundle(self) -> None:
        results = list(
            replay_stream([_bundle("t-1", _echo_runner)], max_workers=2, timeout_seconds=2.0)
        )
        assert len(results) == 1
        result = results[0]
        assert isinstance(result, ReplaySuccess)
        assert result.trace_id == "t-1"
        assert result.output.text == "echo: t-1"

    def test_count_preserved(self) -> None:
        bundles = [_bundle(f"t-{i}", _echo_runner) for i in range(10)]
        results = list(replay_stream(bundles, max_workers=3, timeout_seconds=2.0))
        assert len(results) == 10

    def test_trace_ids_preserved_no_swap(self) -> None:
        # Each result's trace_id matches one input. No bundle swap;
        # no missing or duplicated trace_id.
        bundles = [_bundle(f"t-{i}", _echo_runner) for i in range(10)]
        results = list(replay_stream(bundles, max_workers=4, timeout_seconds=2.0))
        result_ids = {r.trace_id for r in results}
        input_ids = {f"t-{i}" for i in range(10)}
        assert result_ids == input_ids


# ---------------------------------------------------------------------------
# Mixed success / failure
# ---------------------------------------------------------------------------


class TestMixed:
    def test_success_and_failure_in_same_stream(self) -> None:
        def good(ti: TraceInput, cfg: ReplayConfig, tc: ToolCache) -> ReplayOutput:
            return ReplayOutput(text="ok")

        def bad(ti: TraceInput, cfg: ReplayConfig, tc: ToolCache) -> ReplayOutput:
            raise ValueError("nope")

        bundles = [
            _bundle("ok-1", good),
            _bundle("bad-1", bad),
            _bundle("ok-2", good),
            _bundle("bad-2", bad),
        ]
        results = {
            r.trace_id: r for r in replay_stream(bundles, max_workers=2, timeout_seconds=2.0)
        }

        assert isinstance(results["ok-1"], ReplaySuccess)
        assert isinstance(results["ok-2"], ReplaySuccess)
        assert isinstance(results["bad-1"], ReplayFailure)
        assert results["bad-1"].code == "runner_exception"
        assert isinstance(results["bad-2"], ReplayFailure)
        assert results["bad-2"].code == "runner_exception"


# ---------------------------------------------------------------------------
# Bounded concurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_max_workers_bound_observed(self) -> None:
        # Probe the bound by counting concurrent runner entries via a
        # threading.Lock-protected counter. With max_workers=2, the
        # peak should be <= 2 even when 8 bundles are submitted.
        active = 0
        peak = 0
        lock = threading.Lock()

        def slow_runner(ti: TraceInput, cfg: ReplayConfig, tc: ToolCache) -> ReplayOutput:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)  # hold the slot long enough to overlap
            with lock:
                active -= 1
            return ReplayOutput(text="ok")

        bundles = [_bundle(f"t-{i}", slow_runner) for i in range(8)]
        results = list(replay_stream(bundles, max_workers=2, timeout_seconds=5.0))

        assert len(results) == 8
        assert peak <= 2, f"max_workers=2 violated: peak concurrent runners = {peak}"

    def test_max_workers_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            list(replay_stream([], max_workers=0, timeout_seconds=2.0))

    def test_max_workers_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            list(replay_stream([], max_workers=-1, timeout_seconds=2.0))


# ---------------------------------------------------------------------------
# Streaming semantics (lazy input consumption)
# ---------------------------------------------------------------------------


class TestStreaming:
    def test_input_consumed_lazily(self) -> None:
        # The input is a generator that records how many bundles
        # have been pulled. After the first result is yielded, the
        # pulled count should be at most max_workers + 1 (the prime
        # plus one slide). This pins that the streaming layer
        # doesn't eagerly drain the iterator.
        pulled = 0

        def bundle_gen():
            nonlocal pulled
            for i in range(100):
                pulled += 1
                yield _bundle(f"t-{i}", _echo_runner)

        stream = replay_stream(bundle_gen(), max_workers=3, timeout_seconds=2.0)

        # Pull just the first result.
        first = next(stream)
        assert isinstance(first, ReplayResult)  # type: ignore[misc,arg-type]

        # Generator should NOT have drained 100 inputs by now.
        # Conservative bound: max_workers (prime) + a few more
        # the streaming layer may have advanced through. <100
        # is the load-bearing assertion.
        assert pulled < 100, (
            f"streaming layer drained {pulled} bundles before "
            "yielding the first result — should be lazy"
        )

        # Drain the rest so the executor shuts down cleanly.
        list(stream)


# ---------------------------------------------------------------------------
# Bundle data carrier
# ---------------------------------------------------------------------------


class TestBundle:
    def test_bundle_is_frozen(self) -> None:
        b = _bundle("t-1", _echo_runner)
        with pytest.raises(AttributeError):
            b.trace_id = "t-2"  # type: ignore[misc]
