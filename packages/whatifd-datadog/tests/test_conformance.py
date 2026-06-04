"""`DatadogTraceSource` conformance test (mocked spans_provider).

Runs the parent repo's `TraceSourceConformance` harness against a synthetic
Datadog LLM-Obs span fixture. No network. Real-Datadog recorded smoke
(against the Export API) is deferred to a follow-up when the cassette
infrastructure lands — see the R-1 residual in the integrations plan.
"""

from __future__ import annotations

import pytest
from conformance import TraceSourceConformance  # type: ignore[import-not-found]
from whatifd.adapters import TraceSource

from whatifd_datadog import DatadogTraceSource


def _classify_baseline(_spans: list[dict[str, object]]) -> str:
    return "baseline"


def _make_root_span(
    trace_id: str, *, user_input: str = "hello", llm_output: str = "world"
) -> dict[str, object]:
    """Construct a synthetic root span with Datadog LLM-Obs attributes.

    `input` / `output` use the `SearchedIO` `{value, messages}` shape the
    Export API returns.
    """
    return {
        "trace_id": trace_id,
        "span_id": f"root-{trace_id}",
        "parent_id": None,
        "span_kind": "agent",
        "name": "agent.run",
        "input": {"value": user_input},
        "output": {"value": llm_output},
        "user.id": f"user-{trace_id}",
        "session_id": f"session-{trace_id}",
        "model_name": "claude-haiku-4-5",
    }


def _make_child_span(trace_id: str, parent_id: str = "root") -> dict[str, object]:
    return {
        "trace_id": trace_id,
        "span_id": f"tool-{trace_id}",
        "parent_id": parent_id,
        "span_kind": "tool",
        "name": "search",
    }


class TestDatadogTraceSource(TraceSourceConformance):
    # Override the base class's `__test__ = False` so pytest collects the
    # inherited test_* methods against this concrete adapter.
    __test__ = True

    @pytest.fixture
    def trace_source(self) -> TraceSource:
        spans = [
            _make_root_span("trace-1", user_input="what's the weather?", llm_output="sunny"),
            _make_child_span("trace-1", parent_id="root-trace-1"),
            _make_root_span("trace-2", user_input="define entropy", llm_output="disorder"),
        ]
        return DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )


# ---------------------------------------------------------------------------
# Adapter-specific behavior (beyond the conformance harness)
# ---------------------------------------------------------------------------


class TestSpanGrouping:
    def test_groups_spans_by_trace_id(self) -> None:
        spans = [
            _make_root_span("t-1"),
            _make_child_span("t-1", parent_id="root-t-1"),
            _make_root_span("t-2"),
            _make_child_span("t-2", parent_id="root-t-2"),
        ]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        traces = list(source.iter_traces())
        assert len(traces) == 2
        assert {t.trace_id for t in traces} == {"t-1", "t-2"}

    @pytest.mark.parametrize("bad_trace_id", [None, "", 42, 3.14, b"bytes-id", []])
    def test_skips_spans_with_non_string_trace_id(self, bad_trace_id: object) -> None:
        spans = [
            _make_root_span("good"),
            {"trace_id": bad_trace_id, "parent_id": None, "input": {"value": "x"}},
        ]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        traces = list(source.iter_traces())
        assert len(traces) == 1
        assert traces[0].trace_id == "good"

    def test_root_span_provides_user_content(self) -> None:
        spans = [_make_root_span("t-1", user_input="Q?", llm_output="A.")]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert trace.user_message.unwrap(reason="conformance test") == "Q?"
        assert trace.original_response.unwrap(reason="conformance test") == "A."

    def test_searchedio_messages_fallback(self) -> None:
        # When `value` is absent, the projection concatenates message
        # `content` fields (cardinal #1: no silent drop).
        spans = [
            {
                "trace_id": "t-1",
                "parent_id": None,
                "span_kind": "agent",
                "input": {"messages": [{"role": "user", "content": "hi there"}]},
                "output": {"value": "ok"},
            }
        ]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert trace.user_message.unwrap(reason="io test") == "hi there"

    def test_pii_attributes_wrapped_at_boundary(self) -> None:
        from whatifd.types.sensitive import Sensitive

        spans = [_make_root_span("t-1")]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert isinstance(trace.metadata["user.id"], Sensitive)
        assert isinstance(trace.metadata["session_id"], Sensitive)
        assert isinstance(trace.metadata["model_name"], str)

    def test_metadata_excludes_input_output_attrs(self) -> None:
        spans = [_make_root_span("t-1")]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert "input" not in trace.metadata
        assert "output" not in trace.metadata
        assert trace.metadata["model_name"] == "claude-haiku-4-5"

    def test_max_traces_caps_iteration(self) -> None:
        spans = [_make_root_span(f"t-{i}") for i in range(10)]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
            max_traces=3,
        )
        assert len(list(source.iter_traces())) == 3


class TestToolSpansProjection:
    def test_non_root_spans_appear_in_tool_spans(self) -> None:
        spans = [
            _make_root_span("t-1"),
            _make_child_span("t-1", parent_id="root-t-1"),
            _make_child_span("t-1", parent_id="root-t-1"),
        ]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert len(trace.tool_spans) == 2

    def test_root_span_excluded_from_tool_spans(self) -> None:
        spans = [_make_root_span("t-1"), _make_child_span("t-1", parent_id="root-t-1")]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert len(trace.tool_spans) == 1
        assert trace.tool_spans[0].kind == "tool"
        assert trace.tool_spans[0].name == "search"

    def test_tool_span_content_wrapped_not_stripped(self) -> None:
        from whatifd.types.sensitive import Sensitive

        child_with_content = {
            "trace_id": "t-1",
            "parent_id": "root-t-1",
            "span_kind": "tool",
            "name": "search",
            "input": {"value": "user's secret query"},
            "output": {"value": "tool's secret response"},
        }
        spans = [_make_root_span("t-1"), child_with_content]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        span = trace.tool_spans[0]
        assert isinstance(span.input, Sensitive)
        assert isinstance(span.output, Sensitive)
        assert span.input.unwrap(reason="test") == "user's secret query"
        assert span.output.unwrap(reason="test") == "tool's secret response"

    def test_tool_span_pii_attributes_wrapped(self) -> None:
        from whatifd.types.sensitive import Sensitive

        child_with_pii = {
            "trace_id": "t-1",
            "parent_id": "root-t-1",
            "span_kind": "tool",
            "name": "search",
            "user.id": "u-7",
            "session_id": "s-42",
            "user.email": "leak@example.com",
        }
        spans = [_make_root_span("t-1"), child_with_pii]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        attrs = trace.tool_spans[0].attributes
        for key in ("user.id", "session_id", "user.email"):
            assert isinstance(attrs[key], Sensitive), f"{key} not wrapped"

    def test_tool_spans_empty_when_no_children(self) -> None:
        spans = [_make_root_span("t-1")]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert trace.tool_spans == []


class TestRootIdentificationCorrectness:
    """Cardinal #1: a child `llm` span whose parent_id was dropped upstream
    must NOT be picked as the trace root (it would surface the model prompt
    as the user's question). Only `agent` / `workflow` are root-kind
    fallbacks."""

    def test_llm_kind_without_parent_is_not_root(self) -> None:
        spans = [
            _make_root_span("t-1", user_input="user's question", llm_output="agent's answer"),
            {
                "trace_id": "t-1",
                "parent_id": None,  # simulated missing parent
                "span_kind": "llm",
                "input": {"value": "internal prompt to the model"},
                "output": {"value": "model raw completion"},
            },
        ]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        [trace] = list(source.iter_traces())
        assert trace.user_message.unwrap(reason="root-id test") == "user's question"


class TestSensitiveWrappingAtIngress:
    def test_classifier_sees_wrapped_child_input(self) -> None:
        from whatifd.types.sensitive import Sensitive

        captured: list[object] = []

        def capturing_classifier(spans: list[dict[str, object]]) -> str:
            for s in spans:
                if "input" in s:
                    captured.append(s["input"])
            return "baseline"

        child_with_input = _make_child_span("t-1", parent_id="root-t-1")
        child_with_input["input"] = {"value": "child-prompt-secret"}
        spans = [_make_root_span("t-1", user_input="root-prompt"), child_with_input]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=capturing_classifier,
        )
        list(source.iter_traces())
        assert len(captured) == 2
        assert all(isinstance(v, Sensitive) for v in captured)

    def test_original_input_dicts_not_mutated(self) -> None:
        original = _make_root_span("t-1", user_input="raw")
        spans = [original]
        source = DatadogTraceSource(
            spans_provider=lambda: spans,
            cohort_classifier=_classify_baseline,
        )
        list(source.iter_traces())
        # Original dict still has a plain SearchedIO dict at `input`.
        assert original["input"] == {"value": "raw"}


class TestAdapterMetadata:
    def test_adapter_id_is_datadog(self) -> None:
        source = DatadogTraceSource(
            spans_provider=lambda: [],
            cohort_classifier=_classify_baseline,
        )
        assert source.adapter_metadata().adapter_id == "datadog"

    def test_explicit_sdk_version_passes_through(self) -> None:
        source = DatadogTraceSource(
            spans_provider=lambda: [],
            cohort_classifier=_classify_baseline,
            sdk_version="0.27.0-test",
        )
        assert source.adapter_metadata().sdk_version == "0.27.0-test"

    def test_package_version_fallback_is_string(self) -> None:
        from whatifd_datadog import __version__ as pkg_version

        assert isinstance(pkg_version, str)
        assert pkg_version


class TestClusterKeySupport:
    def test_no_cluster_keys_in_v0_2(self) -> None:
        source = DatadogTraceSource(
            spans_provider=lambda: [],
            cohort_classifier=_classify_baseline,
        )
        assert source.cluster_key_support().available_keys == ()


class TestRealExportApiShape:
    """Projection against the EXACT span shape confirmed from a live Datadog
    org (ml_app `whatifd-faithfulness`, 2026-06-04, via `probe_datadog.py`):
    `span_kind` ∈ {workflow, llm, tool}; `input`/`output` are `SearchedIO`
    (`{value}` on tool spans, `{value, messages:[{content, role}]}` on llm);
    real attribute keys `duration/metrics/model_name/model_provider/start_ns/
    status/ml_app/tags`; `tags` is a `list[str]`; `tool_definitions` is NOT
    present on tool-call spans. The adapter required no code changes — this
    pins the contract so a future projection refactor stays faithful to the
    real API.
    """

    @staticmethod
    def _real_trace() -> list[dict[str, object]]:
        tid = "abc123"
        return [
            {  # root: workflow (confirmed real root kind)
                "trace_id": tid,
                "span_id": "wf-1",
                "parent_id": None,
                "span_kind": "workflow",
                "name": "cohort-score",
                "input": {
                    "value": "score this turn",
                    "messages": [{"content": "score this turn", "role": "user"}],
                },
                "output": {
                    "value": "scored",
                    "messages": [{"content": "scored", "role": "assistant"}],
                },
                "ml_app": "whatifd-faithfulness",
                "tags": ["env:prod", "service:judge"],
                "duration": 1234,
                "start_ns": 1,
                "status": "ok",
            },
            {  # llm child (auto-instrumented Anthropic call)
                "trace_id": tid,
                "span_id": "llm-1",
                "parent_id": "wf-1",
                "span_kind": "llm",
                "name": "anthropic.messages.create",
                "input": {
                    "value": "judge prompt",
                    "messages": [{"content": "judge prompt", "role": "user"}],
                },
                "output": {"value": "5", "messages": [{"content": "5", "role": "assistant"}]},
                "model_name": "claude-haiku-4-5",
                "model_provider": "anthropic",
                "metrics": {"input_tokens": 10, "output_tokens": 1},
                "tags": ["env:prod"],
            },
            {  # tool child — input/output are SearchedIO {value} only (no messages)
                "trace_id": tid,
                "span_id": "tool-1",
                "parent_id": "wf-1",
                "span_kind": "tool",
                "name": "Bash",
                "input": {"value": "ls -la"},
                "output": {"value": "file1\nfile2"},
                "tags": ["env:prod", "tool:bash"],
            },
        ]

    def test_root_workflow_provides_user_content(self) -> None:
        source = DatadogTraceSource(
            spans_provider=self._real_trace, cohort_classifier=_classify_baseline
        )
        [trace] = list(source.iter_traces())
        assert trace.user_message.unwrap(reason="test") == "score this turn"
        assert trace.original_response.unwrap(reason="test") == "scored"

    def test_tool_span_projected_from_value_only_searchedio(self) -> None:
        source = DatadogTraceSource(
            spans_provider=self._real_trace, cohort_classifier=_classify_baseline
        )
        [trace] = list(source.iter_traces())
        tool = next(s for s in trace.tool_spans if s.kind == "tool")
        assert tool.name == "Bash"
        assert tool.input is not None and tool.input.unwrap(reason="test") == "ls -la"
        assert tool.output is not None and tool.output.unwrap(reason="test") == "file1\nfile2"

    def test_all_non_root_children_captured(self) -> None:
        # Confirmed behavior: every non-root span (llm + tool) is captured in
        # tool_spans with its kind preserved (mirrors whatifd-phoenix).
        source = DatadogTraceSource(
            spans_provider=self._real_trace, cohort_classifier=_classify_baseline
        )
        [trace] = list(source.iter_traces())
        kinds = sorted(s.kind for s in trace.tool_spans)
        assert kinds == ["llm", "tool"]

    def test_list_tags_drive_cohort_classifier(self) -> None:
        # `tags` is a list[str] (confirmed) — a tag-based classifier works.
        def _by_tag(spans: list[dict[str, object]]) -> str:
            for s in spans:
                tags = s.get("tags")
                if isinstance(tags, list) and "tool:bash" in tags:
                    return "failure"
            return "baseline"

        source = DatadogTraceSource(spans_provider=self._real_trace, cohort_classifier=_by_tag)
        [trace] = list(source.iter_traces())
        assert trace.cohort == "failure"


class TestClientGuards:
    """`make_spans_provider` enforces the explicit-time-window rule
    (cardinal #1: the 15-min default must not silently apply)."""

    def test_make_spans_provider_requires_from_ts(self) -> None:
        from whatifd_datadog.client import DatadogExportClient, make_spans_provider

        client = DatadogExportClient(api_key="k", app_key="a")
        with pytest.raises(ValueError, match="from_ts"):
            make_spans_provider(client, from_ts="")

    def test_base_url_uses_site(self) -> None:
        from whatifd_datadog.client import DatadogExportClient

        client = DatadogExportClient(api_key="k", app_key="a", site="datadoghq.eu")
        assert client.base_url == "https://api.datadoghq.eu"
