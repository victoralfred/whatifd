"""`whatifd.scorer_loader` — resolve `scorer.score_fn` to a callable.

Phase B of the v0.2 roadmap. Mirrors `whatifd.runner_loader` for the
`scorer.score_fn` config field. Closes the v0.1 setup-failure cliff
where `scorer.adapter: inspect_ai` couldn't be reached from YAML.

## Doctrine

- **Cardinal #1 (failure-as-data):** every resolution failure produces
  a structured `ScorerLoadError` with the bad reference quoted; never
  an unhandled `ImportError` / `AttributeError`.
- **Cardinal #6 (boundary discipline):** the loader returns a callable
  with no inspection of its signature beyond `callable()` — the
  Inspect AI score-fn shape is the user's contract with their own
  Inspect codebase, not whatifd's. Validation happens at call time
  inside `InspectAIScorer.score`.

## Format

`python:<module.path>:<attr>`. Same shape as `target.runner`. Loader
is a separate module (not a shared helper) because the error messages
name the config field — `scorer.score_fn` vs `target.runner` —
producing actionable hints. Sharing a helper would require threading
the field name through every error string.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

from whatifd._dynamic_import import ensure_cwd_importable

# `Callable` is imported unconditionally (not under TYPE_CHECKING) so
# the runtime annotation surface is unambiguous: `from __future__ import
# annotations` defers evaluation, but a future linter or runtime
# inspection (`typing.get_type_hints`) needs Callable resolvable at
# import time. Cost is one extra collections.abc symbol; benefit is
# the discipline reads correctly without the parenthetical caveat.


class ScorerLoadError(Exception):
    """Raised when `scorer.score_fn` cannot be resolved.

    Mirrors `RunnerLoadError`. Names the bad input + the failure
    class (bad scheme / bad shape / module not importable /
    attribute missing / not callable) so an operator sees exactly
    what to fix.
    """


_PYTHON_PREFIX = "python:"


def load_score_fn(reference: str) -> Callable[..., object]:
    """Resolve `cfg.scorer.score_fn` to a callable.

    Thin wrapper around `load_python_callable(reference,
    field_name="scorer.score_fn")` — kept as a named entry point so
    the InspectAI factory call site reads at-the-domain rather than
    naming the generic loader.
    """
    return load_python_callable(reference, field_name="scorer.score_fn")


def load_python_callable(reference: str, *, field_name: str) -> Callable[..., object]:
    """Resolve a `python:<module.path>:<attr>` reference to a callable.

    Used by both `scorer.score_fn` (via `load_score_fn`) and
    `source.spans_provider` (Phoenix adapter wiring). Doctrine-review
    iter-1 widened the loader from a single field name to a
    parameterized one so callers can produce field-specific error
    messages WITHOUT downstream `.replace(...)` string-patching (which
    silently no-ops if the upstream message format changes — fragile
    per cardinal #1).

    Raises `ScorerLoadError` on:
    - non-string or empty reference,
    - missing `python:` scheme,
    - malformed body (wrong number of `:` separators),
    - empty module path or attribute name,
    - module import failure,
    - missing attribute on the imported module,
    - resolved attribute is not callable.
    """
    if not isinstance(reference, str) or not reference:
        raise ScorerLoadError(f"{field_name} must be a non-empty string; got {reference!r}.")
    if not reference.startswith(_PYTHON_PREFIX):
        raise ScorerLoadError(
            f"{field_name} {reference!r} has unsupported scheme. v0.2 supports "
            "`python:<module.path>:<attr>` only."
        )

    body = reference[len(_PYTHON_PREFIX) :]
    if body.count(":") != 1:
        raise ScorerLoadError(
            f"{field_name} {reference!r} is malformed. Expected exactly one "
            "`:` separator after the `python:` prefix; got "
            f"{body.count(':')} additional separator(s). Format: "
            "`python:<module.path>:<attr>`."
        )

    module_path, _, attr = body.partition(":")
    if not module_path:
        raise ScorerLoadError(
            f"{field_name} {reference!r} is missing the module path. Format: "
            "`python:<module.path>:<attr>`."
        )
    if not attr:
        raise ScorerLoadError(
            f"{field_name} {reference!r} is missing the attribute name. "
            "Format: `python:<module.path>:<attr>`."
        )

    # Resolve from the user's project root too (see whatifd._dynamic_import):
    # an installed console script doesn't put the invocation dir on sys.path,
    # so a developer's own scorer / spans-provider module would otherwise fail.
    ensure_cwd_importable()
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ScorerLoadError(
            f"{field_name} {reference!r}: module {module_path!r} could not be "
            f"imported ({exc}). Check the module path and that the module is "
            "importable from the current environment or your project root."
        ) from exc

    if not hasattr(module, attr):
        raise ScorerLoadError(
            f"{field_name} {reference!r}: module {module_path!r} has no "
            f"attribute {attr!r}. Check the attribute name and the module's "
            "exports."
        )

    candidate: Callable[..., object] = getattr(module, attr)
    if not callable(candidate):
        raise ScorerLoadError(
            f"{field_name} {reference!r}: resolved {attr!r} is not callable "
            f"(got {type(candidate).__name__})."
        )

    return candidate
