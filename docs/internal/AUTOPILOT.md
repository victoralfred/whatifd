# whatifd autopilot — autonomous hardening loop (cycle 2)

> Operating contract for the unattended `/loop`. The human is **out of the loop**
> except for the **final `main` merge** and the **employment-conflict surface**
> (see Boundaries). Authorized 2026-06-13 by the maintainer.

## Goal

Iterate until the whatifd backlog is genuinely complete: every known bug fixed,
every promoted feature implemented with tests, all documentation current, and a
green, mergeable single PR ready for human review. Do not fake completion — a
task is done only when its tests pass and CI is green.

## Branch & PR model

- **Integration branch:** `auto/whatifd-hardening`.
- **The single PR:** `auto/whatifd-hardening` → `main`. Its body is the live
  task board; update it every completed task. **A human merges this to `main`** —
  the loop never does.
- **Per task:** short branch `auto/<task-id>-<slug>` off the integration branch
  → small PR into `auto/whatifd-hardening` → **the loop squash-merges it once
  that sub-PR's CI is green** (auto-merge sub-tasks, authorized). Then update the
  single PR body and move on. Never push to `main`; never merge the single PR.

## Per-iteration protocol

1. **Sync.** `git fetch`; rebase/merge `main` into the integration branch if it
   moved (e.g. once the cycle-1 closeout PR #146 lands).
2. **Select** the highest-priority not-done task from the Backlog.
3. **Branch** off the integration branch.
4. **Implement** with tests. For doctrine-guarded modules
   (`src/whatifd/{decision,statistical,report}`, `docs/schema/`) read
   `.claude/skills/whatifd-design/references/doctrine.md` +
   `cascade-catalog.md` first and record a cascade-catalog entry in the same
   sub-PR (full-autonomy: make the design call under the doctrine, but write it
   down).
5. **Verify.** Run `uv run pytest` (full suite), `uv run mypy src`, `ruff`, and
   the relevant integration tests. Paste results in the sub-PR.
6. **Land.** Open the sub-PR into `auto/whatifd-hardening`; when its CI is green,
   squash-merge it. If CI is red, fix before starting the next task — never leave
   the integration branch red.
7. **Update** the single PR body (task board: done / in-progress / next) and
   print a one-line status. Keep `consistency_check.py --repo .` and
   `--self-test` at exit 0 (cardinal rule 7 still applies).
8. **Stall rule.** Two iterations with no landed change on a task → mark it
   BLOCKED with a diagnosis and move on; if the whole board stalls, stop and
   summarize.

## Backlog (priority order; full-autonomy scope)

**P0 — correctness & hygiene (do first):**
- Bug hunt: failing/--xfail tests, `mypy` gaps, `TODO`/`FIXME` in
  `src/whatifd/`, any open GitHub issues. Fix with regression tests.
- GAP-007 option (a) proper fix (optional, supersedes the checker exclusion):
  make the renderer emit a resolving manifest target in sample context, then
  regenerate walkthrough fixtures so the fidelity tests pass.

**P1 — self-contained features (deferred catalog §, implement + test):**
- §13 pre-run power/MDE disclosure · §14 K-replay flake-stability ·
  §15 `exec:` stdio runner lane (spec drafted in
  `docs/internal/drafts/runner-contract-exec-spec.md`) · §16 OTel GenAI source
  adapter · §17 LangSmith source adapter · §18 cost/latency endpoints.
- Deferred §1–§10 hygiene items as capacity allows (conformance harness export,
  PEP440 validator, typed ToolSpan, real bootstrap §4, cluster scenarios §5,
  CI determinism gate, delta_fn→Scorer, verdict-change matrix, json-dumps
  allowlist).

**P2 — doctrine-guarded features (design under doctrine, cascade-catalog entry each):**
- §11 cluster-paired bootstrap math · §12 judge-vs-human calibration gate ·
  §19 `ReportV01` signing/provenance.

**P3 — documentation completeness:**
- Reconcile every `docs/` page and the site to whatever P1/P2 ships; keep
  `consistency_check` green; update CHANGELOG `[Unreleased]` only.

## Boundaries (held even under full autonomy)

- **Never push to `main`; never merge the single PR.** Final merge is the human's.
- **Never bump versions, tag, release, or publish.**
- **CHANGELOG:** `[Unreleased]` only; never touch released sections.
- **Employment-conflict surface (GAP-025):** build the Datadog *technical*
  integration neutrally, but make **no** positioning/marketing/comparison claims
  about Datadog and take no action on the marketing surface — that stays human.
- **Secrets:** never commit tokens/credentials; stop and flag if found.
- **Honesty:** a red CI or a failing test is reported, not hidden; no cosmetic
  change to manufacture progress.

## Done

The loop is complete when: backlog P0–P3 are each DONE or BLOCKED(reason); the
single PR is green (CI passing, `consistency_check --repo .` = 0, `--self-test`
= 0, full `pytest` green); and the PR body's final task board + a closeout
summary (what shipped, what's blocked, what the human should review) are
written. Then stop and notify — the human reviews and merges.
