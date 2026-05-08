"""`InspectAIScorer` conformance test (mocked score_fn).

Runs the parent repo's `ScorerConformance` and
`StructuralFailureScorerConformance` harnesses against a fake
score function. No network. Per the package README: Inspect AI
is a local evaluation framework, not a hosted API — there is no
"Inspect AI host" to record cassettes against. Real-network proof
(model-provider HTTP calls) is Phase 9B's real-adapter smoke.

Test scaffolds below are intentionally NOT `frozen=True` /
`slots=True` nor `Protocol`-typed. The project's style for
production code (cardinal #6 typed boundaries) doesn't apply to
test fakes — these classes exist to be mutated in-fixture (e.g.,
`_FakeAsyncScoreFn.calls` appended to during the protocol-call
shape check) and rebound across test methods. If a future
contributor mechanically applies the production style to this
file, the conformance harness's auditing surface breaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from conformance import (  # type: ignore[import-not-found]
    ScorerConformance,
    StructuralFailureScorerConformance,
)
from whatif.adapters import Scorer
from whatif.contract import ScoreCase

from whatif_inspect_ai import InspectAIScorer


@dataclass
class _FakeScore:
    value: float | None
    explanation: str
    answer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[Any] = field(default_factory=list)


def _passthrough_score_fn(case: ScoreCase) -> _FakeScore:
    """Sync score_fn returning a non-None Score. The conformance
    harness's `test_score_returns_judge_result` accepts either a
    float or None; this fake always returns 0.85 so a regression
    that drops `score_value` to None for non-failing cases would
    show up in the harness's float-isinstance check."""
    return _FakeScore(value=0.85, explanation=f"passthrough rationale for {case.trace_id}")


def _none_score_fn(_case: ScoreCase) -> None:
    """score_fn returning None — exercises cardinal-#1 structural
    failure. Used by `StructuralFailureScorerConformance` subclass
    below."""
    return None


class TestInspectAIScorerConformance(ScorerConformance):
    __test__ = True

    @pytest.fixture
    def scorer(self) -> Scorer:
        return InspectAIScorer(
            score_fn=_passthrough_score_fn,
            judge_provider="anthropic",
            judge_model_id="claude-opus-4-7",
            rubric_id="test-rubric",
            rubric_text="Score 0-1 by passthrough quality.",
            sdk_version="0.3.217-test",
        )


class TestInspectAIScorerStructuralFailure(StructuralFailureScorerConformance):
    __test__ = True

    @pytest.fixture
    def scorer(self) -> Scorer:
        # score_fn returns None → cardinal #1 structural failure.
        # The variant inherits ScorerConformance, so the base-class
        # tests (isinstance, adapter_metadata, score-shape,
        # cache_key_components) all run on this fixture too.
        return InspectAIScorer(
            score_fn=_none_score_fn,
            judge_provider="anthropic",
            judge_model_id="claude-opus-4-7",
            rubric_id="test-rubric",
            rubric_text="Will return None.",
            sdk_version="0.3.217-test",
        )


class TestInspectAISpecificBehaviors:
    """Behaviors the generic harness doesn't cover — async score_fn
    handling, exception → None projection, non-numeric value
    coercion, cache-key determinism."""

    def _case(self, trace_id: str = "t-1", cohort: str = "failure") -> ScoreCase:
        from whatif.contract import ReplayOutput, TraceInput, TraceOutput

        return ScoreCase(
            trace_id=trace_id,
            cohort=cohort,  # type: ignore[arg-type]
            input=TraceInput(user_message="hello"),
            original_output=TraceOutput(text="orig"),
            replayed_output=ReplayOutput(text="replay"),
        )

    def test_async_score_fn_is_awaited(self) -> None:
        async def _async_fn(case: ScoreCase) -> _FakeScore:
            return _FakeScore(value=0.5, explanation=f"async rationale for {case.trace_id}")

        scorer = InspectAIScorer(
            score_fn=_async_fn,
            judge_provider="anthropic",
            judge_model_id="claude-opus-4-7",
            rubric_id="test",
            rubric_text="r",
        )
        result = scorer.score(self._case())
        assert result.score == 0.5

    def test_score_fn_exception_surfaces_as_none_score(self) -> None:
        # Cardinal #1: a score_fn that raises does NOT propagate;
        # it surfaces as JudgeResult(score=None) with a rationale
        # naming the exception type. The pipeline converts that
        # into a structured FailureRecord.
        def _raising(_case: ScoreCase) -> _FakeScore:
            raise RuntimeError("scorer outage")

        scorer = InspectAIScorer(
            score_fn=_raising,
            judge_provider="anthropic",
            judge_model_id="claude-opus-4-7",
            rubric_id="test",
            rubric_text="r",
        )
        result = scorer.score(self._case())
        assert result.score is None
        # Sensitive redacts repr; unwrap with reason for the test.
        unwrapped = result.rationale.unwrap(reason="conformance: exception-projection check")
        assert "RuntimeError" in unwrapped
        assert "scorer outage" in unwrapped

    def test_non_numeric_score_value_coerces_to_none(self) -> None:
        # An Inspect AI scorer that returns a non-numeric value
        # (e.g., a string label) projects to score=None instead of
        # crashing on float(). The pipeline gets the structured
        # signal.
        def _string_value(case: ScoreCase) -> _FakeScore:
            return _FakeScore(value="high", explanation="string label")  # type: ignore[arg-type]

        scorer = InspectAIScorer(
            score_fn=_string_value,
            judge_provider="anthropic",
            judge_model_id="claude-opus-4-7",
            rubric_id="test",
            rubric_text="r",
        )
        result = scorer.score(self._case())
        assert result.score is None

    def test_cache_key_components_deterministic(self) -> None:
        scorer = InspectAIScorer(
            score_fn=_passthrough_score_fn,
            judge_provider="anthropic",
            judge_model_id="claude-opus-4-7",
            rubric_id="rubric-A",
            rubric_text="rubric A text",
            sdk_version="0.3.217-test",
        )
        case = self._case()
        c1 = scorer.cache_key_components(case)
        c2 = scorer.cache_key_components(case)
        assert c1 == c2

    def test_cache_key_components_distinct_for_distinct_rubric(self) -> None:
        # A rubric edit MUST invalidate cache entries — different
        # rubric_text → different rubric_hash. Pin the contract so
        # a future refactor that drops rubric_text from the hash
        # input fails here.
        common = {
            "score_fn": _passthrough_score_fn,
            "judge_provider": "anthropic",
            "judge_model_id": "claude-opus-4-7",
            "rubric_id": "rubric-A",
            "sdk_version": "0.3.217-test",
        }
        scorer1 = InspectAIScorer(rubric_text="version 1", **common)
        scorer2 = InspectAIScorer(rubric_text="version 2", **common)
        case = self._case()
        assert (
            scorer1.cache_key_components(case).rubric_hash
            != scorer2.cache_key_components(case).rubric_hash
        )

    def test_adapter_metadata_sourced(self) -> None:
        scorer = InspectAIScorer(
            score_fn=_passthrough_score_fn,
            judge_provider="anthropic",
            judge_model_id="claude-opus-4-7",
            rubric_id="r",
            rubric_text="r",
            sdk_version="0.3.217-test",
        )
        meta = scorer.adapter_metadata()
        assert meta.adapter_id == "inspect_ai"
        assert meta.package_version  # non-empty
        assert meta.sdk_version == "0.3.217-test"

    def test_judge_rationale_is_sensitive(self) -> None:
        # Cardinal #5 pin at the package boundary: the rationale
        # field on every JudgeResult MUST be a Sensitive instance,
        # not a raw str. The conformance harness already checks
        # this on the success path; pin here on the explicit-None
        # and exception paths too.
        from whatif.types.sensitive import Sensitive

        for fn in (_none_score_fn, lambda _c: (_ for _ in ()).throw(RuntimeError("x"))):
            scorer = InspectAIScorer(
                score_fn=fn,
                judge_provider="anthropic",
                judge_model_id="claude-opus-4-7",
                rubric_id="r",
                rubric_text="r",
            )
            result = scorer.score(self._case())
            assert isinstance(result.rationale, Sensitive)
