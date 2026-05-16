"""`whatifd.cache.keying` — cache key construction.

Versioned package: the active version is `v2` (was `v1` through
v0.2.0). PRs that change keying semantics (component set, hashing
scheme, normalization) MUST bump to a new version module rather than
mutate the current one. Keys produced by different versions MUST NOT
collide; the version prefix on the emitted key string makes the
distinction grep-able.

The active version is re-exported here so call sites import from
`whatifd.cache.keying` (stable surface) rather than
`whatifd.cache.keying.v2` (versioned, may be deprecated in a future
release).

## v1 -> v2 (F-2.1 fix, v0.2.1)

v2 adds `original_output_hash` and `replayed_output_hash` to
`CacheKeyComponents`. v1 omitted these, so two scoring calls for the
same trace_id + cohort + input but different replayed outputs hashed
to the same key and returned stale cached results — a silent wrong
verdict. v1 keys (prefix `v1:`) and v2 keys (prefix `v2:`) never
collide; persisted v1 cache entries become unreachable on upgrade,
producing a one-time wave of cache misses that re-score correctly.

`whatifd.cache.keying.v1` is retained in-tree for migration tooling
(operators inspecting old `meta.json` files referencing v1); all new
construction goes through v2.
"""

from whatifd.cache.keying.v2 import (
    CACHE_KEY_VERSION,
    CacheKeyComponents,
    build_cache_key,
)

__all__ = ("CACHE_KEY_VERSION", "CacheKeyComponents", "build_cache_key")
