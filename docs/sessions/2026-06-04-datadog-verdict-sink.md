---
session_id: 2026-06-04-datadog-verdict-sink
started_at: 2026-06-04T13:20:00Z
---

## Session start

**User request:** Start P1b of the integrations plan — the Datadog verdict *sink*: a CI-side emitter that reads the ReportV01 JSON and pushes verdict + cohort metrics to Datadog. Locked decision #3: build it, but keep it OUT of core.

**Skill files read:** SKILL.md + cascade-catalog.md (carried from the datadog adapter sessions).

**Cardinal rules cited:** the "more defensible verdict?" test (a sink fails it → out of core); #1 (missing/malformed report = actionable error; null numerics skipped not zeroed; emission soft-fails so it can't redden a verdict).

**Phase plan position:** integrations plan P1b. Prereqs: P1 (adapter) merged (#121, #122).

## Session end

**Artifacts produced:**
- `packages/whatifd-datadog/src/whatifd_datadog/emit.py` — `report_to_metrics`, `DatadogMetricsClient` (v1 `/api/v1/series`, agentless, DD_API_KEY), `emit_report`, and `main` (the `whatifd-datadog-emit` console script). Soft-fail default; `--strict`/`--dry-run`/`--tag`.
- `packages/whatifd-datadog/pyproject.toml` — `[project.scripts] whatifd-datadog-emit`.
- `packages/whatifd-datadog/tests/test_emit.py` — 12 tests (projection, null-skip, ratios, blocking count, dry-run, error paths, CLI soft/strict-fail). No network.
- `packages/whatifd-datadog/README.md` — "Emitting verdict metrics" section.
- `CHANGELOG.md` + cascade-catalog — P1b recorded.

**Cascade catalog items:**
- Updated: the Datadog adapter entry — P1b verdict sink DONE; only the HTTP-level cassette remains deferred.

**Gaps surfaced:** none new. (The emitter's HTTP path to `/api/v1/series` has no recorded cassette — same content-scrubbed-body blocker as the read client; deferred together.)

**Doctrine moments:** kept the sink OUT of core (it only reads the already-written report; emitting metrics doesn't make any verdict more defensible) and made it soft-fail by default so a metrics outage can never flip a green verdict red — the verdict stays the `whatifd fork` exit code, the emitter is a downstream reporter.

**Notes for next session:** P2/P2b (#93 CLI-emits-report-paths, #94 marker-comments) precede the CI marketplace wrappers (P3 GitHub / P4 GitLab / P5 Travis), per the locked plan.
