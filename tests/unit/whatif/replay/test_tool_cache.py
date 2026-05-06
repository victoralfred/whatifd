"""Tests for `whatif.replay.tool_cache` — Phase 6.2 strict per-trace
tool cache.

Pin properties:

1. `make_strict_tool_cache` returns a `StrictToolCache` (a `ToolCache`
   subclass — Liskov: user code annotated `ToolCache` accepts it).
2. `StrictToolCache.lookup` returns the cached value on hit.
3. `StrictToolCache.lookup` raises `CacheMissError` on miss (NOT
   returns `None` — that's the parent contract's behavior, which
   the strict subclass intentionally diverges from).
4. `CacheMissError` carries `trace_id`, `tool_name`, `args`.
5. `CacheMissError.details_for_failure()` returns the
   `Mapping[str, JsonPrimitive]` shape the pipeline projects to
   `ReplayFailure(details=...)`.
6. `details_for_failure()` does NOT include `args` — sensitive-data
   safety (cardinal #5 boundary).
7. The strict cache uses the parent's `_key` for canonicalization so
   miss detection is consistent with how the public contract keys
   entries.
"""

from __future__ import annotations

import pytest

from whatif.contract import ToolCache
from whatif.replay.tool_cache import (
    CacheMissError,
    StrictToolCache,
    make_strict_tool_cache,
)

# ---------------------------------------------------------------------------
# Factory + Liskov substitutability
# ---------------------------------------------------------------------------


class TestFactory:
    def test_factory_returns_strict_subclass(self) -> None:
        c = make_strict_tool_cache({}, trace_id="t-1")
        assert isinstance(c, StrictToolCache)
        # Liskov: a user runner annotated `tool_cache: ToolCache`
        # accepts the strict variant.
        assert isinstance(c, ToolCache)

    def test_factory_captures_trace_id(self) -> None:
        c = make_strict_tool_cache({}, trace_id="t-42")
        assert c._trace_id == "t-42"

    def test_factory_uses_use_original_policy(self) -> None:
        # Cardinal contract: v0.1 is `use-original` policy. The strict
        # cache stamps it; the alternative `live` policy is a v0.3+
        # feature.
        c = make_strict_tool_cache({}, trace_id="t-1")
        assert c.policy == "use-original"

    def test_factory_copies_entries(self) -> None:
        # Defense: the factory dict-copies entries so a caller
        # mutating the input dict afterwards doesn't bleed into the
        # cache. (Consistent with frozen-dataclass conservatism — even
        # though Pydantic would re-validate, the explicit copy keeps
        # the intent clear at the boundary.)
        entries: dict[str, object] = {"k": "v"}
        c = make_strict_tool_cache(entries, trace_id="t-1")
        entries["k"] = "mutated"
        assert c.cache["k"] == "v"


# ---------------------------------------------------------------------------
# Strict lookup behavior
# ---------------------------------------------------------------------------


class TestStrictLookup:
    def test_hit_returns_value(self) -> None:
        # Build the cache via the parent's keying so miss-detection
        # is consistent with the public contract's hit path.
        parent = ToolCache(cache={}, policy="use-original")
        key = parent._key("get_weather", {"city": "Tokyo"})
        c = make_strict_tool_cache({key: {"temp": 20}}, trace_id="t-1")

        result = c.lookup("get_weather", {"city": "Tokyo"})
        assert result == {"temp": 20}

    def test_miss_raises_cache_miss_error(self) -> None:
        c = make_strict_tool_cache({}, trace_id="t-1")
        with pytest.raises(CacheMissError) as excinfo:
            c.lookup("get_weather", {"city": "Tokyo"})
        assert excinfo.value.trace_id == "t-1"
        assert excinfo.value.tool_name == "get_weather"
        assert excinfo.value.tool_args == {"city": "Tokyo"}

    def test_miss_with_different_args_raises(self) -> None:
        # Pin: hit on (tool, args_a) and miss on (tool, args_b). The
        # strict cache disambiguates by the full canonical key.
        parent = ToolCache(cache={}, policy="use-original")
        key_a = parent._key("get_weather", {"city": "Tokyo"})
        c = make_strict_tool_cache({key_a: {"temp": 20}}, trace_id="t-1")

        # Hit
        assert c.lookup("get_weather", {"city": "Tokyo"}) == {"temp": 20}
        # Miss on different args
        with pytest.raises(CacheMissError) as excinfo:
            c.lookup("get_weather", {"city": "Paris"})
        assert excinfo.value.tool_args == {"city": "Paris"}


# ---------------------------------------------------------------------------
# CacheMissError shape
# ---------------------------------------------------------------------------


class TestCacheMissError:
    def test_message_includes_trace_id_and_tool(self) -> None:
        e = CacheMissError(trace_id="t-1", tool_name="get_weather", args={"city": "Tokyo"})
        msg = str(e)
        assert "t-1" in msg
        assert "get_weather" in msg

    def test_message_does_not_leak_args_values(self) -> None:
        # Defense: the diagnostic message names the tool and arg
        # COUNT, but not the arg VALUES — args may carry sensitive
        # user content (PII, credentials). Operators debugging a miss
        # have the trace at hand for full context; the message stays
        # safe to emit to logs.
        e = CacheMissError(
            trace_id="t-1",
            tool_name="lookup_user",
            args={"email": "alice@example.com", "password": "hunter2"},
        )
        msg = str(e)
        assert "alice@example.com" not in msg
        assert "hunter2" not in msg

    def test_details_for_failure_shape(self) -> None:
        # Pin: the details map only carries `tool_name` (per the
        # registry's `tool_cache_miss` required_details). args are
        # NOT propagated — sensitive-data boundary.
        e = CacheMissError(
            trace_id="t-1",
            tool_name="get_weather",
            args={"city": "Tokyo", "user_id": "u-99"},
        )
        details = e.details_for_failure()
        assert details == {"tool_name": "get_weather"}
        assert "args" not in details
        assert "user_id" not in details
        assert "city" not in details

    def test_details_for_failure_satisfies_registry(self) -> None:
        # Cardinal #1: the registry's `tool_cache_miss` spec lists
        # `required_details=("tool_name",)`. The details map
        # produced here MUST contain that key — `make_failure_record`
        # would raise otherwise at projection time.
        from whatif.decision.failure_codes import FAILURE_CODE_REGISTRY

        spec = FAILURE_CODE_REGISTRY["tool_cache_miss"]
        e = CacheMissError(trace_id="t-1", tool_name="get_weather", args={})
        details = e.details_for_failure()
        for key in spec.required_details:
            assert key in details, (
                f"details_for_failure() missing required-details key {key!r} "
                "from FAILURE_CODE_REGISTRY['tool_cache_miss'] spec"
            )

    def test_args_dict_copied(self) -> None:
        # Mutating the input args after construction must not
        # affect the captured CacheMissError state.
        args: dict[str, object] = {"k": "v"}
        e = CacheMissError(trace_id="t-1", tool_name="f", args=args)
        args["k"] = "mutated"
        assert e.tool_args == {"k": "v"}
