"""Deterministic-subset extraction — Phase 9A.3.

Reads the committed JSON Schema (`v0.1.schema.json`) to discover
which top-level `ReportV01` fields are tagged `x-deterministic: true`
and projects a serialized report down to that subset. The
deterministic subset is what the determinism CI test compares
byte-for-byte across re-runs of the same fixture; non-deterministic
fields (timestamps, environment fingerprints, sensitive-unwrap
audit logs) live under `runtime` and are excluded.

## Why schema-driven, not a hardcoded list

The `x-deterministic` annotations live on the schema; the schema
is the source of truth (cardinal #4: determinism is opt-in per
field). Hardcoding a list here would drift the moment the schema
adds or removes a tagged field — the extractor must follow the
schema, not the other way around.

## Cardinal #4 alignment

Determinism is opt-in **per field**, not per object. v0.1 ships
top-level scalar/list fields tagged `x-deterministic: true` and
the entire `runtime` subtree tagged `false`. The extractor
operates at the top level only — nested-field determinism (e.g.,
`runtime.config_hash` is deterministic even though `runtime` is
not) is the determinism *claim*, not the comparison surface. The
report's deterministic subset is the part that should be byte-
equal across re-runs; for v0.1 that's everything except `runtime`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "report" / "schema" / "v0.1.schema.json"


@lru_cache(maxsize=1)
def _deterministic_field_names() -> frozenset[str]:
    """Read the schema once and cache the set of top-level field
    names tagged `x-deterministic: true`. Cached because the schema
    is a committed file — it doesn't change at runtime."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    properties = schema.get("properties", {})
    return frozenset(
        name for name, prop in properties.items() if prop.get("x-deterministic") is True
    )


def deterministic_field_names() -> frozenset[str]:
    """Public accessor for the cached set. Tests use this to assert
    coverage against the schema (e.g., \"the determinism test must
    cover every field tagged True\")."""
    return _deterministic_field_names()


def extract_deterministic_subset(report_dict: Mapping[str, Any]) -> dict[str, Any]:
    """Project `report_dict` down to the deterministic subset.

    `report_dict` is the JSON-serialized form (a `dict[str, Any]`) of
    a `ReportV01`. Returns a new dict containing only the keys whose
    schema property carries `x-deterministic: true`. Non-deterministic
    keys (currently just `runtime`) are dropped.

    This function does NOT serialize — pass it the result of
    `json.loads(WhatifJSONEncoder.encode(report))` (or equivalent).
    Splitting serialization from extraction keeps the determinism
    test composable with any future JSON-shape changes.
    """
    keep = _deterministic_field_names()
    return {k: v for k, v in report_dict.items() if k in keep}


__all__ = [
    "deterministic_field_names",
    "extract_deterministic_subset",
]
