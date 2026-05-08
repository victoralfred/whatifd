"""Adapter factory — config name → adapter instance.

Phase 10 CLI wiring foundation. The CLI's `_run_fork_pipeline`
needs to construct a concrete `TraceSource` and `Scorer` from the
adapter names in the validated `WhatifConfig`. This module owns
that dispatch.

## Why a registry, not a switch in cli.py

Three reasons:

1. **Lazy import.** Real adapter packages (`whatif_langfuse`,
   `whatif_inspect_ai`) MUST NOT be imported by core code paths
   (cardinal-enforced lazy-load contract pinned by
   `tests/unit/whatif/adapters/test_protocols.py::
   test_core_modules_do_not_load_real_adapter_packages`). The
   factory imports them inside the dispatch function so `import
   whatif.cli` doesn't drag them in transitively.
2. **Test isolation.** Wiring tests instantiate the stub adapter
   without spinning up a real Langfuse client. The factory's
   stub branch is the contract surface for that.
3. **Single source of truth.** Adapter name strings appear in the
   user's YAML, the config schema, the cascade catalog, and the
   wiring layer. Centralizing the dispatch here means adding a
   new adapter is one line + one branch + one test, not a
   project-wide grep.

## Why credentials read from the environment, not config

Langfuse credentials are secrets. v0.1's `WhatifConfig` is a
plain YAML/JSON file commonly checked into source control or PR
templates. Reading `LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` /
`LANGFUSE_SECRET_KEY` from the environment matches the Langfuse
SDK's own convention and keeps secrets out of repo files. A
follow-up may add a config-block override for non-default hosts,
but the secret material stays in env.

## Failure surface

Construction failures raise `AdapterFactoryError`. The CLI
catches this at the dispatcher and exits with the setup-failure
code (cardinal #1: setup failures are structured signals to the
operator, not stack traces).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from whatif.adapters.stub import StubScorer, StubTraceSource

if TYPE_CHECKING:
    from whatif.adapters.protocols import Scorer, TraceSource
    from whatif.config import ScorerConfig, SourceConfig


class AdapterFactoryError(Exception):
    """Raised when an adapter cannot be constructed.

    Carries an actionable message naming the adapter, the missing
    requirement, and the env var or config field that would fix
    it. The CLI converts the message into stderr output with the
    setup-failure exit code.
    """


_LANGFUSE_HOST_ENV_KEYS = ("LANGFUSE_HOST", "LANGFUSE_BASE_URL")
_LANGFUSE_CRED_ENV_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def build_trace_source(cfg: SourceConfig) -> TraceSource:
    """Construct a `TraceSource` from `cfg.source`.

    Supported adapters in v0.1:
    - `"stub"` — synthetic in-memory source. Useful for end-to-end
      CLI tests and for the v0.1 release smoke. Yields zero traces
      (callers that need fixture data should construct
      `StubTraceSource(specs=...)` directly, not via this
      factory).
    - `"langfuse"` — real Langfuse adapter. Reads
      `LANGFUSE_HOST` (or `LANGFUSE_BASE_URL`) and
      `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` from the
      environment. Constructs the Langfuse SDK client lazily.
    """
    name = cfg.adapter
    if name == "stub":
        return StubTraceSource(specs=[])
    if name == "langfuse":
        return _build_langfuse_source()
    raise AdapterFactoryError(
        f"Unknown trace-source adapter {name!r}. v0.1 supports 'stub' and 'langfuse'."
    )


def build_scorer(cfg: ScorerConfig) -> Scorer:
    """Construct a `Scorer` from `cfg.scorer`.

    Supported adapters in v0.1:
    - `"stub"` — synthetic scorer that returns zero. Useful for
      end-to-end CLI tests; production runs should use a real
      scorer.
    - `"inspect_ai"` — real Inspect AI adapter. Requires the
      caller to wire a `score_fn`; v0.1 does NOT load `score_fn`
      from config (it's user code, not config data). The CLI
      surfaces this with an actionable error pointing at the
      programmatic `run_pipeline` path; full config-loaded
      score_fn is a v0.2 surface (cascade-catalog "Scorer
      score_fn config-loadable").
    """
    name = cfg.adapter
    if name == "stub":
        # `StubScorer.score_fn` defaults to a no-op that returns
        # 0.0 for every case (see `whatif.adapters.stub
        # ._default_score_fn`). That's the right CLI default — a
        # smoke run with no judge configured produces deterministic
        # zero-delta scoring, which the pipeline interprets as
        # "no improvement, no regression."
        return StubScorer()
    if name == "inspect_ai":
        raise AdapterFactoryError(
            "v0.1 'inspect_ai' scorer requires a programmatic score_fn that "
            "config cannot load (it's user code). Use the run_pipeline API "
            "shown in docs/getting-started.md, or wait for the v0.2 "
            "scorer.score_fn config field. Current scorer.adapter='inspect_ai'."
        )
    raise AdapterFactoryError(
        f"Unknown scorer adapter {name!r}. v0.1 CLI supports 'stub' "
        "(programmatic API supports 'inspect_ai' via run_pipeline)."
    )


def _build_langfuse_source() -> TraceSource:
    host = next((os.environ.get(k) for k in _LANGFUSE_HOST_ENV_KEYS if os.environ.get(k)), None)
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not host or not public_key or not secret_key:
        missing = []
        if not host:
            missing.append("LANGFUSE_HOST (or LANGFUSE_BASE_URL)")
        if not public_key:
            missing.append("LANGFUSE_PUBLIC_KEY")
        if not secret_key:
            missing.append("LANGFUSE_SECRET_KEY")
        raise AdapterFactoryError(
            "langfuse adapter requires environment credentials; missing: "
            + ", ".join(missing)
            + ". Set these env vars before running `whatif fork`, or "
            "switch source.adapter to 'stub' for a credentialless smoke."
        )

    # Lazy import — keeps the cardinal-enforced lazy-load contract
    # (test_core_modules_do_not_load_real_adapter_packages). This
    # function only runs at CLI fork-time, never at module import.
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found,unused-ignore]
        from whatif_langfuse import (
            LangfuseTraceSource,  # type: ignore[import-untyped,unused-ignore]
        )
    except ImportError as exc:
        raise AdapterFactoryError(
            f"langfuse adapter import failed: {exc}. Install the package "
            "with `pip install whatif-langfuse`."
        ) from exc

    client = Langfuse(host=host, public_key=public_key, secret_key=secret_key)
    source: TraceSource = LangfuseTraceSource(
        api=client.api,
        # Default cohort classifier: tags-based, mirroring the
        # whatif-langfuse README. v0.2 adds config-driven
        # classifier selection.
        cohort_classifier=lambda t: (
            "failure" if "failure" in (getattr(t, "tags", None) or []) else "baseline"
        ),
    )
    return source


__all__ = [
    "AdapterFactoryError",
    "build_scorer",
    "build_trace_source",
]
