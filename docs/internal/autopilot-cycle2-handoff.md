# Autopilot cycle-2 — handoff & blocked-feature design briefs

> Written by the whatifd-gap-bridge autopilot loop (`docs/internal/AUTOPILOT.md`).
> Summarizes what the unattended loop delivered on the integration branch
> `auto/hardening-cycle2` and — honestly — what it **deliberately did not
> implement** because it needs a human design or release decision. The loop's
> contract forbids faking progress; for novel doctrine-guarded statistics, a
> plausible-but-unverified implementation would undermine the one thing whatifd
> sells (a *defensible* verdict), so those are briefed here instead of guessed.

## Delivered (merged into the integration branch, each behind green CI + a passing doctrine review)

- **`exec:` runner lane (`whatifd-exec/1`) — complete.** Non-Python agents
  satisfy the runner contract over NDJSON stdio. Spec (`docs/runner-contract-exec.md`),
  `whatifd.exec_runner.ExecRunner` (handshake → per-trace replay with in-core
  tool-cache callbacks → shutdown), the `exec:<argv>` loader scheme, deterministic
  fork-pipeline teardown, the `whatifd exec-check` conformance harness, a
  zero-dependency Node reference runner (`examples/exec_agent_node/`), and an
  end-to-end pipeline test. The single largest TAM unlock in the backlog.
- **`whatifd report-migrate --indent`** (#79) — human-readable migrator output
  by default, with `whatifd.serialization.indented_json_bytes`.
- **Issue sweep** — #93 and #94 closed (already shipped in v0.3.0); no open issues remain.
- **Docs reconciliation** — README/getting-started/runner-contract now cover the
  exec lane + `exec-check`; corrected stale "the `whatifd fork` CLI is a stub"
  claims (it has been fully wired since v0.3.0).

The whole cycle keeps `consistency_check.py --repo .` = 0 and `--self-test` = 0.

## Blocked — needs a human design decision (NOT implemented)

These are real "potential features" from the deferred catalog. They are **doctrine-guarded
statistical/decision work** (cardinal #10: statistical claims must match the design; a
subtle error is a *correctness* bug, not a cosmetic one) or **release-coordinated package
work** (cardinal #3: the agent never versions/tags/releases). The loop is authorized for
full autonomy but is holding the line on correctness: each needs a decision only you can make.

### S1. Pre-run power / minimum-detectable-effect disclosure (deferred §13)
**Why blocked:** the "observed-MDE power warnings" the design notes referenced are **not
actually implemented** (a prior misread — confirmed: no MDE/power code exists in
`src/whatifd/statistical/`). So this is *novel* statistical methodology, not an extension.
**Decision needed:** the MDE definition for a paired-percentile bootstrap — what power, what
effect-size metric, computed how at cohort-selection time — and exactly what `MethodologyDisclosure`
field carries it. Once the definition is pinned, implementation + a regression test asserting
the disclosure matches the runtime computation is straightforward.

### S2. Cluster-paired bootstrap (deferred §4/§5/§11)
**Why blocked:** multi-turn traces from one session violate the i.i.d. paired-bootstrap
assumption; `cluster_paired_percentile_bootstrap` is named in `bootstrap.py` as forward-compat
but the resampling math isn't written. The math (resample whole clusters) and its disclosure
are doctrine-load-bearing. **Decision needed:** confirm the cluster-resampling design (and that
`MethodologyDisclosure.bootstrap.method` flips only when the real method runs — cardinal #10).

### S3. Judge-vs-human calibration gate (deferred §12)
**Why blocked:** the schema already carries `calibration_measured`/`calibrated_from_judge_noise_floor`
disclosure fields, but there is no mechanism to measure judge-vs-human agreement and no floor/policy
term that consumes it. Converting the project's biggest non-claim ("not a judge-quality validator")
into a gate is a doctrine decision. **Decision needed:** the agreement metric, the N-label protocol,
and whether the floor refuses `Ship` when uncalibrated (and the default).

### S4. Cost / latency as first-class endpoints (deferred §18)
**Why partially blocked:** the bootstrap machinery would be reused (not novel), but *endpoint
discipline comes first* (doctrine): a cost/latency endpoint is still a predeclared cohort-level
endpoint with its own direction and threshold semantics. **Decision needed:** the endpoint
definitions (is lower-cost an "improvement"? thresholds? how it composes with the quality verdict).
The mechanical extension to `EndpointDirection` + config is then tractable.

### S5. K-replay flake-stability (deferred §14)
**Why blocked:** the descriptive half (replay each trace K times, report variance) is implementable
and verifiable; the load-bearing half — a *stability term in the trust floor* — is doctrine-guarded.
**Decision needed:** whether/how replay variance affects the floor (and the K default + cost trade-off).

### S6. New source adapters: OTel GenAI (§16), LangSmith (§17)
**Why blocked:** each is a new *published package* (`whatifd-otel` / `whatifd-langsmith`). Adding a
6th/7th workspace package ripples into `release.yml` publish jobs, `test_version_parity`, the
"five packages" counts across README/RELEASING/site, and — critically — **versioning + a PyPI
release**, which the agent never does (cardinal #3). **Decision needed:** approve the new package(s)
+ own the release coordination; the agent can then scaffold the in-repo adapter + conformance tests.

### S7. Verdict provenance / `ReportV01` signing (deferred §19)
**Why blocked:** a distinct subsystem (sigstore attestation, key management, trust roots) with
its own design surface; pairs with the EU-AI-Act evidence map. **Decision needed:** the signing
approach + trust model.

## Optional remaining (low-risk, agent-doable on request)
Deferred-catalog hygiene §1 (promote conformance harness), §2 (PEP 440 validator on
`AdapterMetadata.package_version`), §6 (CI determinism diff gate), §10 (machine-checkable
json-dumps allowlist); the exec-lane walkthrough fixture #8 (byte-equal determinism). Say the
word and the loop will take any of these.

## Recommendation
Merge `auto/hardening-cycle2` → `main` (it is a green, self-contained increment — the exec lane
plus polish). Then make the S1–S7 calls above; the loop can resume and implement each once its
design/release decision is settled.
