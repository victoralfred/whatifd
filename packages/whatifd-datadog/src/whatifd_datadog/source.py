"""`DatadogTraceSource` — implementation of `whatifd.adapters.TraceSource`.

Constructor takes a `spans_provider` callable returning an iterable of
normalized Datadog LLM-Observability span dicts; `iter_traces` groups spans
by `trace_id` and projects each trace into a `RawTrace` with content fields
wrapped as `Sensitive[str]`. The runtime contract follows
`whatifd.adapters.protocols.TraceSource`; the conformance harness at
`tests/adapters/conformance.py` is the gating test.

The span dict shape is the Datadog LLM-Obs Export API span attributes,
flattened by `whatifd_datadog.client.make_spans_provider`:

    {
      "trace_id": "...", "span_id": "...", "parent_id": "..." | None,
      "span_kind": "agent" | "llm" | "tool" | "workflow" | "retrieval" | ...,
      "name": "...",
      "input":  {"value": "...", "messages": [...]} ,   # SearchedIO
      "output": {"value": "...", "messages": [...]} ,   # SearchedIO
      "model_name": "...", "tags": [...] | {...}, "meta": {...}, ...
    }
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from whatifd.adapters.pii import wrap_pii_attributes
from whatifd.adapters.protocols import (
    AdapterMetadata,
    RawTrace,
)
from whatifd.contract import ToolSpan
from whatifd.serialization.canonical import canonical_json_bytes
from whatifd.types.sensitive import Sensitive
from whatifd.types.statistical import ClusterKeySupport

_log = logging.getLogger(__name__)

ADAPTER_ID = "datadog"

# Datadog LLM-Obs span attribute keys this adapter reads. Defined as
# constants so a future Export-API field rename lands in one place rather
# than scattered through projection logic.
# https://docs.datadoghq.com/llm_observability/evaluations/export_api/
_ATTR_TRACE_ID = "trace_id"
_ATTR_PARENT_ID = "parent_id"
_ATTR_SPAN_KIND = "span_kind"
_ATTR_NAME = "name"
_ATTR_INPUT = "input"
_ATTR_OUTPUT = "output"
# Content slots are excluded from the metadata projection so user content
# never double-exposes through `RawTrace.metadata` (cardinal #5).
_CONTENT_ATTRS = frozenset({_ATTR_INPUT, _ATTR_OUTPUT})

# Root-span kind fallback. Datadog LLM-Obs span kinds are lowercase
# (`agent`, `workflow`, `llm`, `tool`, `task`, `embedding`, `retrieval`).
# `agent` and `workflow` are top-level orchestration kinds; a span with no
# `parent_id` and one of these kinds is the trace root.
#
# `llm` is INTENTIONALLY EXCLUDED (mirrors the Phoenix adapter's rationale):
# a child LLM-call span whose `parent_id` was dropped upstream would
# otherwise be misidentified as the trace root and surface the model prompt
# as the trace's `user_message` — a silent wrong result, not a structured
# failure (cardinal #1).
_ROOT_SPAN_KINDS = frozenset({"agent", "workflow"})


def _stringify(value: object) -> str:
    """Project an arbitrary attribute value into a canonical string.

    None / empty render as the empty string so downstream `Sensitive[str]`
    wrapping always succeeds with a real `str`. Dicts/lists route through
    `canonical_json_bytes` (stable JSON, not Python repr). Mirrors
    `whatifd_phoenix.source._stringify` and `whatifd_langfuse.source._stringify`.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    decoded: str = canonical_json_bytes(value).decode("ascii")
    return decoded


def _io_to_str(io_value: object) -> str:
    """Project a Datadog `SearchedIO` (`{value, messages}`) into a string.

    The Export API returns span `input` / `output` as a `SearchedIO` object
    with a `value` (a rendered string) and/or a `messages` array. Prefer
    `value`; fall back to concatenating message `content` fields; finally
    fall back to a canonical-JSON dump so nothing is silently dropped.
    Plain strings (some spans store the raw string) pass through.
    """
    if io_value is None:
        return ""
    if isinstance(io_value, str):
        return io_value
    if isinstance(io_value, dict):
        value = io_value.get("value")
        if isinstance(value, str) and value:
            return value
        messages = io_value.get("messages")
        if isinstance(messages, list) and messages:
            parts = [
                str(m.get("content", ""))
                for m in messages
                if isinstance(m, dict) and m.get("content")
            ]
            if parts:
                return "\n".join(parts)
    # Structured but neither value nor messages usable — canonicalize the
    # whole object rather than drop it (cardinal #1: no silent loss).
    return _stringify(io_value)


def _wrap_user_content_in_span(span: dict[str, object]) -> dict[str, object]:
    """Return a shallow copy of `span` with `input` and `output` wrapped as
    `Sensitive[str]`.

    Cardinal #5 boundary: any span attribute that may carry user content is
    wrapped at adapter ingress so the classifier callable (and any other
    downstream consumer) sees a `Sensitive[str]` rather than a raw
    user-content string. Original spans are NOT mutated — the caller may
    reuse them.
    """
    if _ATTR_INPUT not in span and _ATTR_OUTPUT not in span:
        return span
    wrapped: dict[str, object] = dict(span)
    if _ATTR_INPUT in wrapped:
        wrapped[_ATTR_INPUT] = Sensitive(
            _io_to_str(wrapped[_ATTR_INPUT]), classification="user_content"
        )
    if _ATTR_OUTPUT in wrapped:
        wrapped[_ATTR_OUTPUT] = Sensitive(
            _io_to_str(wrapped[_ATTR_OUTPUT]), classification="user_content"
        )
    return wrapped


def _project_tool_span(span: dict[str, object]) -> ToolSpan:
    """Project a non-root Datadog span into a typed `ToolSpan` (#108).

    Content (`input` / `output`) arrives pre-wrapped as `Sensitive[str]` from
    `_wrap_user_content_in_span`, so it passes straight through `ToolSpan`'s
    before-validator. Structural attributes route through
    `wrap_pii_attributes` so any registered-PII key is wrapped, satisfying
    `ToolSpan`'s attribute validator.

    ## Caller precondition
    The call site uses `s is not root` (identity, not equality) to exclude
    the root span; callers MUST pass the same span dict instance selected as
    `root`. Mirrors the Phoenix adapter's documented precondition.
    """
    name = span.get(_ATTR_NAME) or span.get(_ATTR_SPAN_KIND) or "tool"
    kind = span.get(_ATTR_SPAN_KIND) or "tool"
    attributes = {k: v for k, v in span.items() if k not in _CONTENT_ATTRS}
    # input/output are already Sensitive[str] (or absent) from
    # _wrap_user_content_in_span. The span dict is `dict[str, object]`, so
    # narrow back to `Sensitive[str] | None` with an isinstance check rather
    # than leaking `object` into ToolSpan's typed field (no blind cast).
    raw_input = span.get(_ATTR_INPUT)
    raw_output = span.get(_ATTR_OUTPUT)
    return ToolSpan(
        name=str(name),
        kind=str(kind),
        input=raw_input if isinstance(raw_input, Sensitive) else None,
        output=raw_output if isinstance(raw_output, Sensitive) else None,
        attributes=wrap_pii_attributes(attributes),
    )


def _is_root_span(span: dict[str, object]) -> bool:
    """Identify the root span of a trace.

    Prefers (a) no `parent_id` for correctness — a trace's root is
    structurally the span with no parent — and falls back to (b) an
    orchestration `span_kind` (`agent` / `workflow`) for malformed traces
    where `parent_id` was dropped upstream. `llm` is intentionally excluded
    from the fallback set (see `_ROOT_SPAN_KINDS`).
    """
    if span.get(_ATTR_PARENT_ID) in (None, ""):
        return True
    kind = span.get(_ATTR_SPAN_KIND)
    return kind in _ROOT_SPAN_KINDS


@dataclass(frozen=True, slots=True)
class DatadogTraceSource:
    """Datadog LLM Observability `TraceSource` adapter (read-only).

    Construct with:

    - `spans_provider`: a zero-argument callable returning an iterable of
      normalized Datadog LLM-Obs span dicts (see module docstring for the
      shape). Wire it from `whatifd_datadog.client.make_spans_provider`, or
      any source emitting the same dict shape (offline tests pass a list).
    - `cohort_classifier`: a callable mapping the span list of a single
      trace to a cohort name (`"failure"` / `"baseline"` for failure-rescue;
      `"baseline"` only for regression-check). Receives the full span list
      so classifiers can read non-root attributes (e.g., a tag on a tool
      span).
    - `max_traces`: optional cap on total iteration. None = unbounded.
    - `sdk_version`: optional override for the transport version string.
    """

    spans_provider: Callable[[], Iterable[dict[str, object]]]
    cohort_classifier: Callable[[list[dict[str, object]]], str]
    max_traces: int | None = None
    sdk_version: str | None = None

    def iter_traces(self) -> Iterator[RawTrace]:
        spans_by_trace: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
        for span in self.spans_provider():
            trace_id = span.get(_ATTR_TRACE_ID)
            if not isinstance(trace_id, str) or not trace_id:
                _log.debug(
                    "DatadogTraceSource: span missing %s; skipping. span_id=%r",
                    _ATTR_TRACE_ID,
                    span.get("span_id"),
                )
                continue
            # Cardinal #5: pre-wrap input/output on EVERY span (not just the
            # root) before the classifier sees them — a child span may carry
            # user content in its own input/output (e.g., a sub-agent call).
            spans_by_trace[trace_id].append(_wrap_user_content_in_span(span))

        for emitted, (trace_id, spans) in enumerate(spans_by_trace.items()):
            if self.max_traces is not None and emitted >= self.max_traces:
                return
            yield self._project(trace_id, spans)

    def adapter_metadata(self) -> AdapterMetadata:
        from whatifd_datadog import __version__ as package_version

        return AdapterMetadata(
            adapter_id=ADAPTER_ID,
            package_version=package_version,
            sdk_version=self.sdk_version or _resolve_sdk_version(),
        )

    def cluster_key_support(self) -> ClusterKeySupport:
        # v0.2: empty. Datadog spans carry `session_id` / `trace_id`, but
        # using either as a cluster key would be an unannounced inferential
        # commitment (cardinal #10). v0.3+ may add explicit per-attribute
        # opt-in; for now the source declares no clusters and the
        # methodology disclosure reflects that honestly.
        return ClusterKeySupport(available_keys=())

    def _project(self, trace_id: str, spans: list[dict[str, object]]) -> RawTrace:
        # Defensive: an empty `spans` list is structurally impossible under
        # the current iter_traces (a span is only grouped if it has a valid
        # trace_id). Cardinal #1 belt-and-suspenders for a future refactor.
        if not spans:
            return RawTrace(
                trace_id=trace_id,
                cohort=self.cohort_classifier(spans),
                user_message=Sensitive("", classification="user_content"),
                original_response=Sensitive("", classification="user_content"),
                metadata={},
            )

        roots = [s for s in spans if _is_root_span(s)]
        root = roots[0] if roots else spans[0]

        # input/output arrived pre-wrapped as Sensitive[str] from
        # _wrap_user_content_in_span. Re-bind to the typed RawTrace slots;
        # fall back to an empty Sensitive[""] if the root lacks them
        # (downstream guards surface that as a structured failure).
        wrapped_input = root.get(_ATTR_INPUT)
        wrapped_output = root.get(_ATTR_OUTPUT)
        user_message = (
            wrapped_input
            if isinstance(wrapped_input, Sensitive)
            else Sensitive(_io_to_str(wrapped_input), classification="user_content")
        )
        original_response = (
            wrapped_output
            if isinstance(wrapped_output, Sensitive)
            else Sensitive(_io_to_str(wrapped_output), classification="user_content")
        )
        # Project non-root spans into `RawTrace.tool_spans`. Identity
        # comparison (`s is not root`) is correct because `root` was picked
        # from `spans`.
        tool_spans = [_project_tool_span(s) for s in spans if s is not root]

        return RawTrace(
            trace_id=trace_id,
            cohort=self.cohort_classifier(spans),
            user_message=user_message,
            original_response=original_response,
            tool_spans=tool_spans,
            # Wrap PII-bearing attributes at the boundary (cardinal #5,
            # issue #87). `wrap_pii_attributes` wraps registered keys as
            # Sensitive[str] and passes everything else through.
            metadata=wrap_pii_attributes(
                {k: v for k, v in root.items() if k not in _CONTENT_ATTRS}
            ),
        )


def _resolve_sdk_version() -> str | None:
    """Best-effort transport version (`httpx`) read lazily so importing this
    module doesn't require the `[live]` extra. Returns None if httpx isn't
    installed — the resulting `AdapterMetadata.sdk_version` is None, which
    the manifest accepts."""
    try:
        import httpx  # type: ignore[import-not-found,unused-ignore]

        version = getattr(httpx, "__version__", None)
        sdk_version: str | None = version
        return sdk_version
    except ImportError:
        _log.debug(
            "httpx not installed; AdapterMetadata.sdk_version will be None. "
            "Install via `pip install whatifd-datadog[live]` for the Export "
            "API client."
        )
        return None
