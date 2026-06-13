# whatifd evidence map — `ReportV01` artifacts and EU AI Act high-risk obligations

> **Status:** DRAFT for ledger unit **H-13** · lane `DOCS` · **publication is HUMAN-gated**
> (legal-adjacent claims; see gap-bridge cardinal rules). Proposed repo location:
> `docs/compliance/eu-ai-act-evidence-map.md`.
>
> **Not legal advice.** This document maps whatifd's report fields to the
> *categories of evidence* the EU AI Act (Regulation (EU) 2024/1689) asks
> providers and deployers of high-risk AI systems to produce. It is an
> engineering crosswalk written by the project, not by counsel. Using whatifd
> does not make a system compliant, and whatifd makes no conformity claims —
> consistent with its own doctrine of non-claims. Have counsel review before
> relying on any row below.
>
> **Lineage:** written 2026-06-13 against `ReportV01` as documented in
> `docs/schema/v0.1.md` and `src/whatifd/report/models_v01.py` (repo `main`
> @ 47869c1, v0.3.0). Regulatory status as of the same date: the Digital
> Omnibus on AI reached provisional political agreement on 2026-05-07,
> deferring Annex III high-risk obligations from 2026-08-02 to **2027-12-02**
> (Annex I embedded systems to 2028-08-02), with formal adoption pending and
> preparation explicitly expected in the interim. Verify the current text and
> dates before citing this section.

---

## 1. The claim this document makes (and the one it doesn't)

**Made:** every `whatifd fork` run emits a versioned, schema-validated,
partially byte-deterministic JSON record (`ReportV01`) plus a human-readable
rendering, produced automatically as part of a pre-deployment change-control
workflow. Several Act obligations call for exactly this *shape* of evidence:
documented testing, predeclared acceptance criteria, automatically generated
records, disclosed methodology and limitations, and a monitoring loop that
feeds production behavior back into development.

**Not made:** that any field below *satisfies* an obligation. Obligations
attach to the AI system and its provider/deployer, span far more than
behavioral regression testing (data governance plans, QMS, registration,
conformity assessment, ...), and are judged in context. whatifd contributes
**evidence artifacts**, not conformity.

## 2. Why a behavior-change verdict tool maps unusually well

The Act's high-risk chapter repeatedly asks for things whatifd refuses to
fake: predeclared decision criteria (`decision_policy`, `trust_floor` are
fixed before the run and serialized into the report), honest uncertainty
(`verdict_state: "inconclusive"` is a first-class outcome with exit code 2,
not an error), and disclosed limitations (`methodology.causal_claim_scope` is
always `"associated_under_cached_tool_replay"` in v0.1 — the report itself
tells the reader what it cannot claim). Auditable honesty is the product;
that is the overlap.

## 3. Field-level crosswalk

Article references are at article level only; consult the consolidated text.
"Report path" names real `ReportV01` fields — if a field below ever drifts
from `docs/schema/v0.1.md`, that is a T1 finding for the gap-bridge loop.

### Art. 9 — Risk management system (testing against defined criteria)

| Obligation theme | Report path | What the artifact shows |
|---|---|---|
| Testing against pre-defined metrics and thresholds | `decision_policy.*`, `trust_floor.*` (both `x-deterministic: true`) | Acceptance criteria existed *before* results; identical across reruns of the same config. |
| Identification of risks from changes | `verdict_state` + `decision_findings[]` (severity ladder `info < warning < blocks_ship < blocks_all`) | A change's risks were evaluated and either blocked or accepted with rationale. |
| Residual-risk judgment | `verdict` + `failures[]` registry codes (e.g. `replay_validity_below_floor`, `min_scored_per_required_cohort`) | The system refused to render Ship when evidence was insufficient — the floor is a risk-control, with a `FloorPassedProof` witness required to construct `"ship"`. |

### Art. 10 — Data and data governance

| Obligation theme | Report path / mechanism | Shows |
|---|---|---|
| Relevance & representativeness of test data | `methodology.cohorts`, `cohort_results[]` (failure + baseline cohorts) | Evaluation used real production cases plus a representative baseline, both predeclared. |
| Personal-data minimization in tooling | `Sensitive[str]` wrapper on `ToolSpan.input/output`; Cardinal-#5 validator on `ToolSpan.attributes` | PII-bearing content is typed for redaction at render time; structurally enforced, not best-effort. |

### Art. 11 + Annex IV — Technical documentation

| Obligation theme | Report path | Shows |
|---|---|---|
| Description of validation/testing procedures, metrics, results | the entire `methodology` block: `unit_of_analysis`, `primary_metric`, `primary_endpoints`, `bootstrap.{method,resamples,seed,sample_unit,ci_level}`, `multiplicity.{correction,reason}`, `effect_size.*` | Method, parameters, and statistical procedure are inside the artifact, not in a wiki that drifts. |
| Known limitations | `methodology.bootstrap.unavailable_reason` (v0.1 truthfully shipped `method="unavailable"`), `per_trace_inference: "descriptive_only"`, `causal_claim_scope` | The artifact discloses its own shortcuts and scope limits — Annex IV's "limitations" ask, machine-readable. |
| Judge/measurement instrument description | `methodology.judge.*`: `scorer`, `scorer_version`, `judge_provider`, `judge_model`, prompt/rubric hashes, and the five reproducibility concepts (`reproducibility_addressed`, `reliability_measured`, `validity_measured`, `calibration_measured`, `bias_audit_measured`) | What measured the output, pinned by hash — and, today, an honest `false` on unmeasured concepts. (Gap unit H-05 proposes making judge calibration a floor input; when it lands, this row strengthens materially.) |

### Art. 12 — Record-keeping / automatic logging

| Obligation theme | Report path | Shows |
|---|---|---|
| Automatically generated, attributable records | `schema_version`, `schema_uri`, `runtime.config_hash` (sha256 of canonical config), `runtime.selection_seed`, `runtime.started_at/finished_at/duration_ms`, `runtime.environment.*` | Each evaluation event is a self-describing record tied to an exact configuration. |
| Integrity / reproducibility of records | `x-deterministic` field annotations + `extract_deterministic_subset_from_report` + the byte-equality integration test | A defined deterministic subset reproduces byte-identically — a stronger integrity property than most logs offer. (Gap unit H-13's signing half — sigstore attestation over the JSON — would add tamper-evidence.) |

### Art. 13 — Transparency to deployers

`methodology` + the rendered Markdown report (fix-suggestion templates are
mandatory for blocking findings, per the registry) give a deployer-readable
account of what was tested, what failed, and what to do — the report is
designed to be attached to a PR and read by a non-author.

### Art. 14 — Human oversight

whatifd's CI shape *is* an oversight design: exit codes (0/1/2) gate a merge,
but merging remains a human act, and `blocks_ship` findings arrive with
registered fix suggestions rather than silent failure. Document the
PR-gate-plus-human-merge workflow itself as the oversight measure; the report
is its paper trail.

### Art. 15 — Accuracy and robustness

| Obligation theme | Report path | Shows |
|---|---|---|
| Accuracy levels and consistency | `cohort_results[]` per-cohort summaries; `regression_check` experiment shape (known-good baseline vs candidate) | Behavioral consistency across versions measured on real traffic, both directions (rescue + regression). |
| Robustness of the evaluation itself | `failures[]` with stage/scope/retryable semantics; floor codes | The evaluation pipeline accounts for its own failure modes instead of silently dropping them. |

### Art. 17 — Quality management system

A QMS wants procedures, not heroics: the GitHub Action / GitLab component
wiring, the exit-code gate, `decision_policy` versioned in config, and the
report archive together evidence a *repeatable* change-control procedure for
model/prompt/tool changes.

### Art. 72 — Post-market monitoring (and Art. 26 deployer duties)

This is whatifd's most natural fit: the tool's input *is* production
behavior. Forking failed production traces into the next experiment
(`failure_rescue` shape) is a documented loop from post-market observation →
corrective change → evidence of the correction (`cohort_results` on the
failure cohort) → release decision. Retain reports alongside the monitoring
plan; the `whatifd-datadog` verdict-metrics emitter additionally lands the
verdict back in the monitoring system of record.

## 4. Honest gaps in the mapping (do not oversell)

- **Judge validity is disclosed, not established** — the five
  `*_measured` flags are typically `false` today. Disclosure ≠ validation
  (tracked as H-05).
- **Association, not causation** — `causal_claim_scope` says so; do not
  present verdicts as causal guarantees.
- **Sample sizes** — small cohorts will (correctly) yield Inconclusive;
  an evidence trail of Inconclusives demonstrates honesty, not coverage
  (H-06's power pre-check helps set expectations).
- **whatifd covers behavioral change-control only** — nothing here touches
  registration, conformity assessment, cybersecurity testing, or data-set
  governance beyond the evaluation data itself.

## 5. Suggested operating procedure (one paragraph for the QMS)

For every behavior-affecting change to a high-risk-classified LLM system:
run `whatifd fork` with a version-controlled config; archive the JSON +
Markdown reports (suggested retention: align with the Act's record-keeping
horizon, ≥ 6 months and per your sector rules); gate merge on exit code;
record the human merge decision; on production incidents, fork the implicated
traces into a `failure_rescue` experiment and archive the corrective-run
report next to the incident record.

---
*Maintainers: re-verify §lineage dates and the Omnibus adoption status before
publishing; route the published version through counsel (HUMAN gate, ledger
unit H-13).*
