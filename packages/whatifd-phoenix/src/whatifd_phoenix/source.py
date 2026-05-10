"""`PhoenixTraceSource` — implementation of `whatifd.adapters.TraceSource`.

Constructor takes a `spans_provider` callable returning an iterable
of OpenInference-shaped span dicts; `iter_traces` groups spans by
`context.trace_id` and projects each trace into a `RawTrace` with
content fields wrapped as `Sensitive[str]`. The runtime contract
follows `whatifd.adapters.protocols.TraceSource`; the conformance
harness at `tests/adapters/conformance.py` is the gating test.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from whatifd.adapters.protocols import (
    AdapterMetadata,
    RawTrace,
)
from whatifd.types.sensitive import Sensitive
from whatifd.types.statistical import ClusterKeySupport

_log = logging.getLogger(__name__)

ADAPTER_ID = "phoenix"

# OpenInference attribute keys this adapter reads. Defined as
# constants so a future OpenInference-spec revision (e.g.,
# `input.value` → `llm.input_messages`) lands in one place rather
# than scattered through projection logic. See
# https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md
_ATTR_INPUT = "input.value"
_ATTR_OUTPUT = "output.value"
_ATTR_TRACE_ID = "context.trace_id"
_ATTR_PARENT_ID = "parent_id"
_ATTR_SPAN_KIND = "openinference.span.kind"
_ROOT_SPAN_KINDS = frozenset({"CHAIN", "AGENT", "LLM"})


def _stringify(value: object) -> str:
    """Project an OpenInference attribute value (typically str, but
    Phoenix occasionally surfaces serialized JSON or None) into a
    canonical string. None and empty values render as the empty
    string so downstream `Sensitive[str]` wrapping always succeeds."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _is_root_span(span: dict[str, object]) -> bool:
    """Identify the root span of a trace.

    OpenInference root spans either (a) have no `parent_id` or
    (b) carry an `openinference.span.kind` of `CHAIN` / `AGENT` / `LLM`
    at the top level. The adapter prefers (a) for correctness — a
    trace's root span is structurally the one with no parent — and
    falls back to (b) for cases where the parent_id wasn't recorded.
    """
    if span.get(_ATTR_PARENT_ID) in (None, ""):
        return True
    kind = span.get(_ATTR_SPAN_KIND)
    return kind in _ROOT_SPAN_KINDS


@dataclass(frozen=True, slots=True)
class PhoenixTraceSource:
    """Phoenix / OpenInference `TraceSource` adapter.

    Construct with:

    - `spans_provider`: a zero-argument callable returning an iterable
      of span dicts. Each span dict is OpenInference-shaped — `context.trace_id`
      identifies the trace, `parent_id` builds the tree, and
      `input.value` / `output.value` carry user content. Callers wire
      this from their Phoenix client (`Client.query_spans(...).to_dict()`)
      or any OTLP collector emitting OpenInference attributes.
    - `cohort_classifier`: a callable mapping the span list of a single
      trace to a cohort name (`"failure"` / `"baseline"` for
      failure-rescue scope; `"baseline"` only for regression-check).
      Receives the full span list so classifiers can read non-root
      attributes (e.g., a tag set on a tool span).
    - `max_traces`: optional cap on the total iteration; matches the
      `LangfuseTraceSource.max_traces` behavior. None means unbounded.
    - `sdk_version`: optional override for the `arize-phoenix-client`
      version string. None = best-effort detection via
      `_resolve_sdk_version`.
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
                    "PhoenixTraceSource: span missing %s; skipping. span=%r",
                    _ATTR_TRACE_ID,
                    {k: v for k, v in span.items() if k != _ATTR_INPUT},
                )
                continue
            spans_by_trace[trace_id].append(span)

        for emitted, (trace_id, spans) in enumerate(spans_by_trace.items()):
            if self.max_traces is not None and emitted >= self.max_traces:
                return
            yield self._project(trace_id, spans)

    def adapter_metadata(self) -> AdapterMetadata:
        from whatifd_phoenix import __version__ as package_version

        return AdapterMetadata(
            adapter_id=ADAPTER_ID,
            package_version=package_version,
            sdk_version=self.sdk_version or _resolve_sdk_version(),
        )

    def cluster_key_support(self) -> ClusterKeySupport:
        # v0.2: empty. OpenInference spans carry `user.id` and
        # `session.id` attributes when set, but using either as a
        # cluster key would be an unannounced inferential commitment
        # (cardinal #10 forbids fabricating cluster keys for
        # confirmatory verdicts). v0.3+ surfaces explicit per-attribute
        # opt-in via `PhoenixTraceSource(cluster_attributes=("user.id",))`
        # or similar; for now the source declares no clusters and the
        # methodology disclosure reflects that honestly.
        return ClusterKeySupport(available_keys=())

    def _project(self, trace_id: str, spans: list[dict[str, object]]) -> RawTrace:
        # Find the root span — that's where input/output user content
        # lives. If multiple candidates pass `_is_root_span`, prefer
        # the parent-less one; if none, fall back to the first span
        # (still better than emitting nothing; the projection becomes
        # empty Sensitive[""] strings, which downstream guards will
        # surface as a structured failure rather than silently scoring).
        roots = [s for s in spans if s.get(_ATTR_PARENT_ID) in (None, "")]
        if not roots:
            roots = [s for s in spans if _is_root_span(s)]
        root = roots[0] if roots else spans[0]

        # Sensitive-wrap boundary (cardinal #5): input.value and
        # output.value are user content. Other attributes are tooling
        # state (model name, latency, tool calls) and the conformance
        # contract requires them to flow as plain dict[str, Any].
        return RawTrace(
            trace_id=trace_id,
            cohort=self.cohort_classifier(spans),
            user_message=Sensitive(
                _stringify(root.get(_ATTR_INPUT)),
                classification="user_content",
            ),
            original_response=Sensitive(
                _stringify(root.get(_ATTR_OUTPUT)),
                classification="user_content",
            ),
            metadata={k: v for k, v in root.items() if k not in (_ATTR_INPUT, _ATTR_OUTPUT)},
        )


def _resolve_sdk_version() -> str | None:
    """Read `arize_phoenix_client.__version__` lazily so importing
    this module doesn't drag the Phoenix SDK in until it's actually
    needed. Returns None if the SDK isn't installed — the resulting
    `AdapterMetadata.sdk_version` is None, which the manifest accepts.
    """
    try:
        import arize_phoenix_client  # type: ignore[import-not-found]

        version = getattr(arize_phoenix_client, "__version__", None)
        if version is None:
            _log.debug(
                "arize-phoenix-client imported but exposes no __version__; "
                "AdapterMetadata.sdk_version will be None"
            )
        sdk_version: str | None = version
        return sdk_version
    except ImportError:
        _log.debug(
            "arize-phoenix-client not installed; AdapterMetadata.sdk_version "
            "will be None. Install via `pip install whatifd-phoenix[live]` "
            "or directly with `pip install arize-phoenix-client`."
        )
        return None
