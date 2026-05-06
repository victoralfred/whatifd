"""Canonical JSON encoding for hash inputs.

Produces deterministic, platform-independent bytes from a Python value
suitable for use as a hash input (cache keys, content-addressed
identifiers, integrity manifests). NOT for artifact serialization — the
artifact-path encoder (`WhatifJSONEncoder`, Phase 5) carries the
cardinal #5 redaction enforcement; this module deliberately does not.

## Why a separate helper

The banned-import lint (Phase 5, per `references/enforcement.md` row 2)
blocks `json.dumps` outside `whatif/serialization/` to enforce that
artifact-path bytes traverse the redaction graph walk. Hash-input bytes
are categorically different:

- They never leave the process as an artifact.
- Their inputs are pre-hashed by the adapter (`rendered_prompt_hash`,
  `score_case_hash`, etc.); no `Sensitive[T]` ever reaches them.
- They are consumed immediately by a hash function, not written to a
  file or sent over a network.

Centralizing canonical encoding in this module gives the cache keying
code (and any future hash-input code) a single source of truth. When
the Phase 5 banned-import lint lands, it will allow `json.dumps`
inside `whatif/serialization/` and block it everywhere else;
everything outside the package imports from here.

## The canonical encoding

`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`
encoded to ASCII bytes.

- `sort_keys=True` — deterministic across dict-insertion-order changes.
- `separators=(",", ":")` — no whitespace; byte-identical regardless of
  Python's default whitespace.
- `ensure_ascii=True` — escape non-ASCII characters; the encoded bytes
  are pure ASCII regardless of the host locale.

These three flags together produce a stable canonical form: same value
in → same bytes out, on every platform, every interpreter, every run.
The CPython contract for these flags has been stable since Python 2.6.

## Versioning note

This helper does NOT carry a version. Callers that hash its output
SHOULD carry their own version (`CACHE_KEY_VERSION` for cache keys,
etc.) so that a future change to the canonical contract — should one
ever be necessary — invalidates the dependent caches via the caller's
version bump rather than silently across all consumers.
"""

from __future__ import annotations

import json
from typing import Any

from whatif.types.sensitive import Sensitive, UnredactedSensitiveError


def canonical_json_bytes(obj: Any) -> bytes:
    """Return the canonical JSON encoding of `obj` as ASCII bytes.

    The output is deterministic across platforms and Python versions
    (CPython contract for `sort_keys` + explicit separators +
    `ensure_ascii` has been stable since 2.6). The caller is
    responsible for ensuring `obj` is JSON-serializable; passing a
    non-serializable value raises `TypeError` from the stdlib encoder.

    Cardinal #5 contract: this function MUST NOT receive `Sensitive[T]`
    instances. The top-level `isinstance(obj, Sensitive)` check catches
    direct misuse (caller passes a `Sensitive` as the entire payload)
    with a clear `UnredactedSensitiveError`. Nested `Sensitive` inside
    a dict/list IS NOT walked here — that's the Phase 5
    `assert_no_unredacted_sensitive` graph walk's job, plus the
    `WhatifJSONEncoder.default()` fallback. For now, a nested
    `Sensitive` reaches `json.dumps` which raises `TypeError` because
    `Sensitive` has no JSON encoder hook (intentional — `Sensitive`'s
    `__reduce__` raises `SensitiveSerializationError` for pickle, and
    no `__json__` is provided). Either way, fail loud, never silent.
    """
    if isinstance(obj, Sensitive):
        raise UnredactedSensitiveError(
            "canonical_json_bytes received a Sensitive[T] instance "
            "directly. Cache keying components must be pre-hashed by the "
            "adapter; raw user content cannot reach the cache key path "
            "(cardinal #5)."
        )
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
