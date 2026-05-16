---
session_id: 2026-05-16-production-hardening-review-decisions
started_at: 2026-05-16
type: review-decision-record
pinned_to:
  project: f89c218
  whatifd-docs: b5169e6
---

# Production-Hardening Review — Decision Record

Companion to `2026-05-16-production-hardening-review-findings.md`. Captures the **judgment calls** made during the review — severity-rubric applications, scope decisions, doctrinal interpretations, and remediation-direction choices. The findings file logs *what* was found; this file logs *why* it was classified the way it was, so a future reviewer can re-derive the verdicts without re-deliberating.

Authority order (per `[[whatif_design_decisions]]` memory): decision record > skill > code. Decisions made here override later code-level intuition; if a reviewer disagrees with a severity here, they edit this file with a paired rationale, they do not silently re-grade the finding.

---

## D1 — Scope discipline: pipelines 1–5 only

**Decision.** Phase 2 traces only the five named pipelines (CLI fork, adapter projection, cache lock lifecycle, programmatic API, schema→consumer). Other potential pipelines (`whatifd diff`, `report-migrate`, `cache rebuild/unlock/verify`) get scoped delta-mentions in their owning component's Phase-3 verdict but no standalone pipeline trace.

**Rationale.** The skill's prioritization clause permits explicit scope cuts. The five named pipelines cover every cardinal-rule enforcement boundary (#1/#2/#5/#9/#10) and every external trust boundary (config ingress, runner code, adapter SDKs, filesystem writes, schema URL). Adding pipelines beyond these would mostly produce findings already surfaced in pipelines 1–5.

---

## D2 — (N) / (C) / (G) finding-tag definitions

**Decision.** Every finding row carries one of three tags:

- **(N) Novel** — finding not present in the cascade catalog Open or Resolved entries as of pinned SHA.
- **(C) Confirms cascade entry** — finding restates a known catalog entry. Must cross-reference the entry's header text in the evidence column.
- **(G) Gap** — catalog has no related entry; this finding *should* file a new catalog entry as part of Phase 3 remediation.

**Rationale.** Without this discipline, the review would double-report known-deferred work (cascade-catalog has 96 entries spanning Open / Deferred / Resolved). Distinguishing (N)/(C)/(G) tells the user which findings *are new information* vs. which *re-surface known risk*.

**Operational rule.** If unsure between (N) and (C), default to (C) and force the cross-reference. Lazy (N) classification erodes the review's utility.

---

## D3 — Severity rubric applied to whatifd specifically

The skill's severity rubric is generic; whatifd-specific applications:

- **P0 (critical).** Examples: graph-walk redaction bypass → PII leak in artifact; floor-bypass path → `Ship` with structural failure; cache corruption that survives `verify`; CLI accepting config that disables the two-affirmation forensic gate.
- **P1 (high).** Examples: dynamic-import `eval`/`exec` adjacent paths in user code load (cardinal-#1 boundary leak); timeout-and-leak patterns that don't release process resources; missing input validation on report-migrate JSON; schema-URL drift between repo and docs.
- **P2 (medium).** Examples: O(n²) on a path with a 1000-trace ceiling that's enforced elsewhere; missing structured-logging at a single trust boundary; rotating-log gap; unparameterized retry interval.
- **P3 (low).** Hygiene; missing typed-error specializations; over-broad except clauses that don't lose information; magic numbers without named constants.
- **Info.** Observation worth recording; not a defect (e.g., "this is a documented v0.3 deferral").

**Operational rule.** A finding's severity is **immutable once the row is written**. Disagreement is resolved by adding a new row that supersedes (and cross-references) the old one — never by editing the old row in-place. This preserves audit trail.

---

## D4 — How the skill's "no soften findings" rule is operationalized

**Decision.** Pushback during this review is met with **evidence**, not severity downgrade. If the user disagrees with a P0/P1 finding, the response is one of:

1. Cite the actual code path that contradicts the finding (which may then be a withdrawn finding, not a downgraded one — withdrawn rows are struck through with rationale).
2. Provide a documented exception (e.g., a cascade-catalog entry that explicitly accepts the gap; the finding then becomes (C)).
3. Accept the finding as-is and proceed to remediation.

A withdrawn finding is *not* the same as a downgraded one. A withdrawn finding is wrong; a downgraded finding is right-but-graded-differently. The rubric (D3) forbids downgrading without a paired rationale citing why the failure mode is less severe than the original reading.

---

## D5 — Adapter SDK opacity: external-boundary scope

**Decision.** Findings against Langfuse SDK / Inspect AI SDK / arize-phoenix-client internals are **out of scope**. Only the **whatifd wrapping boundary** at the adapter ingress is in scope: does whatifd correctly wrap external content as `Sensitive[str]`, does it handle SDK exceptions, does it respect cardinal-#5 at the projection step.

**Rationale.** The skill explicitly scopes the review to whatifd. External SDKs have their own maintainers and review processes; reviewing them here would dilute focus and produce findings the project can't act on.

---

## D6 — Decision file format and append discipline

**Decision.** Every entry in this file:

- Has a unique ID (`D<N>`) used as a stable reference from findings.
- Has a one-line **Decision** statement.
- Has a **Rationale** explaining *why this choice over alternatives*.
- Optionally has an **Operational rule** translating the decision into reviewer behavior.

Append-only during a review pass. If a later decision supersedes an earlier one, the earlier entry is *not* deleted — a "**Superseded by D<N>**" line is added at the top of the original entry and the new entry includes "**Supersedes D<M>**" at the top.

**Rationale.** A decision record that gets edited in-place is a worse audit artifact than a chronological one. Future reviewers reconstructing the review's reasoning need both the conclusion *and* the alternatives that were rejected.

---

*Subsequent decisions added below as Phase 2 traces produce judgment calls.*

---

## D7 — F-1.1 (phoenix unwired in factory) graded P1, not P2

**Decision.** Finding 1.1 — `whatifd-phoenix` package ships and docs claim "shipped (v0.2)" but `adapters/factory.py:build_trace_source` has no `'phoenix'` branch — is graded **P1 (high)**, not P2.

**Rationale.** The skill's P1 definition: "Likely exploitable or likely to fail under reasonable conditions. Requires fix before next release." The concrete failure mode: an operator follows the published Phoenix integration docs, sets `source.adapter: phoenix` in their YAML, runs `whatifd fork`, and gets `AdapterFactoryError: Unknown trace-source adapter 'phoenix'. v0.1 supports 'stub' and 'langfuse'.` This is a **contract break** between the documented public surface and the runtime — adopters trust the docs as the contract. Not a hypothetical edge case; first-touch friction for any Phoenix-curious adopter, and the audit doc (`requirements.txt` at workspace root) already flagged adopter friction as the project's weakest dimension.

**Operational rule.** Docs-vs-code contract drift for a documented v0.X-shipped feature graded P0/P1 depending on visibility (P0 if a security boundary; P1 if a functional one).

---

## D8 — F-1.3 (filesystem writes outside try/except) graded P1, not P2

**Decision.** Finding 1.3 — `cli.py:485-490` runs three filesystem operations (`mkdir`, `write_bytes`, `write_text`) outside any try/except — is graded **P1 (high)**, not P2.

**Rationale.** The dispatcher's own docstring at `cli.py:226-240` lists cardinal-#1 alignment as the first bullet ("every adapter / loader / pipeline exception is caught and converted to a setup-failure stderr + exit 2. No stack traces leak."). The filesystem-write path violates this promise on three common conditions: read-only disk (CI), permission denied (containerized write to `./reports/`), and disk full. Each surfaces as a raw `OSError` past the CLI exit point — an adopter sees a Python stack trace where they expect "setup failure: cannot write report to ./reports/...; check filesystem permissions". Cardinal #1 is non-negotiable per CLAUDE.md; a known load-bearing claim with a broken enforcement path is P1.

**Operational rule.** A cardinal-rule promise violated on a foreseeable failure path is at minimum P1. Speculative/exotic paths (e.g., `mkdir` racing with another process) can be P2-Info.

---

## D9 — F-1.6 (judge_provider methodology field) graded P1, not P2

**Decision.** Finding 1.6 — `MethodologyDisclosure.judge.judge_provider` set to `cfg.scorer.adapter` ("stub" / "inspect_ai") instead of the actual judge provider — is graded **P1 (high)**, not P2.

**Rationale.** Cardinal #10 is one of the cardinal rules (`CLAUDE.md` lines 36-42): "Statistical claims must match the design... Methodology is disclosed in every report." The `MethodologyDisclosure.judge.judge_provider` field is by name a provider claim — consumers reading the report's JSON or rendered Markdown WILL interpret `"judge_provider": "inspect_ai"` as "the LLM judge was named inspect_ai", which is structurally wrong (Inspect AI is the evaluation framework, not a model provider). A consumer who cites the methodology in a downstream document compounds the error. Per cardinal #10's "no causal claims beyond 'associated under cached-tool replay'" discipline, a misleading provider claim is more severe than a missing one. The TODO at lines 359-362 acknowledges the gap; the cascade entry tracks the resolution. P1 because the failure mode is "deployed report misleads consumers."

**Operational rule.** Cardinal-#10 disclosure fields with misleading values are at minimum P1; fields with placeholder values that consumers can detect (like the `"v01-cli-placeholder-no-scorecase"` sentinel in F-1.7) are P2.

---

## D10 — F-1.18 (asyncio.run per trace) tagged (C), severity per cascade

**Decision.** Finding 1.18 — async-runner per-trace event-loop creation — is tagged **(C)** and graded **P2** (medium) following the cascade entry "Phase 11: shared asyncio loop for async-runner trace stream"'s implicit acceptance.

**Rationale.** The code at `cli_pipeline.py:135-144` documents the limitation, names the cascade entry, and explains the v0.1 acceptability (I/O-bound workload, fork concurrency bounded by `run_pipeline`). The finding confirms a known-deferred risk; tagging (C) prevents double-reporting. Severity matches the project's own acceptance posture.

**Operational rule.** When a cascade entry already accepts a risk with explicit rationale, the finding's severity follows the catalog's implied bar — usually P2 (medium, scheduled). Bumping above the catalog's bar requires a paired rationale citing new information.

---

## D11 — Append-only modification discipline ("note changes for future deliberation")

**Decision.** Any change to a finding after it has been approved by the user (withdrawal, severity adjustment, tag reclassification, evidence correction) MUST be recorded as an entry in the **Changes log** section of `2026-05-16-production-hardening-review-findings.md`, never as an in-place edit.

**Rationale.** User instruction confirming the discipline rule already implicit in D6 (decision-file append-only) and D3 (severity immutability). The Changes log surfaces:

- What was modified (the affected finding ID, e.g., F-1.6)
- When (turn date)
- Who instigated (user pushback / new evidence / reviewer self-correction)
- Why (the rationale; cite cascade entry or code path that surfaces new information)
- What the change was (old severity/tag → new severity/tag, OR the withdrawal text)

A reviewer reading the findings file weeks later can reconstruct the deliberation trail without needing to diff git history. This is the audit-trail half of the trust-first frame applied to the review itself — the review's own defensibility comes from showing the work.

**Operational rule.** When the user approves a finding and later asks for a change, the workflow is:

1. **Do not edit the finding row.** It stays as the original audit record.
2. **Add a Changes-log entry** with the structure above.
3. **If the modification is structural** (a withdrawn finding stops counting toward the Phase-3 verdict; a severity change affects component classification), add a paired decision entry (D<N>) explaining the doctrinal basis.
4. **In Phase 3**, derive verdicts from `(original finding row) ⊕ (Changes-log entries that supersede it)` — the final classification reflects the deliberation, not just the first read.

This rule applies retroactively: if Pipeline 1's 18 findings need modification at any point, all changes route through the log. The findings file's row-by-row state is the audit record; the changes log is the deliberation record.

---

## D12 — Pipeline 1 findings approved by user (2026-05-16)

**Decision.** All 18 findings from Pipeline 1 are user-approved as recorded. Subsequent modifications follow D11.

**Rationale.** User confirmation message "approved" after the Pipeline 1 summary. No reclassifications requested. The three P1 findings (F-1.1, F-1.3, F-1.6) are now load-bearing inputs to Phase 3's per-component verdicts.

**Operational rule.** Phase 2 continues to Pipeline 2 (adapter projection). Pipeline 1's findings are immutable except via the D11 Changes log.

---

## D13 — F-2.1 verified against full codebase; defect confirmed in both shipped scorer adapters

**Decision.** User requested codebase verification of F-2.1 (Inspect AI cache key omits output content). Verification grep across all `score_case_hash =` assignments:

- `packages/whatifd-inspect-ai/src/whatifd_inspect_ai/scorer.py:164` — `score_case_hash=_hash16("case", case.trace_id, case.cohort)`
- `src/whatifd/adapters/stub.py:215` — `score_case_hash=_hash16("case", case.trace_id, case.cohort)`

Both shipped scorer implementations use the same pattern. **Neither** includes `case.original_output.text` or `case.replayed_output.text` in the cache key components. `CacheKeyComponents` (`src/whatifd/cache/keying/v1.py:107-142`) has 12 fields; none capture the output content. F-2.1 is doctrinally consistent across the codebase (not an Inspect-AI-specific bug; the stub has the same defect). The cache key represents "score case identity" as `(trace_id, cohort)` — but a single ScoreCase carries `(input, original_output, replayed_output)` content that the scorer reads to compute its judgment. Two cases with identical `(trace_id, cohort)` but different `replayed_output` content produce the same cache key.

**Rationale.** P1 grading from D7 stands. The defect is shared across both adapters because they implement the same documented pattern; the pattern itself is structurally wrong. The fix (when undertaken) should land at the `CacheKeyComponents` shape (add an `output_hash` field) so all scorer adapters acquire the protection at once — fixing only one adapter leaves the structural class open.

**Operational rule.** A finding that surfaces as identical patterns across multiple adapter implementations is a **structural defect**, not an adapter bug. Remediation should target the shared boundary (`CacheKeyComponents` schema + `score_case_hash` semantics in `CacheKeyComponents.__post_init__`), not per-adapter patches.

---

## D14 — F-2.2 (Phoenix `tool_spans` projection) fixed in-session; design choice "strip content, not wrap"

**Decision.** F-2.2 (Phoenix child-span content lost) confirmed in code, then fixed in this review session. Design choice: strip content + PII keys at the projection boundary rather than wrapping content as `Sensitive[T]` inside `tool_spans` dicts.

**Rationale.** Two paths considered:

**Path A — Wrap content as Sensitive[T] inside tool_spans dicts.**
- Pro: surfaces content with cardinal-#5 type-level protection equivalent to user_message/original_response.
- Con: `RawTrace.tool_spans` is typed `list[dict[str, Any]]`. The `RawTrace.metadata` model_validator does NOT recurse into `tool_spans`. The graph_walk at serialization time DOES recurse into dicts/lists and raises `UnredactedSensitiveError` on ANY `Sensitive[T]` reachable from the report tree — regardless of whether it's "wrapped" or "leaked". Result: a wrapped `Sensitive[str]` inside `tool_spans` would crash serialization.
- Requires typed-`ToolSpan` model (issue #108) to land first, which requires runner-contract coordination across three packages.

**Path B (chosen) — Strip content + PII keys at projection.**
- Pro: surfaces tool-span structure (kind, parent_id, tool.name, model.name, timing) immediately. Preserves cardinal #5 by not surfacing content at all — no Sensitive[T] reaches tool_spans. Doesn't require #108 to land first.
- Con: loses tool-span CONTENT from the report. A reviewer can see "this trace fired a tool call to `search`" but not "the search query was X" or "the search returned Y".
- Upgrade path: when #108 lands typed `ToolSpan` with proper Sensitive[T] support, `_project_tool_span` upgrades from strip-content to wrap-content; the partial fix's call site (`tool_spans=[_project_tool_span(s) for s in spans if s is not root]`) stays unchanged.

**Why Path B over Path A:** the verdict-defensibility frame asks "would a reviewer be misled?" — a tool-span surface with structure-but-no-content is honest (you can see what fired); a tool-span surface with leaked content is misleading (cardinal #5 violation). Cardinal #5 is non-negotiable; cardinal-#8 (Inconclusive must be actionable) is satisfied because tool-span structure IS actionable (operators can see which tools fired without needing the content). The trade-off is acceptable because issue #108 tracks the proper resolution.

**Operational rule.** When fixing an enforcement-boundary gap, prefer **structural strip** over **enforcement-extension** unless the enforcement extension is part of the same PR's scope. Strip is reversible (a later PR re-adds content with proper wrapping); enforcement-extension changes the type-system contract and requires broader coordination.

---

## D15 — Phoenix fix tests added; no existing tests regressed

**Decision.** F-2.2 fix ships with 6 new tests in `packages/whatifd-phoenix/tests/test_conformance.py::TestToolSpansProjection`. Full test suite green at 1316 passing (+6 from 1310 pre-fix baseline). No existing test relied on `tool_spans == []` so no negative-test removal was needed.

**Rationale.** The 6 tests pin the projection's load-bearing properties: (1) non-root spans present, (2) root excluded, (3) content keys stripped, (4) PII keys stripped, (5) structural keys preserved, (6) empty list when no children. A future refactor that touches `_project_tool_span` must keep all six green or surface the change deliberately.

**Operational rule.** In-review fixes for P1/P2 findings ship with tests that pin the load-bearing properties of the fix, not just "doesn't break". The test bar is the same as for any other landed change in the codebase.
