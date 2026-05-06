"""`whatif.replay.tool_cache` — strict per-trace tool cache.

Phase 6.2 of the v0.1 implementation plan. The replay pipeline hands
each user-runner invocation a `ToolCache` (the public contract type
from `whatif.contract`) populated from the original trace. v0.1
policy is `use-original`: a tool call the runner makes during replay
MUST have a matching entry in the recorded cache, or the trace
records a replay failure. No live tool calls.

This module supplies the STRICT lookup behavior for `use-original`:

  - `CacheMissError` — typed exception raised on miss. Carries
    `trace_id`, `tool_name`, `args` for diagnostic context.
  - `StrictToolCache` — `whatif.contract.ToolCache` subclass that
    overrides `lookup(...)` to raise `CacheMissError` instead of
    returning `None`.
  - `make_strict_tool_cache(entries, trace_id)` — factory the
    adapter / pipeline calls when handing a cache to the runner.

## Why a subclass, not a contract change

`whatif.contract.ToolCache` is the public, version-stable surface
user runners reference for type annotations. Changing its `lookup`
return type from `Any | None` to `Any (raises)` would be a v0.1
contract break. The subclass approach keeps the public type stable;
runtime instances are `StrictToolCache` (a `ToolCache` by Liskov),
and user code annotated `tool_cache: ToolCache` correctly receives
the strict variant. mypy / Pydantic typing remain valid.

## Why miss-raises rather than miss-returns-None

Cardinal #1 (failures-as-data) says expected failures are structured
data, not exceptions. So why does the cache RAISE on miss? Because
the cache is internal to the runner's execution — the user runner
doesn't know to handle a `None` semantically (it would propagate
into the agent code as bad data and produce silent garbage). The
exception escapes the runner, the pipeline catches it at the
runner-call boundary, and converts to `ReplayFailure(code=
"tool_cache_miss")` — THAT is the structured data per cardinal #1.
The exception is module-private, never appears in a report.

## Per-trace, not global

Each trace gets its own `StrictToolCache` instance with only that
trace's cached calls. A miss on one trace doesn't affect siblings;
the failure is per-trace-scoped (`scope="trace"` on the projected
`FailureRecord`). The pipeline (Phase 6.3) constructs one cache per
trace, hands it to the runner, discards it after replay.

## Cardinal alignment

- **#1 failures-as-data:** cache miss propagates as a typed
  `CacheMissError`, caught at the pipeline boundary and converted
  to `ReplayFailure(code="tool_cache_miss")`. The exception is
  internal; the report sees structured data.
- **#6 typed boundaries:** `CacheMissError.details_for_failure()`
  returns the `Mapping[str, JsonPrimitive]` shape the pipeline
  hands to `ReplayFailure(details=...)`. No `dict[str, Any]`
  crosses.
- **#9 orchestration not compute:** lookup is a dict get + raise.
  No optimization, no fancy cache eviction, no compute.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import PrivateAttr

# Prime the serialization ↔ cache import cycle. `ToolCache._key`
# lazy-imports `canonical_json_bytes` from `whatif.serialization`,
# which in turn pulls `whatif.cache.lock` (POSIX-only). When this
# module is loaded BEFORE anything else has touched `whatif.cache`,
# the cycle resolves cleanly only because we force-load `whatif.cache`
# here. Without this prime, running just the replay tests in
# isolation triggers `ImportError: cannot import name
# 'parse_lock_file_content' from partially initialized module
# 'whatif.serialization'`. The cascade entry "Serialization ↔ report
# ↔ cache import cycle" tracks the root-cause refactor; this prime
# is a load-order safety net until that lands.
import whatif.cache  # noqa: F401
from whatif.contract import ToolCache
from whatif.types.primitives import JsonPrimitive


class CacheMissError(Exception):
    """A tool call during replay had no matching entry in the cache.

    Module-private to `whatif.replay`: the pipeline catches this at
    the runner boundary and converts to `ReplayFailure(code=
    "tool_cache_miss", trace_id=..., details={"tool_name": ...})`.
    The exception never escapes the pipeline; the report sees only
    the structured `ReplayFailure`.

    `tool_args` is captured for the diagnostic message; it is NOT
    included in the failure's `details` map because user-content
    args may carry sensitive data (e.g., a user_id, a query string).
    The canonical-keyed args go through `ToolCache._key`'s
    `canonical_json_bytes` for deterministic miss-detection but the
    original args dict isn't propagated past the pipeline boundary.

    Attribute name `tool_args` (not `args`) avoids shadowing
    `BaseException.args` (the message tuple); see `__init__`.
    """

    def __init__(
        self,
        *,
        trace_id: str,
        tool_name: str,
        args: Mapping[str, Any],
    ) -> None:
        self.trace_id = trace_id
        self.tool_name = tool_name
        # `tool_args` rather than `args`: `BaseException.__init__`
        # binds `self.args = (message,)` AFTER user `__init__` runs,
        # so naming our attribute `args` would silently shadow it
        # back to the message tuple by end of __init__. Using a
        # distinct name keeps the captured Mapping intact.
        self.tool_args = dict(args)
        super().__init__(
            f"tool cache miss on trace {trace_id!r}: tool {tool_name!r} called "
            f"with {len(self.tool_args)} args has no matching entry. v0.1 policy "
            "'use-original' forbids live calls; the original trace must have "
            "captured this call for replay to succeed."
        )

    def details_for_failure(self) -> Mapping[str, JsonPrimitive]:
        """Project to the `Mapping[str, JsonPrimitive]` shape the
        pipeline hands to `ReplayFailure(details=...)`.

        Only `tool_name` is required by the registry's
        `tool_cache_miss` spec (`required_details=("tool_name",)`).
        We deliberately do NOT include the `args` dict — user-content
        args may carry sensitive data. The pipeline sees enough to
        identify the call site (trace_id + tool_name); operators
        debugging a miss can re-run with the trace at hand.
        """
        return {"tool_name": self.tool_name}


class StrictToolCache(ToolCache):
    """`ToolCache` subclass whose `lookup` raises on miss.

    Constructed by `make_strict_tool_cache` per-trace. User runners
    annotated `tool_cache: ToolCache` receive this variant via Liskov;
    they don't import `StrictToolCache` directly.

    `_trace_id` is a Pydantic v2 PrivateAttr — it lives outside the
    model's validated field set, so the parent's
    `model_config = ConfigDict(extra="forbid")` doesn't reject it.
    The factory `make_strict_tool_cache` populates it after
    construction; user code never sees this attribute (it's not in
    the public `ToolCache` contract).
    """

    _trace_id: str = PrivateAttr(default="")

    def lookup(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Strict lookup: returns the cached value or raises
        `CacheMissError`. Never returns `None`.
        """
        # Reuse the parent's keying so `_key` stays the single source
        # of truth for canonicalization (cardinal #6 — one boundary,
        # not two).
        result = self.cache.get(self._key(tool_name, args))
        if result is None:
            raise CacheMissError(
                trace_id=self._trace_id,
                tool_name=tool_name,
                args=args,
            )
        return result


def make_strict_tool_cache(
    entries: Mapping[str, Any],
    *,
    trace_id: str,
) -> StrictToolCache:
    """Build a `StrictToolCache` for one trace.

    `entries` is the already-canonical-keyed dict (the adapter or
    Phase 6.2 from-trace projection produces it via `ToolCache._key`
    or equivalent canonicalization). `trace_id` is captured so the
    `CacheMissError` can name it diagnostically.

    The factory exists so the pipeline doesn't have to know about
    `_trace_id` private-attribute mechanics — it just calls
    `make_strict_tool_cache(entries, trace_id=...)` and hands the
    result to the runner.
    """
    cache = StrictToolCache(cache=dict(entries), policy="use-original")
    cache._trace_id = trace_id
    return cache


__all__ = [
    "CacheMissError",
    "StrictToolCache",
    "make_strict_tool_cache",
]
