"""`whatifd-datadog` — Datadog LLM Observability `TraceSource` adapter.

Implements `whatifd.adapters.TraceSource` against the Datadog **LLM
Observability Export API** (`/api/v2/llm-obs/v1/spans/events[/search]`),
wraps user content as `Sensitive[str]` at the boundary (cardinal #5), and
streams traces via a generator (bounded memory for large backfills).

## Shape (mirrors `whatifd-phoenix`)

`DatadogTraceSource` is span-iterator-shaped: it takes a `spans_provider`
callable yielding normalized Datadog LLM-Obs span dicts and groups them by
`trace_id`. This keeps the adapter offline-testable and decouples it from
the HTTP transport. The transport lives in `whatifd_datadog.client`
(`DatadogExportClient` + `make_spans_provider`), which lazily imports
`httpx` (the `[live]` extra).

```python
import os
from whatifd_datadog import DatadogTraceSource
from whatifd_datadog.client import DatadogExportClient, make_spans_provider

client = DatadogExportClient(
    api_key=os.environ["DD_API_KEY"],
    app_key=os.environ["DD_APP_KEY"],
    site=os.environ.get("DD_SITE", "datadoghq.com"),
)
source = DatadogTraceSource(
    spans_provider=make_spans_provider(
        client,
        ml_app="my-agent",
        # ALWAYS bound the window — the API defaults to the last 15 min.
        from_ts="now-24h",
        to_ts="now",
    ),
    cohort_classifier=lambda spans: "failure" if _has_failure_tag(spans) else "baseline",
)

for raw in source.iter_traces():
    print(raw.trace_id, raw.cohort)
```

## Cardinal alignment

- **#5 Sensitive[T] at the boundary:** `input.value` / `output.value` on
  every span (root + children) are wrapped at ingress; PII-registered
  attribute keys are wrapped via `wrap_pii_attributes`.
- **#9 orchestration, not compute:** streaming pagination; no CPU tricks.
- **#10 statistical claims:** `cluster_key_support` returns an empty tuple.
  v0.2 does NOT mine Datadog `session_id` / `trace_id` as cluster keys.
"""

from importlib.metadata import PackageNotFoundError, version

from whatifd_datadog.source import DatadogTraceSource

try:
    __version__ = version("whatifd-datadog")
except PackageNotFoundError:
    # Editable / source-only install pre-`pip install`; sentinel mirrors
    # the langfuse/phoenix pattern.
    __version__ = "0.0.0+unknown"

__all__ = [
    "DatadogTraceSource",
    "__version__",
]
