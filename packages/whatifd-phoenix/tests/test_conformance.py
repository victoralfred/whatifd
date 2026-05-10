"""`PhoenixTraceSource` conformance test (mocked spans_provider).

Runs the parent repo's `TraceSourceConformance` harness against a
synthetic OpenInference-shaped span fixture. No network. Real-Phoenix
recorded smoke (against arize-phoenix-client) is deferred to v0.3
when the cassette infrastructure for Phoenix's HTTP API lands.
"""

from __future__ import annotations

import pytest
from conformance import TraceSourceConformance  # type: ignore[import-not-found]
from whatifd.adapters import TraceSource

from whatifd_phoenix import PhoenixTraceSource


def _classify_baseline(_spans: list[dict[str, object]]) -> str:
    return "baseline"


def _make_root_span(
    trace_id: str, *, user_input: str = "hello", llm_output: str = "world"
) -> dict[str, object]:
    """Construct a synthetic root span with OpenInference attributes."""
    return {
        "context.trace_id": trace_id,
        "parent_id": None,
        "openinference.span.kind": "CHAIN",
        "input.value": user_input,
        "output.value": llm_output,
        "user.id": f"user-{trace_id}",
        "session.id": f"session-{trace_id}",
        "model.name": "claude-haiku-4-5",
    }


def _make_child_span(trace_id: str, parent_id: str = "root") -> dict[str, object]:
    return {
        "context.trace_id": trace_id,
        "parent_id": parent_id,
        "openinference.span.kind": "TOOL",
        "tool.name": "search",
    }


class TestPhoenixTraceSource(TraceSourceConformance):
    # Override the base class's `__test__ = False` so pytest collects
    # the inherited test_* methods against this concrete adapter.
    __test__ = True

    @pytest.fixture
    def trace_source(self) -> TraceSource:
        spans = [
            _make_root_span("trace-1", user_input="what's the weather?", llm_output="sunny"),
            _make_child_span("trace-1"),
            _make_root_span("trace-2", user_input="define entropy", llm_output="disorder"),
        ]
        return PhoenixTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )


# ---------------------------------------------------------------------------
# Adapter-specific behavior (beyond the conformance harness)
# ---------------------------------------------------------------------------


class TestSpanGrouping:
    """Phoenix-specific behavior: spans grouped by trace_id, root
    span identified, projection drops input/output from metadata."""

    def test_groups_spans_by_trace_id(self) -> None:
        spans = [
            _make_root_span("t-1"),
            _make_child_span("t-1"),
            _make_root_span("t-2"),
            _make_child_span("t-2"),
        ]
        source = PhoenixTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        traces = list(source.iter_traces())
        assert len(traces) == 2
        assert {t.trace_id for t in traces} == {"t-1", "t-2"}

    def test_skips_spans_without_trace_id(self) -> None:
        # Defensive: a malformed span without a trace_id is dropped
        # rather than crashing the iteration.
        spans = [
            _make_root_span("good"),
            {"parent_id": None, "input.value": "no-trace-id-here"},
        ]
        source = PhoenixTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        traces = list(source.iter_traces())
        assert len(traces) == 1
        assert traces[0].trace_id == "good"

    def test_root_span_provides_user_content(self) -> None:
        spans = [_make_root_span("t-1", user_input="Q?", llm_output="A.")]
        source = PhoenixTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        # Sensitive[T] doesn't expose its value via repr; check via
        # the audited unwrap path.
        assert trace.user_message.unwrap(reason="conformance test").endswith("Q?")
        assert trace.original_response.unwrap(reason="conformance test").endswith("A.")

    def test_metadata_excludes_input_output_attrs(self) -> None:
        spans = [_make_root_span("t-1")]
        source = PhoenixTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        # input.value and output.value are wrapped as Sensitive[T]
        # at the user_message / original_response slots; they MUST
        # NOT also leak into metadata (would double-expose user
        # content under cardinal #5).
        assert "input.value" not in trace.metadata
        assert "output.value" not in trace.metadata
        # Tooling attributes should still be present.
        assert "model.name" in trace.metadata
        assert trace.metadata["model.name"] == "claude-haiku-4-5"

    def test_classifier_receives_full_span_list(self) -> None:
        # Cohort classification often depends on non-root spans
        # (e.g., a tool span that errored, a tag attribute on a
        # specific child). The classifier callable receives the
        # full span list, not just the root.
        captured: list[list[dict[str, object]]] = []

        def capturing_classifier(spans: list[dict[str, object]]) -> str:
            captured.append(spans)
            return "baseline"

        spans = [_make_root_span("t-1"), _make_child_span("t-1")]
        source = PhoenixTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=capturing_classifier,
        )
        list(source.iter_traces())
        assert len(captured) == 1
        assert len(captured[0]) == 2  # both spans visible to classifier

    def test_max_traces_caps_iteration(self) -> None:
        spans = [_make_root_span(f"t-{i}") for i in range(10)]
        source = PhoenixTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
            max_traces=3,
        )
        assert len(list(source.iter_traces())) == 3


class TestAdapterMetadata:
    def test_adapter_id_is_phoenix(self) -> None:
        source = PhoenixTraceSource(
            spans_provider=lambda: [],
            cohort_classifier=_classify_baseline,
        )
        meta = source.adapter_metadata()
        assert meta.adapter_id == "phoenix"

    def test_explicit_sdk_version_passes_through(self) -> None:
        source = PhoenixTraceSource(
            spans_provider=lambda: [],
            cohort_classifier=_classify_baseline,
            sdk_version="1.5.0-test",
        )
        assert source.adapter_metadata().sdk_version == "1.5.0-test"


class TestClusterKeySupport:
    def test_no_cluster_keys_in_v0_2(self) -> None:
        # Cardinal #10: empty `available_keys` until v0.3 adds
        # explicit per-attribute opt-in. Mining `user.id` /
        # `session.id` from spans without operator declaration
        # would be an unannounced inferential commitment.
        source = PhoenixTraceSource(
            spans_provider=lambda: [],
            cohort_classifier=_classify_baseline,
        )
        assert source.cluster_key_support().available_keys == ()
