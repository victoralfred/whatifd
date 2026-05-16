"""Cache key construction — v2.

F-2.1 (production-hardening review 2026-05-16) fix. v1 omitted the
original-output and replayed-output text from the cache key: two
scoring calls for the same `trace_id` + `cohort` + `input` but
DIFFERENT `replayed_output.text` (re-run after a runner change) hashed
to the same key, so the second call hit cache and returned the first
call's `JudgeResult` — silent wrong delta. v1 fork CLI ships with cache
`mode="off"` so default users were unaffected, but programmatic
callers that enable the cache hit this defect with no warning.

v2 adds `original_output_hash` and `replayed_output_hash` to the
`CacheKeyComponents` schema; both shipped scorer adapters
(`whatifd-inspect-ai`, `whatifd.adapters.stub`) populate them via
`_hash16("output", ...)` over the output text. v1 and v2 keys never
collide because the version prefix differs (`v1:` vs `v2:`); existing
v1 cache entries become unreachable on upgrade (cache miss → re-score,
which is the correct behavior — they were silently wrong).

## Migration

There is no in-place upgrade. v2 is a fresh module; `CACHE_KEY_VERSION`
re-exported from `whatifd.cache.keying.__init__` flips to `"v2"`.
Operators with persisted v1 caches see a one-time wave of misses; the
storage layer's `cache_key_version` field in `meta.json` lets `cache
rebuild` distinguish v1 entries from v2 entries if a cleanup pass is
desired. v1 is preserved in-tree (imports still work) for migration
tooling, but new keying construction goes through v2.

## Versioning discipline

Per `keying/__init__.py`'s versioning rule, future component-set
changes introduce v3 — never mutate v2.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from whatifd.exceptions import InvariantViolationError
from whatifd.serialization import canonical_json_bytes

CACHE_KEY_VERSION = "v2"

_HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{16,}$")


@dataclass(frozen=True, slots=True)
class CacheKeyComponents:
    """All inputs needed for a deterministic v2 cache key.

    Delta from v1: adds `original_output_hash` and
    `replayed_output_hash`. These two hashes close the F-2.1 silent-
    wrong-verdict defect — two calls with identical scorer config and
    identical input but different replayed outputs now produce
    distinct keys, so the second call re-scores rather than returning
    the first call's cached result.

    Adapter responsibility: hash the output text via the adapter's
    chosen 16-char hex helper (the same `_hash16` used for other v1
    fields). The cache-keying module never sees the raw output text
    (cardinal #5 — outputs may carry user content; only their digest
    crosses this boundary).

    All other fields are unchanged from v1 to keep adapter migration
    mechanical (`from whatifd.cache.keying import CacheKeyComponents`
    is the only surface; adapters add the two new keyword arguments).
    """

    whatif_schema_version: str
    whatif_scorer_adapter_version: str
    scorer_type: str
    scorer_package_version: str
    judge_provider: str
    judge_model_id: str
    judge_model_snapshot: str | None
    rendered_prompt_hash: str
    rubric_hash: str
    scoring_parameters_hash: str
    score_case_serialization_version: str
    score_case_hash: str
    original_output_hash: str
    replayed_output_hash: str

    def __post_init__(self) -> None:
        for field_name in (
            "rendered_prompt_hash",
            "rubric_hash",
            "scoring_parameters_hash",
            "score_case_hash",
            "original_output_hash",
            "replayed_output_hash",
        ):
            value = getattr(self, field_name)
            if not _HEX_DIGEST_RE.match(value):
                raise InvariantViolationError(
                    f"CacheKeyComponents.{field_name}={value!r} is not a "
                    "lowercase hex digest of >=16 characters. The adapter "
                    "is responsible for hashing this field before passing "
                    "it to cache keying — passing raw text here would put "
                    "user content into cache filenames (cardinal #5)."
                )


def build_cache_key(components: CacheKeyComponents) -> str:
    """Return the versioned, content-addressed v2 cache key.

    Output format: `v2:<64-char hex digest>`. Same algorithm as v1
    (SHA-256 over canonical JSON of components) — only the component
    set and version prefix differ.
    """
    digest = hashlib.sha256(canonical_json_bytes(asdict(components))).hexdigest()
    return f"{CACHE_KEY_VERSION}:{digest}"
