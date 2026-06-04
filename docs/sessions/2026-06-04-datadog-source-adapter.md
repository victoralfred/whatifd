---
session_id: 2026-06-04-datadog-source-adapter
started_at: 2026-06-04T08:41:48Z
---

## Session start

**User request:** Start P1 of the integrations plan — scaffold the `whatifd-datadog` `TraceSource` adapter (read-only, Datadog LLM Observability Export API), wire it into config + factory, and ship the conformance test, following the langfuse/phoenix adapter conventions.

**Skill files read:**
- .claude/skills/whatifd-design/SKILL.md
- .claude/skills/whatifd-design/references/cascade-catalog.md (datadog/adapter scan + cassette discipline)

**Cardinal rules cited:**
- Rule #5: Datadog span `input`/`output` are user content → wrapped `Sensitive[str]` at projection; `tags`/`meta` PII keys routed through `wrap_pii_attributes`.
- Rule #9: pagination is a streaming generator; thin httpx client, no CPU tricks.
- Rule #10: `cluster_key_support()` returns `()` — no mining DD session/trace ids as cluster keys.
- Rule #1: missing creds / missing time-window / missing package surface as typed `AdapterFactoryError`, never a raw stack trace; the 15-min-default window must error if unset, not silently return an empty cohort.
- Rule #6: the adapter's internal `_SpanLike` shape is free; it must not widen the `RawTrace` public contract.

**Clarifying questions asked:** none this session — the four §6 decisions were locked in the prior turn (httpx client, per-platform CI repos, sink alongside source, #93/#94 first) and R-1 resolved the read-API surface.

**Phase plan position (per references/phases.md):**
- Phase: post-v0.2 adapter expansion (Phase D established the Phoenix adapter; this mirrors it for Datadog).
- Sub-item: P1 of `whatifd-integrations-plan.md` — adapter package + factory/config wiring + conformance test.
- Prerequisites status: R-1 RESOLVED (Export API confirmed, input/output retrievable, dependency = httpx). Residual: live cassette deferred to a follow-up (no real DD org available this session).

## Session end

**Artifacts produced:**
- packages/whatifd-datadog/pyproject.toml, README.md, src/whatifd_datadog/{__init__,source,client}.py, tests/{conftest,test_conformance}.py — new third trace-source adapter (Datadog LLM-Obs Export API), span-iterator-shaped, httpx in [live] extra.
- src/whatifd/config.py — SourceConfig gains dd_from/dd_to/dd_ml_app/dd_query + validator requiring dd_from when adapter='datadog'.
- src/whatifd/adapters/factory.py — `datadog` dispatch branch + `_build_datadog_source` (env creds DD_API_KEY/DD_APP_KEY/DD_SITE; config-validity-before-creds ordering); updated unknown-adapter messages.
- tests/unit/whatifd/adapters/test_factory.py — datadog dispatch / missing-creds / missing-window tests; lazy-load contract extended to whatifd_datadog.
- pyproject.toml — workspace members, sources, dependency-groups.workspace, mypy override all gain whatifd_datadog.
- .claude/skills/whatifd-design/references/cascade-catalog.md — new "Datadog LLM Observability TraceSource adapter" entry.

**Cascade catalog items:**
- Opened: "Datadog LLM Observability TraceSource adapter" — documents the third adapter, R-1 outcome (Export API + httpx, not the SDK), the 15-min-window cardinal-#1 guard, deferred live cassette + P1b sink.

**Gaps surfaced:**
- Live recorded-cassette smoke is deferred (no real DD org this session); the exact tool `span_kind` value + `tool_definitions` shape need confirming against one real response (R-1 residual).

**Doctrine moments:**
- Cardinal #1 (15-min default): chose to REQUIRE dd_from at both the config validator and the factory, so a forgotten time window fails loudly rather than silently returning a near-empty cohort. Ordered the factory's config-validity check before the credential check so a config error reads as a config error.
- Cardinal #5: mirrored Phoenix's ingress-wrap of input/output on every span (root + child) before the classifier sees them; SearchedIO projected then wrapped.
- "More defensible verdict?" test: kept the Datadog *sink* OUT of core (deferred to P1b as a CI-side emitter) — a sink doesn't make any verdict more defensible.

**Notes for the next session:**
- P1b (Datadog verdict sink, CI-side emitter) and the live cassette are the remaining Datadog items. Then P2/P2b (#93/#94) precede the CI marketplace wrappers per the locked plan.
