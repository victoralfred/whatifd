---
session_id: 2026-06-04-datadog-real-shape-validation
started_at: 2026-06-04T12:56:22Z
---

## Session start

**User request:** Validate the `whatifd-datadog` adapter against a real Datadog LLM-Obs payload (the P1 live-cassette residual). The DEV/whatif harness had no tool-span instrumentation, so we added `LLMObs.tool()` emission, reingested, and probed the real shape.

**Skill files read:** SKILL.md + cascade-catalog.md (carried from the prior datadog session).

**Cardinal rules cited:** #5 (SearchedIO wrapped at ingress — confirmed against real shape), #10 (cluster keys empty), #1 (no silent dropouts).

**Phase plan position:** integrations plan P1 follow-up — close the real-shape residual for the merged `whatifd-datadog` adapter.

## Session end

**Artifacts produced:**
- `DEV/whatif/evaluator/observability.py` — added `tool_span()` CM emitting `LLMObs.tool` spans (not in repo).
- `DEV/whatif/evaluator/faithfulness.py` — `iter_tool_observations()` shared walk; `extract_tool_results` refactored onto it (text byte-identical) (not in repo).
- `DEV/whatif/harness/whatifd_run.py` — re-emits observed `[TOOL]`s as DD tool spans inside the cohort-score workflow (not in repo).
- `DEV/whatif/probes/probe_datadog.py` — structure-only Export-API probe (not in repo).
- `packages/whatifd-datadog/tests/test_conformance.py` — new `TestRealExportApiShape` (4 tests) pinning the probe-confirmed shape.
- `CHANGELOG.md` + cascade-catalog — recorded real-shape validation + the `ToolSpan.args` limitation.

**Findings (probe vs adapter):** `span_kind` ∈ {workflow:33, llm:94, tool:73}; root=`workflow`; `SearchedIO` `{value}` on tool spans, `{value,messages}` on llm; `tags` = `list[str]`; `tool_definitions` absent from tool-call spans. **Adapter required NO code changes** — the documented R-1 contract matched reality.

**Cascade catalog items:**
- Updated: "Datadog LLM Observability TraceSource adapter" — real-shape validation DONE; `ToolSpan.args` limitation documented; HTTP-level cassette + P1b sink still deferred.

**Gaps surfaced:** DD tool spans give `input` as a rendered string, not structured args → `ToolSpan.args` unpopulated → 108b-2 tool cache doesn't fill from DD (same as other adapters; tracer-`args` follow-up).

**Doctrine moments:** chose a real-shape conformance fixture (`TestRealExportApiShape`) over an HTTP cassette — validates the projection contract against confirmed reality without shipping scrubbed user content; the HTTP-level cassette stays optional.

**Notes for next session:** P1b (Datadog verdict sink) is next per the integrations plan; then P2/P2b (#93/#94) before the CI marketplace wrappers.
