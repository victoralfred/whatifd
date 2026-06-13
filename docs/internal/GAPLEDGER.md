<!-- SOURCE-LINEAGE
generated-by: whatifd-gap-bridge skill v1.0
generated-on: 2026-06-13
whatifd-sha: 47869c1d0653ebe9d95106ca9e5d263ff58ee5e0
whatifd-docs-sha: af9420a202537baf343dc85e6432466748c9e5bc
hypothesis-set: references/gap-hypotheses.md (dated 2026-06-13)
operator: <filled at PR #0 merge>
-->
# whatifd Gap Ledger

Phase-1 evidence sweep completed 2026-06-13 against `whatifd` v0.3.0
(`main` @ 47869c1) and `whatifd-docs` @ af9420a (clone succeeded with
maintainer credentials — H-20 is NOT blocked on auth; the repo remains
private to visitors, which is the H-20 brief's subject).

Negative control: `consistency_check.py --self-test --repo whatifd` →
**exit 0** (9/9 planted checks fired). Full scan
(`--repo whatifd --site-dir whatifd-docs --json findings.json`) →
**28 findings: 13 DRIFT / 14 WARN / 1 INFO**, all triaged below.
The site's 60-second demo was executed verbatim in a clean venv against
released PyPI packages → **Inconclusive, exit 2, as the page promises**
(transcript in GAP-029).

## Status summary

| state | count |
|---|---|
| PLANNED | 20 |
| PR_OPEN | 1 |
| DONE | 3 |
| AWAITING_HUMAN | 6 |
| REJECTED | 1 |
| IN_PROGRESS / BLOCKED / DEFERRED | 0 |

## Units — T1 (credibility)

### GAP-001 — whatif.codes status/version drift: site presents v0.2 as latest, v0.3 as "planned"
status: PLANNED
lane: DOCS
tier: T1-credibility
class: DRIFT
size: M
depends-on: none
evidence:
  - whatifd-docs docs/index.md:167 — "`whatifd` v0.2.0 is on PyPI"
  - whatifd-docs docs/index.md:174 — status table row: "v0.3 | planned | Cluster-paired bootstrap; LangSmith adapter; marketplace publication...; live-tool replay" — contradicts CHANGELOG `## [0.3.0] - 2026-06-04` (Datadog adapter, GitLab component, py.typed, --print-paths)
  - whatifd-docs docs/integrations/index.md:20-21 — RAGAS and Custom-plugin scorers marked "v0.3-planned"; v0.3 shipped without them
  - whatifd-docs docs/integrations/langfuse.md:98 — "Write scores back to Langfuse ❌ (planned for v0.3)" — v0.3 shipped without it
  - whatifd-docs docs/getting-started/index.md:3 — "v0.2.0 is on PyPI"; install line omits whatifd-datadog
  - whatifd-docs docs/getting-started/installation.md:15,23 — install lines omit whatifd-phoenix and whatifd-datadog
  - internal site contradiction: docs/integrations/index.md:11 says Datadog "shipped (v0.3)" while docs/index.md:174 says v0.3 is planned
  - `git -C whatifd tag` → v0.1.0 v0.2.0 v0.2.1 v0.3.0
acceptance:
  - site index Status table shows v0.3 as shipped (2026-06-04) with its actual contents per CHANGELOG [0.3.0]
  - unshipped v0.3-row promises (cluster bootstrap, LangSmith, live-tool replay) appear on a clearly-labeled roadmap row (v0.4/roadmap), cross-referenced to GAP-011 / GAP-017 promotions
  - all "v0.3-planned"/"planned for v0.3" labels on shipped-version rows relabeled truthfully (roadmap, no version ≤ 0.3)
  - site install lines name all five published packages (or explicitly scope which are needed per page)
  - `python consistency_check.py --repo whatifd --site-dir whatifd-docs --only release_table,stale_status_words` → 0 site-side findings
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-01; docs/index.md:167,174 vs git tags + CHANGELOG [0.3.0]
  - 2026-06-13 CONFIRMED→PLANNED — acceptance set; PR lands in whatifd-docs

### GAP-002 — README omits shipped whatifd-datadog from install line and calls it "in-development"
status: DONE
lane: DOCS
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - README.md:26 — `uv pip install whatifd whatifd-langfuse whatifd-inspect-ai whatifd-phoenix` (no whatifd-datadog)
  - README.md:28 — "includes the in-development whatifd-datadog adapter"
  - CHANGELOG.md `## [0.3.0] - 2026-06-04` — ships whatifd-datadog as fourth adapter
  - PyPI: `curl https://pypi.org/pypi/whatifd/json` → 0.3.0 long-description contains "in-development" (residue of this README; regenerates from README at next release — release act, human's)
acceptance:
  - README install line lists all five published packages
  - `grep -n "in-development" README.md` → no Datadog-adjacent hit
  - `python consistency_check.py --repo . --only adapter_inventory` → exit 0
pr: "#136"
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-02; README.md:26,28 vs packages/ + CHANGELOG 0.3.0
  - 2026-06-13 CONFIRMED→PLANNED
  - 2026-06-13 PLANNED→IN_PROGRESS→PR_OPEN — branch gap/002-readme-datadog off main; install line now names all 5 packages, "in-development" removed; AC verified (grep exit 1, adapter_inventory 0 findings exit 0); PR #136
  - 2026-06-13 PR_OPEN→DONE — PR #136 merged; re-verified on main: install line lists 5 packages, no "in-development", adapter_inventory exit 0

### GAP-003 — RELEASING.md package/adapter counts predate the fifth package
status: DONE
lane: DOCS
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - RELEASING.md:3 "builds all four distributions"; :36 "All four ... root + three adapter packages"; :83 "builds all four in sequence"; :89 "Bump ALL four packages ... root + three adapters"; :100 "root + all three adapters"; :101 "all four packages"; :122 "all three pyproject.toml files"
  - `ls packages/` → 4 adapters; +root = 5 packages; RELEASING.md:9 and :62 already correctly say "five"
  - RELEASING.md:109 "four publish jobs" — verify against `.github/workflows/release.yml` job count at execution
acceptance:
  - every count in RELEASING.md matches the tree (5 packages / 4 adapters), incl. :109 verified against release.yml
  - `python consistency_check.py --repo . --only numeric_claims` → exit 0
  - `uv run pytest tests/unit/whatifd/test_version_parity.py` passes and covers all five packages
pr: "#137"
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-03; RELEASING.md:3,36,83,89,100,101,122
  - 2026-06-13 CONFIRMED→PLANNED
  - 2026-06-13 PLANNED→IN_PROGRESS→PR_OPEN — branch gap/003-releasing-counts off main; fixed counts at :3,:36,:83,:89,:100,:101,:103,:109,:122 + added datadog to :102 install line; :109 verified against release.yml (5 publish-* jobs); left :20 (OIDC claims) and :115 (4 github actions) unchanged; AC verified (numeric_claims 0 findings exit 0; test_version_parity 7 passed covering all five); PR #137
  - 2026-06-13 PR_OPEN→DONE — PR #137 merged; re-verified on main: numeric_claims exit 0

### GAP-004 — SECURITY.md supported-versions table frozen at pre-v0.1
status: PR_OPEN
lane: DOCS
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - SECURITY.md:5 — "This project is pre-alpha. Security fixes will be issued for the most recent minor release once v0.1 ships." — v0.3.0 shipped 2026-06-04
  - SECURITY.md:10 — "| 0.1.x | :white_check_mark: (planned) |" with no rows for 0.2.x/0.3.x
acceptance:
  - table reflects the policy already stated in the file (most recent minor = 0.3.x supported), no "(planned)" on released versions, no "pre-alpha"/"once v0.1 ships" wording
  - `python consistency_check.py --repo . --only stale_status_words` → no SECURITY.md finding
  - note: the *policy itself* ("most recent minor only") is unchanged — changing the policy would be a HUMAN decision; this unit only makes the table match the existing policy sentence
pr: "#138"
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — new unit (seed appendix); SECURITY.md:5,10 vs git tag v0.3.0
  - 2026-06-13 CONFIRMED→PLANNED
  - 2026-06-13 PLANNED→IN_PROGRESS→PR_OPEN — branch gap/004-security-versions off main; table → 0.3.x supported / <0.3 not, intro de-staled, policy unchanged; AC verified (no SECURITY.md finding in stale_status_words; no pre-alpha/planned/once-v0.1 residue); PR #138

### GAP-005 — "six rendered walkthroughs" claims vs seven files in docs/walkthroughs/
status: PLANNED
lane: DOCS
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - `ls docs/walkthroughs/*.md` → 01..07 + README = 7 scenarios
  - README.md:124 — "six rendered scenarios"
  - docs/schema/v0.1.md:176 — "six rendered scenarios" (rule-6 note: docs/schema/ is doctrine-guarded; this is a prose count, not schema semantics — doctrine.md read 2026-06-13; no schema content touched)
  - docs/getting-started.md:252 "the six committed walkthroughs"; :258 "six rendered examples"
  - docs/walkthroughs/README.md:118 — "The six `.md` files are the canonical rendered output"
  - NOT drift: site docs/index.md:172 v0.1 row "six rendered walkthrough reports" — historically accurate for v0.1; docs/getting-started.md:21,30 "six inputs" — unrelated
acceptance:
  - `grep -rn "six rendered\|six committed\|six \`.md\`" README.md docs/getting-started.md docs/schema/v0.1.md docs/walkthroughs/README.md` → no hits (replaced by "seven" or count-free phrasing)
  - `ls docs/walkthroughs/0*.md | wc -l` output cited in PR body matches the new wording
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-21; README.md:124 et al. vs 7 files
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-006 — docs/concepts.md dead relative link to path-z.md
status: PLANNED
lane: DOCS
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - docs/concepts.md:124 — "[path-z.md](path-z.md) (Phase 10)" — no docs/path-z.md in tree
  - the page exists on the site: whatifd-docs docs/concepts/path-z.md (renders at whatif.codes)
acceptance:
  - the link resolves: either points to the live site page URL or a committed file; "(Phase 10)" label re-checked against phases.md
  - `python consistency_check.py --repo . --only internal_links` → no concepts.md finding
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — new unit (seed appendix); docs/concepts.md:124; file absent, site page present
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-007 — 13 dead `manifest.json` relative links in walkthroughs + design-skill references
status: PLANNED
lane: META
tier: T1-credibility
class: HYGIENE
size: M
depends-on: none
evidence:
  - checker `internal_links`: docs/walkthroughs/{01,02,03,04,05,07}-*.md (6 links), .claude/skills/whatifd-design/references/walkthroughs.md:49,83,161,212,289 (5), cascade-catalog.md:586 (1) — e.g. docs/walkthroughs/01-clean-ship.md:19 "[Manifest →](manifest.json)"
  - no manifest.json committed anywhere under docs/walkthroughs/ (`find docs -name manifest.json` → empty)
  - triage at execution: walkthroughs are "canonical rendered output" (docs/walkthroughs/README.md:5) — decide commit-the-manifests vs remove/relabel links; 06-rerun-after-fix.md has no such link, suggesting the links are vestigial
acceptance:
  - `python consistency_check.py --repo . --only internal_links` → no manifest.json findings
  - decision (commit vs remove) recorded in the PR body with rationale
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — new unit (seed appendix); 13 checker hits, no target files in tree
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-008 — AGENT_TELEMENTRY.md filename misspelling
status: PLANNED
lane: META
tier: T1-credibility
class: HYGIENE
size: S
depends-on: none
evidence:
  - `ls *.md` → AGENT_TELEMENTRY.md (TELEMENTRY ≠ TELEMETRY)
acceptance:
  - `git mv AGENT_TELEMENTRY.md AGENT_TELEMETRY.md`; all inbound references updated (`grep -rn "TELEMENTRY" . --exclude-dir=.git` → 0 hits)
  - `python consistency_check.py --repo . --only filename_hygiene` → exit 0
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-18; ls output
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-009 — stray CLAUDE.md.append.md duplicates CLAUDE.md telemetry section
status: PLANNED
lane: META
tier: T1-credibility
class: HYGIENE
size: S
depends-on: none
evidence:
  - CLAUDE.md.append.md exists at repo root; its content ("## Session telemetry (whatifd-design skill)...") already appears verbatim inside CLAUDE.md
acceptance:
  - confirm byte-level duplication (diff against the corresponding CLAUDE.md section); if duplicate, remove the stray file; if it diverges, reconcile into CLAUDE.md first
  - `ls CLAUDE.md.append.md` → no such file
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — new unit (Phase-1 sweep); file present at root, content duplicated in CLAUDE.md
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-010 — stale "(v0.3)" label on sequential testing in statistical-defaults.md
status: PLANNED
lane: DOCS
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - .claude/skills/whatifd-design/references/statistical-defaults.md:143 — "sequential testing (v0.3) and active selection..." — v0.3.0 shipped 2026-06-04 without sequential testing
  - cardinal-9 note: this edits a version *label* in a skill reference, not the active plan (phases.md); pure reconciliation
acceptance:
  - the line no longer names a version ≤ released (relabel to a future version or "roadmap")
  - `python consistency_check.py --repo . --only stale_status_words` → no statistical-defaults.md finding
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — seed appendix (H-04-adjacent); statistical-defaults.md:143 vs git tag v0.3.0
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-011 — cluster-paired bootstrap promised publicly, absent from tree (promotion)
status: PLANNED
lane: CODE
tier: T1-credibility
class: FEATURE
size: M
depends-on: none
evidence:
  - whatifd-docs docs/index.md:174 — named on the public v0.3 row
  - `grep -ri cluster src/whatifd/statistical/` → only forward-compat naming in bootstrap.py docstring ("distinguishes paired_percentile_bootstrap from cluster_paired_percentile_bootstrap"); no implementation
  - statistical relevance: multi-turn traces from one session violate the paired bootstrap's independence assumption (statistical-defaults.md); whatif-features deferred-refactors.md §5 "Cluster-key scenarios in Phase 9A integration" is adjacent but narrower
  - doctrine-guarded (cardinal rule 6): src/whatifd/statistical/ — promotion only, never CODE-EXEC
acceptance:
  - amendment PR to whatifd-design/references/phases.md adding the unit with acceptance criteria: cluster resampling implementation, `MethodologyDisclosure.bootstrap.method` value `cluster_paired_percentile_bootstrap`, a walkthrough exercising it, cascade-catalog entry
  - GAP-001's roadmap row cross-references this unit
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-04; grep transcript + site v0.3 row
  - 2026-06-13 CONFIRMED→PLANNED — promotion artifact, not implementation

### GAP-012 — judge-calibration gate absent (disclosure exists, mechanism doesn't) (promotion)
status: PLANNED
lane: CODE
tier: T1-credibility
class: FEATURE
size: M
depends-on: none
evidence:
  - hypothesis H-05 as seeded was PARTIALLY STALE: the schema DOES carry calibration fields — src/whatifd/report/schema/v0.2.schema.json:622 `calibration_measured`, :426 `calibrated_from_judge_noise_floor`; docs/schema/v0.1.md:84 "five reproducibility concepts"
  - what is genuinely absent: any *gate* — no judge-vs-human agreement measurement, no floor/policy term consuming `calibration_measured`; docs/concepts.md:23 "Not a judge-quality validator ... the user's calibration concern"
  - doctrine-guarded (cardinal rule 6): decision/, report/, docs/schema/ — promotion only; cascade-catalog entry required
acceptance:
  - amendment PR to phases.md (or whatif-features entry with trigger) for a minimal calibration gate: agreement-on-N-labels recorded in MethodologyDisclosure, policy option refusing Ship when uncalibrated; explicitly preserves the non-claim wording until shipped
  - evidence in the promotion cites the existing disclosure fields (no duplicate fields invented)
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-05 rescoped; schema fields exist (v0.2.schema.json:426,622), gate absent
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-013 — pre-run power/MDE disclosure absent (post-run observed-MDE exists) (promotion)
status: PLANNED
lane: CODE
tier: T1-credibility
class: FEATURE
size: S
depends-on: none
evidence:
  - hypothesis H-06 as seeded was PARTIALLY STALE: src/whatifd/statistical/__init__.py:4 — "Holm correction + observed-MDE power warnings" already shipped (post-run)
  - genuinely absent: a *pre-run* "detectable effect at N" disclosure (no pre-run power computation in src/whatifd/statistical/ or config.py — grep transcript in Phase 1)
acceptance:
  - amendment PR to phases.md (or whatif-features entry) for pre-run MDE disclosure at cohort selection time, building on the shipped observed-MDE machinery
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-06 rescoped; statistical/__init__.py:4 (observed-MDE shipped) vs no pre-run check
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-014 — no K-replay / flake-stability handling on replay (promotion)
status: PLANNED
lane: CODE
tier: T1-credibility
class: FEATURE
size: M
depends-on: none
evidence:
  - `grep -rin "repeat|n_replays|replay_count|flake" src/whatifd/replay/` → only tool_cache.py:337 (unrelated: repeated cache key)
  - whatif-features deferred-refactors.md entries 1–10 — no K-replay/stability entry exists
acceptance:
  - whatif-features entry (or phases.md amendment) with trigger: K-replays per trace, variance reporting, stability term consideration for the floor — doctrine-guarded if it touches decision/
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-07; grep transcript + deferred catalog inspection
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-030 — test_slots_rejects_arbitrary_attrs over-strict on Python 3.13 (red CI on release HEAD)
status: DONE
lane: META
tier: T1-credibility
class: HYGIENE
size: S
depends-on: none
evidence:
  - tests/unit/whatifd/adapters/test_protocols.py:239-241 — `pytest.raises((TypeError, AttributeError))` then `assert excinfo.type in (TypeError, AttributeError)` (exact-class match)
  - CI run 27453089668 job test (py3.13): "FAILED ... test_slots_rejects_arbitrary_attrs - assert <class 'dataclasses.FrozenInstanceError'> in (<class 'TypeError'>, <class 'AttributeError'>)"; the raised exc is FrozenInstanceError("cannot assign to field 'mystery'")
  - `python3 -c` transcript: FrozenInstanceError MRO = [FrozenInstanceError, AttributeError, Exception, ...]; issubclass(FrozenInstanceError, AttributeError) → True; `in (TypeError, AttributeError)` → False — so pytest.raises catches it but the sub-assertion rejects it
  - NOT caused by PR #0: `git diff --stat origin/main...gap/000-ledger` → only .md files; main's ci run 26979347027 had test (py3.13) = success at 47869c1 on 2026-06-04. Failure surfaced 2026-06-13 from a Python 3.13 patch bump that reordered the frozen-vs-slots __setattr__ check (frozen now fires first → FrozenInstanceError)
  - the test comment (:227-237) anticipated only 3.14 TypeError and "older" AttributeError; it did not anticipate 3.13's FrozenInstanceError
acceptance:
  - the sub-assertion accepts FrozenInstanceError without weakening the "fail loudly on a genuinely new exception class" intent — preferred fix: `assert issubclass(excinfo.type, (TypeError, AttributeError))` (isinstance semantics; a non-subclass SlotsViolationError still fails loudly); alt: add `dataclasses.FrozenInstanceError` to both tuples
  - `test (py3.13)` passes in CI; 3.11/3.12/3.14 stay green
  - lane note: META (test-portability/CI hygiene, no product behavior change) — direct-fixable in Phase 3 on its own branch `gap/030-py313-frozen-slots`; NOT folded into PR #0 (ledger-only) per the one-unit-one-branch rule
pr: "#135"
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — Phase-2 discovery via PR #0 CI; run 27453089668 + reproduction transcript; isolated as pre-existing (main was green at same SHA)
  - 2026-06-13 CONFIRMED→PLANNED — first eligible META unit for Phase 3; fix proposed, not applied (held at human gate)
  - 2026-06-13 PLANNED→IN_PROGRESS→PR_OPEN — human fast-tracked; branch gap/030-py313-frozen-slots off fresh main, `assert excinfo.type in (...)` → `assert issubclass(excinfo.type, (...))`; verified `pytest tests/unit/whatifd/adapters/test_protocols.py` 20 passed on both 3.13.13 and 3.14.0; PR #135
  - 2026-06-13 PR_OPEN→DONE — PR #135 merged (MERGED 2026-06-13T02:12:47Z); re-verified on main: test_slots_rejects_arbitrary_attrs passes under py3.13.13 (1 passed)

### GAP-031 — SECURITY/CONTRIBUTING/copilot docs cite nonexistent src/whatifd/{ingest,score} paths
status: PLANNED
lane: META
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - SECURITY.md:46 — "Official adapters shipped under `src/whatifd/ingest/`"; :47 — "default scorer wrappers in `src/whatifd/score/`"
  - CONTRIBUTING.md:103 ("src/whatifd/score/", "src/whatifd/diff/"), :111 ("Adding a tracer adapter (`src/whatifd/ingest/`)"), :129 ("Adding a scorer (`src/whatifd/score/`)")
  - .github/copilot-instructions.md:65,76 — same `src/whatifd/{ingest,score,diff}/` references
  - `ls src/whatifd/` → adapters/ (factory.py, protocols.py, stub.py, pii.py), scorer_loader.py, diff.py (a FILE), contract/; NO ingest/ or score/ dirs; external adapters live in packages/whatifd-*/
  - discovered 2026-06-13 during GAP-004 (SECURITY.md edit); a contributor following these docs hits nonexistent module paths
acceptance:
  - every `src/whatifd/ingest/` and `src/whatifd/score/` reference in SECURITY.md, CONTRIBUTING.md, .github/copilot-instructions.md updated to the real layout (in-repo: src/whatifd/adapters/, scorer_loader.py; external: packages/whatifd-*/) or removed; `src/whatifd/diff/` → diff.py where it implies a dir
  - `grep -rn "src/whatifd/ingest\|src/whatifd/score" --include="*.md" . | grep -v docs/sessions` → 0 hits
  - reconciliation toward the tree (truth hierarchy); if any path names a *planned* future module, label it roadmap rather than asserting it ships
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — discovered during GAP-004; ls src/whatifd/ vs SECURITY.md:46-47 / CONTRIBUTING.md:103,111,129 / copilot-instructions.md:65,76
  - 2026-06-13 CONFIRMED→PLANNED

## Units — T2 (reach)

### GAP-015 — runner contract is Python-only; `exec:` stdio lane (promotion; spec drafted)
status: PLANNED
lane: CODE
tier: T2-reach
class: FEATURE
size: M
depends-on: none
evidence:
  - src/whatifd/runner_loader.py:74-116 — only `python:<module.path>:<attr>`; :99 "v0.1 supports `python:<module.path>:<attr>` only"
  - draft spec exists: docs/internal/drafts/runner-contract-exec-spec.md (filed in PR #0; written 2026-06-13 against main @ 47869c1; proposed final location docs/runner-contract-exec.md)
  - doctrine-guarded boundary (runner contract): promotion = spec PR first, implementation second; cascade-catalog entry required
acceptance:
  - promotion PR: move the spec to docs/runner-contract-exec.md marked DRAFT/proposal, paired phases.md amendment + cascade-catalog entry
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-09; runner_loader.py:99
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-016 — OTel GenAI SemConv source adapter missing (promotion)
status: PLANNED
lane: CODE
tier: T2-reach
class: FEATURE
size: M
depends-on: none
evidence:
  - `ls packages/` → no whatifd-otel*; site integrations/index.md correctly lists "OpenTelemetry GenAI | planned" (no drift component)
acceptance:
  - phases.md amendment (or whatif-features entry) scoped explicitly: read-only TraceSource from OTLP/JSON export, not a tracer
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-10; packages/ listing
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-017 — LangSmith adapter publicly promised on v0.3 row, unshipped (promotion)
status: PLANNED
lane: CODE
tier: T2-reach
class: FEATURE
size: M
depends-on: none
evidence:
  - whatifd-docs docs/index.md:174 — LangSmith named on the v0.3 row; `ls packages/` → absent
  - integrations/index.md says "LangSmith | planned" — correct phrasing; the drift component (index v0.3 row) is GAP-001's
acceptance:
  - phases.md amendment (or whatif-features entry with trigger) for whatifd-langsmith TraceSource adapter; GAP-001's roadmap row cross-references it
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-11; packages/ listing + site rows
  - 2026-06-13 CONFIRMED→PLANNED

## Units — T3 (demand & distribution)

### GAP-018 — cost/latency as first-class endpoints (promotion)
status: PLANNED
lane: CODE
tier: T3-demand
class: FEATURE
size: M
depends-on: none
evidence:
  - src/whatifd/decision/guards/primary_endpoint.py:20 — extension point named ("latency-reduction ... by extending the `EndpointDirection` Literal") but unimplemented; no cost/latency metric support in config.py (grep transcript)
acceptance:
  - whatif-features entry (or phases.md amendment): cost/latency metrics for regression_check; doctrine-guarded (decision/) — promotion only
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-12; primary_endpoint.py:20 + grep transcript
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-019 — EU AI Act evidence-map doc (draft filed; publication HUMAN-gated)
status: PLANNED
lane: DOCS
tier: T3-demand
class: POSITIONING
size: M
depends-on: none
evidence:
  - draft exists: docs/internal/drafts/eu-ai-act-evidence-map.md (filed in PR #0; proposed final location docs/compliance/eu-ai-act-evidence-map.md; carries "Not legal advice" framing)
  - nothing compliance-shaped exists in docs/ today (grep transcript)
acceptance:
  - move draft to docs/compliance/eu-ai-act-evidence-map.md preserving the non-claims framing; PUBLICATION/linking from public surfaces requires the human sign-off recorded in this unit (legal-adjacent — brief to be attached to the PR)
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-13 (docs half); draft filed
  - 2026-06-13 CONFIRMED→PLANNED — human review required before any public linking

### GAP-020 — verdict provenance / report signing (promotion)
status: PLANNED
lane: CODE
tier: T3-demand
class: FEATURE
size: M
depends-on: none
evidence:
  - `grep -rin "sigstore|signing|attest" src/ docs/` → nothing relevant (one false hit in types/sensitive.py)
acceptance:
  - whatif-features entry with trigger (e.g. first compliance-driven user request): sigstore-attested ReportV01
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-13 (code half); grep transcript
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-021 — GitHub Marketplace publication of whatifd-fork action
status: AWAITING_HUMAN
lane: HUMAN
tier: T3-demand
class: FEATURE
size: S
depends-on: none
evidence:
  - docs/internal/marketplace-publish-runbook.md exists (owner-only steps)
  - `gh repo view victoralfred/whatifd-action` → PUBLIC but EMPTY (no contents, no tags); sync workflow inert (ACTION_SYNC_TOKEN unprovisioned per runbook)
  - operator input 2026-06-13: the repo is empty because Marketplace listing requirements are not yet met — support offering details, terms, privacy policy, etc.
brief: The publication pipeline is staged but parked, deliberately. `victoralfred/whatifd-action` exists (public, empty); `.github/workflows/sync-action.yml` will populate it on the next `v*.*.*` tag once `ACTION_SYNC_TOKEN` is provisioned; the runbook documents the remaining owner-only steps. Per the maintainer, the actual blocker is the Marketplace listing prerequisites: a support offering statement, terms, privacy policy, and the Marketplace Developer Agreement. Recommended path: (1) decide whether to publish at all this cycle; (2) if yes, draft the support/terms/privacy texts (the agent can draft these as DOCS follow-ups on request — they are publication artifacts, so they stay human-gated); (3) provision the token and let the next release tag populate the repo; (4) execute the runbook's listing steps. Nothing here blocks releases meanwhile. No agent action until you decide.
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-14; runbook + empty public repo + operator input
  - 2026-06-13 CONFIRMED→AWAITING_HUMAN — publication is a release act (cardinal rule 3)

### GAP-022 — no public live-demo repo with whatifd verdicts on PRs
status: AWAITING_HUMAN
lane: HUMAN
tier: T3-demand
class: POSITIONING
size: M
depends-on: none
evidence:
  - `gh search repos --owner victoralfred` → no live-demo repo; `langfuse_inspectai_whatifd_integration` exists (public integration sample) but is not a PR-verdict showcase
brief: The strongest marketing artifact for a CI-verdict tool is a public repo where every PR visibly carries a whatifd verdict comment. Creating a repo under your account and wiring the Action is your act, not the agent's. If approved, the agent can scaffold the contents (minimal agent + config + whatifd-fork workflow) as a follow-up unit you then publish. Decision needed: create it this cycle? Suggested name and seed content can be drafted on request. The existing langfuse_inspectai_whatifd_integration repo could alternatively be upgraded to carry PR verdicts.
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-15; repo search transcript
  - 2026-06-13 CONFIRMED→AWAITING_HUMAN

### GAP-023 — promote Show-HN draft to its repo location
status: PLANNED
lane: DOCS
tier: T3-demand
class: POSITIONING
size: S
depends-on: GAP-001, GAP-002
evidence:
  - draft exists: docs/internal/drafts/show-hn-draft.md (filed in PR #0; proposed final location docs/internal/show-hn-draft.md)
  - the draft's own pre-flight: H-01/H-02 drift must be DONE before posting; demo verified working (GAP-029 transcript)
acceptance:
  - draft moved to docs/internal/show-hn-draft.md after GAP-001 and GAP-002 are DONE; posting remains GAP-024 (human)
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-16 (drafts half); draft filed
  - 2026-06-13 CONFIRMED→PLANNED

### GAP-024 — distribution publishing decisions (Show HN, ecosystem listings, posts)
status: AWAITING_HUMAN
lane: HUMAN
tier: T3-demand
class: POSITIONING
size: S
depends-on: GAP-001, GAP-002, GAP-023
evidence:
  - show-hn draft filed (GAP-023); no whatifd listing on Langfuse/Phoenix integrations pages (unverified externally — listing requests are outbound acts anyway)
brief: Four motions, all requiring your name/accounts: (1) Show HN — draft is ready; pre-flight requires GAP-001/GAP-002 merged first (HN will click the site within minutes; a "v0.3 planned" table under a v0.3.0 release is the first comment you'd get). The 60-second demo verified working today (exit 2, Inconclusive, as advertised). (2) The "we replaced our own bootstrap shortcut and disclosed it" post — agent can draft on request. (3) Ecosystem listing requests to Langfuse/Phoenix integrations pages. (4) Community posts. Decide which to greenlight; drafts are DOCS units, sending is yours.
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-16 (publishing half)
  - 2026-06-13 CONFIRMED→AWAITING_HUMAN

### GAP-025 — Datadog positioning surface (employment-conflict)
status: AWAITING_HUMAN
lane: HUMAN
tier: T3-demand
class: POSITIONING
size: S
depends-on: none
evidence:
  - packages/whatifd-datadog shipped in v0.3.0 (CHANGELOG [0.3.0]); maintainer is a Datadog employee; Datadog sells an adjacent LLM Obs Experiments product (gap-hypotheses.md H-17)
brief: whatifd now ships a Datadog LLM Observability read-adapter plus a CI-side verdict-metrics emitter — an "open loop" story around a platform you work for, which also sells an adjacent Experiments product. What the integration may claim: read-only trace ingestion via documented public APIs; metrics emission a customer configures themselves. What it must not claim (without clearance): comparisons with or positioning against Datadog Experiments, "better/cheaper than Datadog" framing, use of any non-public knowledge, or implied endorsement. Recommendation: before ANY marketing use of the Datadog integration (blog, HN text, README positioning beyond factual adapter listing), pre-clear with your employer's IP/conflict-of-interest policy (moonlighting/OSS policy + manager or legal as your policy requires). Until cleared, all public text stays at the factual level already in CHANGELOG/README ("a Datadog LLM Observability trace-source adapter exists"). The agent will never act on this surface (cardinal rule 10).
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-17; shipped adapter + employment context
  - 2026-06-13 CONFIRMED→AWAITING_HUMAN — mandatory brief, PR #0 top

### GAP-026 — "whatif" vs "whatifd" naming; repo description ratification
status: AWAITING_HUMAN
lane: META
tier: T3-demand
class: HYGIENE
size: S
depends-on: none
evidence:
  - `gh repo view victoralfred/whatifd` description — opens "whatif is an open experiment runner... whatif forks production traces..." (bare "whatif" ×2)
  - checker name_consistency: bare "whatif" ×2 (cascade-catalog.md:1450,1524) vs "whatifd" ×1122 in repo prose
  - site getting-started/index.md:3 — "the brand stays `whatifd`; the bare PyPI slot was taken"
brief: Usage is 1122:2 in favor of "whatifd" in-repo, and the site itself declares "the brand stays whatifd". Proposal: canonical name is **whatifd** everywhere; fix the GitHub repo description (also fixes its typo'd double-space and aligns with the README one-liner), and the two cascade-catalog stragglers. Ratify (or override) the canonical form; on ratification this unit becomes an S-size META execution (description edit via `gh repo edit` is yours or the agent's per your call — it is public-facing metadata).
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-19; gh repo view output + name_consistency counts
  - 2026-06-13 CONFIRMED→AWAITING_HUMAN — naming ratification is the human's

### GAP-027 — private whatifd-docs vs public "Edit this page" affordance
status: AWAITING_HUMAN
lane: HUMAN
tier: T3-demand
class: HYGIENE
size: S
depends-on: none
evidence:
  - `gh repo clone victoralfred/whatifd-docs` succeeded with maintainer credentials; repo visibility is private (visitors clicking the Furo "Edit this page" links hit 404/login)
  - consistency-surface.md S6 documents the paradox
brief: Every whatif.codes visitor who clicks "Edit this page" hits a wall because the source repo is private. Two clean fixes: (a) make whatifd-docs public — maximizes contribution surface, requires a quick secrets/history scan first; or (b) keep it private and strip/disable the edit links in the Furo conf.py — zero risk, slightly less inviting. Either resolves the broken affordance; (a) is recommended if the history is clean. Decision is repo-visibility = yours. On decision, the follow-up is an S-size unit in whatifd-docs.
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-20; private visibility + rendered edit links
  - 2026-06-13 CONFIRMED→AWAITING_HUMAN

### GAP-028 — nightly CI guard running the site's 60-second demo
status: PLANNED
lane: META
tier: T3-demand
class: HYGIENE
size: M
depends-on: none
evidence:
  - demo executed verbatim 2026-06-13 in a clean venv against PyPI 0.3.0 → Inconclusive, exit 2, exactly as whatifd-docs docs/index.md:80-84 promises (transcript in GAP-029)
  - no workflow currently runs the published-package demo (`ls .github/workflows/` at execution to confirm)
acceptance:
  - a scheduled workflow installs released PyPI packages in a clean env, runs the demo files verbatim, asserts exit code 2 and report artifacts exist
  - workflow passes on its first scheduled/dispatched run (link in PR body)
pr:
log:
  - 2026-06-13 HYPOTHESIS→CONFIRMED — H-08 bridge; demo transcript + no existing guard
  - 2026-06-13 CONFIRMED→PLANNED

## Rejected hypotheses

### GAP-029 — H-08 as drift: "the 60-second demo has bit-rotted"
status: REJECTED
lane: META
tier: T1-credibility
class: DRIFT
size: S
depends-on: none
evidence:
  - executed verbatim from whatifd-docs docs/index.md:36-80 in a clean venv: `uv venv` + `uv pip install whatifd whatifd-langfuse whatifd-inspect-ai` (resolved 0.3.0) → `PYTHONPATH=. whatifd fork --config whatifd.config.yaml` → "report written to reports/whatifd-fork-2026-06-13.md (+ .json)"; `EXIT=2`; rendered verdict "Inconclusive" — exactly the promised outcome
log:
  - 2026-06-13 HYPOTHESIS→REJECTED — demo runs as advertised; preventive guard spun off as GAP-028

Also recorded as corrected-premise (not separate rejected units): H-05's "no calibration field in schema" — false, fields exist (rescoped into GAP-012); H-06's "no power check" — observed-MDE warnings shipped (rescoped into GAP-013). Pre-rejected hypotheses in gap-hypotheses.md ("softer Inconclusive", "build a UI", "docs match DESIGN.md aspirations") remain rejected; no new evidence.

## Iteration log

- 2026-06-13 Phase 0–2: preflight (self-test exit 0), evidence sweep (28 checker findings triaged; demo executed; both repos at recorded SHAs), ledger written; PR #0 opened. Board: 22 PLANNED / 6 AWAITING_HUMAN / 1 REJECTED.
- 2026-06-13 Phase-2 amend: PR #0 CI surfaced a pre-existing Python-3.13 test failure (test_slots_rejects_arbitrary_attrs); isolated as not caused by the docs-only PR; recorded as GAP-030 (META, T1). Board: 23 PLANNED / 6 AWAITING_HUMAN / 1 REJECTED.
- 2026-06-13 GAP-030 fast-tracked at human request: PLANNED→PR_OPEN (#135) on branch gap/030-py313-frozen-slots (issubclass fix; 20 passed on 3.13.13 + 3.14.0). Board: 22 PLANNED / 1 PR_OPEN / 6 AWAITING_HUMAN / 1 REJECTED.
- 2026-06-13 iter 1: PR #134 + #135 merged (Gate A); GAP-030 PR_OPEN→DONE (reconciled, re-verified on main); GAP-002 PLANNED→PR_OPEN (#136). Board: 21 PLANNED / 1 PR_OPEN / 1 DONE / 6 AWAITING_HUMAN / 1 REJECTED.
- 2026-06-13 iter 2: PR #136 merged; GAP-002 PR_OPEN→DONE (reconciled, re-verified on main); GAP-003 PLANNED→PR_OPEN (#137). Board: 20 PLANNED / 1 PR_OPEN / 2 DONE / 6 AWAITING_HUMAN / 1 REJECTED.
- 2026-06-13 iter 3: PR #137 merged; GAP-003 PR_OPEN→DONE (reconciled, re-verified on main); GAP-004 PLANNED→PR_OPEN (#138); discovered + recorded GAP-031 (dead src/whatifd/{ingest,score} doc paths). Board: 20 PLANNED / 1 PR_OPEN / 3 DONE / 6 AWAITING_HUMAN / 1 REJECTED (31 units).

## Closeout report

(Phase 4 only.)
