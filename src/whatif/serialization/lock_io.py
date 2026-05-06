"""Lock-file deserialization helpers.

Phase 3.3 (cache lock) reads `.whatif/cache/.lock` JSON content to
inspect the recorded holder for stale-detection. The deserialization
lives here (under `whatif/serialization/`) rather than inline in
`whatif/cache/lock.py` so that:

1. **Symmetry with `canonical_json_bytes`**: writing canonical bytes
   already lives in this package; reading them back lives next to
   it. A future banned-import lint pass that broadens to cover all
   `json` usage outside the serialization layer (not just `dumps`)
   will not need to chase `json.loads` calls scattered across the
   codebase.
2. **Typed boundary**: callers receive a typed
   `LockFileContent | None` rather than a `dict[str, Any]` that
   might or might not have the right keys. Cardinal #6 (no
   `dict[str, Any]` at typed boundaries) is enforced at this
   helper rather than at every call site.

The helper accepts `bytes` (the canonical write surface) but tolerates
`str` for the file-handle read path that `_try_takeover_if_stale`
uses internally — the caller passes whatever it has.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whatif.cache.lock import LockFileContent


def parse_lock_file_content(raw: str | bytes) -> LockFileContent | None:
    """Parse a lock-file JSON payload into a typed `LockFileContent`.

    Returns `None` when the payload is empty (zero-byte file from a
    crashed-during-write residue) or unparseable (corrupted JSON,
    missing required fields, wrong field types). The caller treats
    `None` as "stale by definition — no provenance to respect."

    A successful return guarantees all four `LockFileContent` fields
    are present and of the correct type. The cardinal #6 boundary
    is the dataclass constructor; this helper raises nothing back to
    the caller — invalid input maps to `None` so the caller's
    decision logic has a clean two-valued contract.
    """
    # Local import to avoid circular dependency: lock module imports
    # from this module at module-load time; the dataclass type only
    # needs to be available inside this function body.
    from whatif.cache.lock import LockFileContent

    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return LockFileContent(
            pid=int(parsed["pid"]),
            process_start_time=float(parsed["process_start_time"]),
            hostname=str(parsed["hostname"]),
            started_at=str(parsed["started_at"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def parse_lock_file_for_diagnostics(raw: str | bytes) -> dict[str, object]:
    """Parse the lock file's top-level fields for diagnostic-message
    enrichment. Returns an empty dict on any parse error.

    Distinct from `parse_lock_file_content`: this helper is for
    `_build_locked_error`'s message construction. The blocking
    condition (lock held) is already established by the caller; we
    just want the recorded `pid`/`hostname`/`started_at` strings to
    enrich the operator-facing message. Strict typing isn't needed
    here — we only call `.get(...)` on the result for string
    formatting.
    """
    if not raw:
        return {}
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(result, dict):
        return {}
    return result
