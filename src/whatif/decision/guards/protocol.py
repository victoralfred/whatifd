"""`Guard` Protocol + `run_guards` chain composer.

A guard is a pure function with the shape:

    def guard(
        cohort_results: Sequence[CohortResult],
        policy: DecisionPolicy,
    ) -> list[DecisionFinding]: ...

It returns 0+ findings. The chain composer concatenates findings from
every guard in registration order so the verdict layer (Phase 2.6) sees
a single flat list. Order in the output list mirrors registration order
within each guard's findings — guards that emit multiple findings keep
them adjacent.

Guards are deliberately a Protocol, not an ABC: any callable that
matches the signature qualifies. This keeps the registration site
free of inheritance ceremony and lets new guards land as plain
functions in their own modules.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from whatif.exceptions import InvariantViolationError
from whatif.types.cohort import CohortResult
from whatif.types.finding import DecisionFinding
from whatif.types.policy import DecisionPolicy


@runtime_checkable
class Guard(Protocol):
    """One link in the guard chain.

    Every guard module exports a callable matching this signature. The
    callable's `__name__` is used by `run_guards` for diagnostic logs
    and by tests asserting registration order.

    `@runtime_checkable` enables `isinstance(g, Guard)` for diagnostic
    use. Caveat: Python cannot verify call signatures at runtime, so
    the runtime `isinstance` check effectively asserts only that
    `__call__` exists (i.e., `callable(x)`). The full signature
    contract is type-system-enforced; the runtime check is a smoke
    test, not a guarantee.
    """

    def __call__(
        self,
        cohort_results: Sequence[CohortResult],
        policy: DecisionPolicy,
    ) -> list[DecisionFinding]: ...


def run_guards(
    guards: Sequence[Guard],
    cohort_results: Sequence[CohortResult],
    policy: DecisionPolicy,
) -> list[DecisionFinding]:
    """Run every guard in order; concatenate findings.

    Each guard is invoked with the SAME `cohort_results` and `policy` —
    guards must not mutate either. The output is a fresh list; callers
    may extend or filter it without affecting per-guard outputs.

    A guard that raises is a bug per the discipline noted in the package
    docstring. We deliberately do NOT swallow exceptions here — an
    unexpected raise should surface immediately rather than silently
    drop findings. Per cardinal #1, expected failures are data
    (FailureRecord); unexpected failures are bugs (let them propagate).

    Each guard MUST return a fresh `list` — not a class-level mutable
    or a list shared with a sibling guard. The check below catches the
    cross-guard sharing case by `is` identity, comparing the actual
    returned list objects. A guard returning the same list across
    separate `run_guards` calls isn't caught here (different
    invocations, different state); that pattern is rare in practice
    and code review is the safety net.

    Implementation note: the contract is "fresh list", not "distinct
    id". `id()` would false-positive if CPython recycled the address
    of a GC'd list. We hold strong references to every returned list
    in `seen_lists` for the duration of the call, which prevents any
    of them from being collected and keeps `is` comparison meaningful.
    """
    findings: list[DecisionFinding] = []
    # Strong references to every returned list — prevents GC, which
    # in turn prevents id recycling, which keeps `is` comparison sound.
    seen_lists: list[list[DecisionFinding]] = []
    for guard in guards:
        result = guard(cohort_results, policy)
        for prior in seen_lists:
            if result is prior:
                raise InvariantViolationError(
                    f"guard {guard!r} returned a list shared with another "
                    "guard in the same run_guards call. Each guard must "
                    "return a fresh list to prevent cross-guard mutation. "
                    "See the protocol.py docstring for the contract."
                )
        seen_lists.append(result)
        findings.extend(result)
    return findings
