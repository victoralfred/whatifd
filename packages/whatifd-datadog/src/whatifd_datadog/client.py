"""Thin HTTP client for the Datadog LLM Observability Export API.

R-1 (2026-06-04) established that the official `datadog-api-client` SDK does
not expose the spans-read path, so this module is a minimal `httpx` wrapper
over the documented endpoints:

- `GET  /api/v2/llm-obs/v1/spans/events`          (list)
- `POST /api/v2/llm-obs/v1/spans/events/search`   (filtered)

https://docs.datadoghq.com/llm_observability/evaluations/export_api/

`httpx` is imported lazily (the `[live]` extra) so importing
`whatifd_datadog` core stays dependency-light and offline-testable.

## Cardinal alignment
- **#1 failure-as-data:** the Export API defaults to the **last 15 minutes**
  if no window is given. `make_spans_provider` REQUIRES an explicit
  `from_ts`, raising `ValueError` rather than silently returning a
  near-empty cohort. Missing `httpx` raises a clear `RuntimeError` with an
  install hint, never a bare `ImportError` deep in a generator.
- **#9 orchestration, not compute:** streaming pagination via a generator;
  no buffering of the full result set.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

_LIST_PATH = "/api/v2/llm-obs/v1/spans/events"
# The Export API caps `page[limit]` at 5000; default to a conservative page.
_DEFAULT_PAGE_LIMIT = 1000
_MAX_PAGE_LIMIT = 5000


@dataclass(frozen=True, slots=True)
class DatadogExportClient:
    """Minimal client for the LLM-Obs Export API.

    Auth uses BOTH the API key and the Application key (the Export API
    requires the application key, not just the API key). `site` selects the
    Datadog region (`datadoghq.com`, `datadoghq.eu`, `us3.datadoghq.com`,
    ...); the base URL is `https://api.{site}`.
    """

    api_key: str
    app_key: str
    site: str = "datadoghq.com"
    timeout_seconds: float = 30.0

    @property
    def base_url(self) -> str:
        return f"https://api.{self.site}"

    def _headers(self) -> dict[str, str]:
        return {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Accept": "application/json",
        }

    def iter_span_pages(
        self,
        *,
        from_ts: str,
        to_ts: str = "now",
        ml_app: str | None = None,
        query: str | None = None,
        page_limit: int = _DEFAULT_PAGE_LIMIT,
    ) -> Iterator[list[dict[str, Any]]]:
        """Yield successive pages of raw span-event objects (JSON:API `data`).

        Each yielded item is one page: a list of `{id, type, attributes}`
        objects. Pagination follows `meta.page.after` (cursor). Raises
        `RuntimeError` if `httpx` is not installed.
        """
        try:
            import httpx  # type: ignore[import-not-found,unused-ignore]
        except ImportError as exc:  # pragma: no cover - exercised only without [live]
            raise RuntimeError(
                "whatifd-datadog's Export API client requires `httpx`. Install "
                "with `pip install whatifd-datadog[live]`."
            ) from exc

        limit = min(page_limit, _MAX_PAGE_LIMIT)
        params: dict[str, str | int] = {
            "filter[from]": from_ts,
            "filter[to]": to_ts,
            "page[limit]": limit,
        }
        if ml_app is not None:
            params["filter[ml_app]"] = ml_app
        if query is not None:
            params["filter[query]"] = query

        with httpx.Client(
            base_url=self.base_url, headers=self._headers(), timeout=self.timeout_seconds
        ) as http:
            cursor: str | None = None
            while True:
                page_params = dict(params)
                if cursor is not None:
                    page_params["page[cursor]"] = cursor
                resp = http.get(_LIST_PATH, params=page_params)
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data") or []
                yield list(data)
                cursor = (((body.get("meta") or {}).get("page")) or {}).get("after")
                if not cursor or not data:
                    return


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Flatten one JSON:API span event (`{id, type, attributes}`) into the
    flat span dict `DatadogTraceSource` consumes. The `attributes` object
    holds the span fields (`trace_id`, `parent_id`, `span_kind`, `input`,
    `output`, ...); `span_id` is the top-level `id`."""
    attrs = dict(event.get("attributes") or {})
    if "span_id" not in attrs and event.get("id"):
        attrs["span_id"] = event["id"]
    return attrs


def make_spans_provider(
    client: DatadogExportClient,
    *,
    from_ts: str,
    to_ts: str = "now",
    ml_app: str | None = None,
    query: str | None = None,
    page_limit: int = _DEFAULT_PAGE_LIMIT,
) -> Callable[[], Iterator[dict[str, Any]]]:
    """Build a zero-arg `spans_provider` for `DatadogTraceSource`.

    REQUIRES an explicit `from_ts` (e.g. `"now-24h"` or an ISO/epoch
    timestamp). The Export API defaults to the last 15 minutes when no
    window is set, which would silently return a near-empty cohort — a
    cardinal-#1 failure mode. An empty `from_ts` raises `ValueError`.
    """
    if not from_ts:
        raise ValueError(
            "make_spans_provider requires an explicit `from_ts` (e.g. 'now-24h'). "
            "The Datadog Export API defaults to the last 15 minutes, which would "
            "silently yield a near-empty cohort."
        )

    def _provider() -> Iterator[dict[str, Any]]:
        for page in client.iter_span_pages(
            from_ts=from_ts,
            to_ts=to_ts,
            ml_app=ml_app,
            query=query,
            page_limit=page_limit,
        ):
            for event in page:
                yield _normalize_event(event)

    return _provider


__all__ = [
    "DatadogExportClient",
    "make_spans_provider",
]
