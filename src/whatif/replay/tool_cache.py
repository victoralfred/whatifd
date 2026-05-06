"""`whatif.replay.tool_cache` — strict per-trace tool cache.

Phase 6.2 of the v0.1 implementation plan. The replay pipeline hands
each user-runner invocation a `ToolCache` (the public contract type
from `whatif.contract`) populated from the original trace. v0.1
policy is `use-original`: a tool call the runner makes during replay
MUST have a matching entry in the recorded cache, or the trace
records a replay failure. No live tool calls.

This module supplies the STRICT lookup behavior for `use-original`:

  - `CacheMissError` — typed exception raised on miss. Carries
    `trace_id`, `tool_name`, `arg_count` for diagnostic context.
    The args VALUES are deliberately NOT stored on the exception
    (cardinal #5 — see "Sensitive-data discipline" below).
  - `StrictToolCache` — `whatif.contract.ToolCache` subclass that
    overrides `lookup(...)` to raise `CacheMissError` on miss. Uses
    a private sentinel so a legitimately cached `None` value is
    distinguished from a true cache miss.
  - `make_strict_tool_cache(entries, *, trace_id)` — factory the
    adapter / pipeline calls when handing a cache to the runner.

These are subpackage-internal: the pipeline (Phase 6.3, sibling
module within `whatif.replay`) imports `CacheMissError` directly to
catch it at the runner-call boundary; sibling-internal use is what
the `__all__` export sanctions. They are NOT public surface — user
runners should never `import` from `whatif.replay.tool_cache` and
should never `except CacheMissError`. The exception is caught
exactly once, at the pipeline boundary, and projected to
`ReplayFailure(code="tool_cache_miss")`.

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
The exception is internal; it never appears in a report.

## Sentinel-vs-`None` miss detection

`dict.get(key)` returning `None` is ambiguous: it could mean "key
absent" OR "key present with value `None`". A tool that legitimately
returns `None` (e.g., a "find user" tool whose value semantics
include "not found") would be misclassified as a cache miss under a
naive `if result is None` check, producing a spurious
`ReplayFailure` for a successful trace.

`StrictToolCache._lookup_or_miss(key)` uses a private `_MISSING`
sentinel via `dict.get(key, _MISSING)` and tests `is _MISSING` to
detect true absence. A cached `None` value is returned as `None`
and the runner sees the legitimate result.

## Sensitive-data discipline (cardinal #5)

`CacheMissError` does NOT store the raw `args` dict. Args may carry
PII, credentials, query strings, or other user content; storing
them on the exception would leak via traceback formatting,
exception chaining, or any code that catches the exception and
calls `repr()` or attribute-walks the object.

The exception captures only `arg_count` (an integer). Operators
debugging a miss have:
- `trace_id` to look up the full trace via the source adapter
- `tool_name` to identify which call missed
- `arg_count` to disambiguate among same-tool-name calls if needed

The full args dict lives in the original trace, where the adapter
already wrapped sensitive content as `Sensitive[T]` at ingestion.

## Per-trace, not global

Each trace gets its own `StrictToolCache` instance with only that
trace's cached calls. A miss on one trace doesn't affect siblings;
the failure is per-trace-scoped (`scope="trace"` on the projected
`FailureRecord`). The pipeline (Phase 6.3) constructs one cache per
trace, hands it to the runner, discards it after replay.

## Cardinal alignment

- **#1 failures-as-data:** cache miss propagates as a typed
  `CacheMissError`, caught at the pipeline boundary and converted
  to `ReplayFailure(code="tool_cache_miss")`. Sentinel-based
  detection ensures a legitimately cached `None` is NOT mis-flagged
  as a miss.
- **#5 sensitive data wrapped:** raw args are never stored on the
  exception. Diagnostic context is bounded to (trace_id, tool_name,
  arg_count). The trace itself remains the source of truth for
  full args; sensitive parts there are already wrapped at
  ingestion.
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
# is the third workaround at the same cycle (encoder.py
# TYPE_CHECKING; ToolCache._key function-level lazy import; this
# module-level prime). Cleanup will retire all three.
import whatif.cache  # noqa: F401
from whatif.contract import ToolCache
from whatif.types.primitives import JsonPrimitive

# Private sentinel for sentinel-vs-None miss detection. Module-level
# so it has stable identity across calls; a fresh `object()` per
# call would still work but is needless allocation.
_MISSING: Any = object()

# Sentinel for unset trace_id. The factory MUST overwrite this; if
# `lookup` runs while `_trace_id == _UNSET_TRACE_ID`, that's a bug
# in the construction path (someone bypassed `make_strict_tool_cache`
# and didn't set `_trace_id`). Detected and raised in `lookup` so
# the failure is loud, not silent.
_UNSET_TRACE_ID = "__whatif_unset_trace_id__"


class CacheMissError(Exception):
    """A tool call during replay had no matching entry in the cache.

    Subpackage-internal to `whatif.replay`: the pipeline (Phase 6.3
    sibling module) catches this at the runner-call boundary and
    converts to `ReplayFailure(code="tool_cache_miss", trace_id=...,
    details={"tool_name": ...})`. The exception never escapes the
    pipeline; the report sees only the structured `ReplayFailure`.

    Attributes:
    - `trace_id`: the trace that missed
    - `tool_name`: the call that missed
    - `arg_count`: number of args (NOT the args themselves — see
      cardinal #5 discipline in module docstring)

    The captured state is deliberately minimal. Full args live in
    the original trace, where the adapter has already wrapped
    sensitive content as `Sensitive[T]`.
    """

    def __init__(
        self,
        *,
        trace_id: str,
        tool_name: str,
        arg_count: int,
    ) -> None:
        self.trace_id = trace_id
        self.tool_name = tool_name
        self.arg_count = arg_count
        super().__init__(
            f"tool cache miss on trace {trace_id!r}: tool {tool_name!r} called "
            f"with {arg_count} args has no matching entry. v0.1 policy "
            "'use-original' forbids live calls; the original trace must have "
            "captured this call for replay to succeed."
        )

    def details_for_failure(self) -> Mapping[str, JsonPrimitive]:
        """Project to the `Mapping[str, JsonPrimitive]` shape the
        pipeline hands to `ReplayFailure(details=...)`.

        Only `tool_name` is included (per the registry's
        `tool_cache_miss` `required_details=("tool_name",)`). The
        pipeline sees enough to identify the call site (trace_id +
        tool_name); operators debugging a miss can re-run with the
        trace at hand for full context.
        """
        return {"tool_name": self.tool_name}


class StrictToolCache(ToolCache):
    """`ToolCache` subclass whose `lookup` raises on miss.

    Constructed by `make_strict_tool_cache` per-trace. User runners
    annotated `tool_cache: ToolCache` receive this variant via Liskov;
    they don't import `StrictToolCache` directly.

    `_trace_id` is a Pydantic v2 `PrivateAttr` — it lives outside the
    model's validated field set, so the parent's
    `model_config = ConfigDict(extra="forbid")` doesn't reject it.
    The factory `make_strict_tool_cache` populates it after
    construction; `lookup` raises `InvariantViolationError` if it
    runs while `_trace_id` is still the unset sentinel (defense
    against bypassing the factory).
    """

    _trace_id: str = PrivateAttr(default=_UNSET_TRACE_ID)

    def lookup(self, tool_name: str, args: dict[str, Any]) -> Any:
        """Strict lookup: returns the cached value or raises
        `CacheMissError`. A cached `None` value is returned as
        `None` (NOT misclassified as a miss); only true absence
        from the cache map raises.
        """
        # Reuse the parent's keying so `_key` stays the single source
        # of truth for canonicalization (cardinal #6 — one boundary,
        # not two).
        key = self._key(tool_name, args)
        result = self.cache.get(key, _MISSING)
        if result is _MISSING:
            if self._trace_id == _UNSET_TRACE_ID:
                # Bypass-the-factory bug: someone constructed
                # StrictToolCache directly without setting trace_id.
                # Cardinal #1: don't silently emit an empty-string
                # trace_id in the failure record — that would
                # corrupt cross-references in the report.
                from whatif.exceptions import InvariantViolationError

                raise InvariantViolationError(
                    "StrictToolCache.lookup raised CacheMissError but "
                    "_trace_id is unset. Construct via "
                    "`make_strict_tool_cache(entries, trace_id=...)`; "
                    "direct StrictToolCache(...) construction is not "
                    "supported."
                )
            raise CacheMissError(
                trace_id=self._trace_id,
                tool_name=tool_name,
                arg_count=len(args),
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
    or equivalent canonicalization). `trace_id` MUST be non-empty;
    the factory rejects empty strings to defend against the empty-
    string-fallback path that would silently corrupt failure-record
    cross-references.

    The factory exists so the pipeline doesn't have to know about
    `_trace_id` private-attribute mechanics — it just calls
    `make_strict_tool_cache(entries, trace_id=...)` and hands the
    result to the runner. Mutating `_trace_id` post-construction is
    the documented Pydantic v2 pattern for `PrivateAttr` (the
    attribute is allocated at __init__ but values can be set
    afterwards); a future Pydantic upgrade that forbids mutation
    would surface here at the assignment, not silently in `lookup`.
    """
    if not trace_id:
        raise ValueError(
            "make_strict_tool_cache: trace_id must be non-empty. The "
            "factory captures it for diagnostic context on cache misses; "
            "an empty trace_id would silently produce un-cross-"
            "referenceable failure records (cardinal #1 corruption)."
        )
    cache = StrictToolCache(cache=dict(entries), policy="use-original")
    cache._trace_id = trace_id
    return cache


__all__ = [
    "CacheMissError",
    "StrictToolCache",
    "make_strict_tool_cache",
]
