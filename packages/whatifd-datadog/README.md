# whatifd-datadog

Datadog **LLM Observability** `TraceSource` adapter for [whatifd](https://github.com/victoralfred/whatifd).

Reads previously-ingested LLM-Obs spans (read-only) and projects each trace
into a whatifd `RawTrace`, so you can fork Datadog-traced agent turns,
replay them under a proposed change, and gate a PR on the verdict.

## Status

- ✅ Span-iterator adapter (`DatadogTraceSource`) + conformance test (offline)
- ✅ Thin Export-API client (`DatadogExportClient`, `[live]` extra)
- ❌ Recorded-cassette smoke against a live Datadog org — deferred (needs a real org)

## Install

```bash
pip install whatifd-datadog          # adapter core
pip install whatifd-datadog[live]    # + httpx for the Export API client
```

## Why a thin httpx client (not the official SDK)

The official `datadog-api-client` Python SDK covers LLM Observability
*ingestion / experiments / eval-metric*, but does **not** expose a
spans-*read* path. The documented read surface is the **LLM Observability
Export API**:

- `GET  /api/v2/llm-obs/v1/spans/events`
- `POST /api/v2/llm-obs/v1/spans/events/search`

This package wraps it with a minimal `httpx` client. Auth requires **both**
the API key and the Application key.

## Usage

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
    # ALWAYS bound the window — the Export API defaults to the last 15 min.
    spans_provider=make_spans_provider(client, ml_app="my-agent", from_ts="now-24h"),
    cohort_classifier=lambda spans: (
        "failure" if any("whatifd:failure" in (s.get("tags") or []) for s in spans)
        else "baseline"
    ),
)

for raw in source.iter_traces():
    print(raw.trace_id, raw.cohort)
```

The adapter is span-iterator-shaped (like `whatifd-phoenix`): `spans_provider`
is any zero-arg callable yielding normalized span dicts, so you can wire your
own transport or feed fixtures in tests with no network.

## Emitting verdict metrics (the sink)

After `whatifd fork` writes its report, push verdict + cohort metrics to
Datadog so dashboards/monitors can track Ship-rate and regression trends:

```bash
whatifd-datadog-emit reports/whatifd-fork-2026-06-04.json --tag service:my-agent
```

Emits gauges: `whatifd.verdict.code` (0=ship / 1=dont_ship / 2=inconclusive,
matching the CLI exit code), `whatifd.cohort.{selected,replayed,scored,
improved,regressed,unchanged,median_delta,floor_passed,regression_ratio,
improvement_ratio}` (tagged `cohort:<name>`), and `whatifd.findings.blocking`.

- **Out of whatifd core by design** — it reads the already-written report and
  only reports; it never touches the verdict path.
- **Soft-fails by default** — a metrics hiccup exits 0 so it can't turn a green
  verdict red in CI. Pass `--strict` to fail the step on emission errors.
- Agentless: `POST /api/v1/series` with `DD_API_KEY` (`DD_SITE` for region).
  `--dry-run` prints metrics without submitting. Needs the `[live]` extra.

## Cardinal alignment

- **#5 Sensitive[T] at the boundary** — span `input` / `output` (Datadog
  `SearchedIO`) are wrapped as `Sensitive[str]` at ingress, on root and child
  spans alike; PII-registered attribute keys are wrapped via
  `wrap_pii_attributes`.
- **#1 failure-as-data** — `make_spans_provider` requires an explicit
  `from_ts`; the API's 15-minute default would otherwise silently return a
  near-empty cohort. Missing `httpx` raises a clear install hint.
- **#9 orchestration, not compute** — streaming pagination; no CPU tricks.
- **#10 statistical claims** — `cluster_key_support()` returns an empty
  tuple; Datadog `session_id` / `trace_id` are not mined as cluster keys.
