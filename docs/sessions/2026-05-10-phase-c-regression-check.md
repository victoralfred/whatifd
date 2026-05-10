---
session_id: 2026-05-10-phase-c-regression-check
started_at: 2026-05-10T00:00:00Z
---

## Session start

**User request:** Phase C of the v0.2 roadmap — wire the verdict layer to branch on `experiment_shape` so regression-check experiments (no failure cohort, just baseline-vs-baseline-with-change) produce defensible verdicts.

**Cardinal rules cited:**
- #2 (trust floor): floor evaluation runs first, regardless of shape. The regression-check shape only changes which cohorts the floor requires; floor-failure → Inconclusive precedence is unchanged.
- #10 (statistical claims match the design): the failure-rescue shape's `min_failure_improvement_ratio` policy field is structurally inapplicable to regression-check. Routing the guard chain on shape ensures the methodology disclosure matches the experiment shape.

**Phase plan position:** Phase C of v0.2-roadmap.md. Phase A (schema) merged as `d0f7e29`; Phase B (config-loaded score_fn) merged as `376f420`. This PR branches off `376f420`.

## Session end

**Artifacts produced:**
- `src/whatifd/decision/verdict.py`: new `_REGRESSION_CHECK_GUARDS`, `_guards_for_shape`, `_required_cohorts_for_shape`. `compute_verdict` gains `experiment_shape` keyword arg with `failure_rescue` default.
- `src/whatifd/pipeline.py`: `run_pipeline` passes `runtime.experiment_shape` to `compute_verdict`.
- `tests/unit/whatifd/decision/test_verdict.py`: new `TestRegressionCheckShape` class — 6 tests covering Ship / DontShip / Inconclusive paths, cohort-required-by-shape semantics, and back-compat.
- `.claude/skills/whatifd-design/references/cascade-catalog.md`: Phase C resolved entry.
- `CHANGELOG.md`: Phase C section under [Unreleased].
- `docs/sessions/2026-05-10-phase-c-regression-check.md`: this file.

**Cascade catalog items:**
- Resolved: "Phase C — regression_check experiment shape: shape-aware guard chain + required_cohorts" (2026-05-10).

**Gaps surfaced:**
- New walkthrough fixture (#7) documenting the regression-check shape end-to-end is deferred. The verdict layer ships now; a fully-rendered walkthrough takes longer (synthetic trace fixture + golden report) and shouldn't gate the policy work.
- The CLI config layer doesn't yet expose `experiment_shape` — operators using `whatifd fork` still get failure-rescue. Wiring `experiment_shape` through `WhatifConfig` is the natural follow-up; this PR is verdict-layer-only.
- A pre-existing circular-import issue (whatifd.serialization ↔ whatifd.cache.lock) surfaces when running individual decision tests in isolation but not when running the full suite. Not from this PR; documented for the next session that touches the import graph.

**Doctrine moments:**
- Considered widening the cohort literal (`failure | baseline | treatment`) for regression-check. Declined: keeping the literal at `failure | baseline` and treating "regression-check has no failure cohort" as data-shape (presence) rather than schema-shape (literal value) is doctrinally cleaner. The wire shape stays stable across experiment shapes; only the verdict-policy-side interpretation changes.
- Considered making `compute_verdict` derive shape from the cohort set (e.g., "no failure cohort → regression_check"). Declined: shape is a manifest-time declaration, not a runtime inference. Cardinal #10 — methodology disclosed in advance, not back-derived from outcomes.

**Notes for the next session:**
- Phase D — Phoenix tracer adapter — is the next big surface. Independent of Phase C.
- Walkthrough fixture #7 (regression-check) can land as its own small PR.
- Config-layer `experiment_shape` field on `WhatifConfig` would close the CLI loop for regression-check users.
