---
session_id: 2026-06-04-readme-refresh
started_at: 2026-06-04T17:10:00Z
---

## Session start

**User request:** Update README.md — it has outdated info; remove stale/unuseful sections like "Status".

**Skill files read:** none beyond carried context (docs-only copy-edit, below the architecture threshold).

**Cardinal rules cited:** none — no behavior/schema/verdict change.

**Phase plan position:** housekeeping; not a roadmap phase.

## Session end

**Artifacts produced:**
- `README.md` — removed the Status badge + the entire "## Status" section (internal phase-jargon + a stale version-roadmap table). De-jargoned the Quickstart headings ("works today"/"stub adapters work today") and dropped scattered "(Phase B)" refs. Install: noted each adapter is optional + the in-development `whatifd-datadog` (NOT yet on PyPI — kept out of the pip-install line, available from source). "How it composes": dropped version tags, added Datadog LLM Observability, and reflected the shipped CI integrations (GitHub Action + GitLab component). Fixed the self-contradictory Contributing section ("Pre-alpha… PRs deferred until v0.1 ships" → "Alpha; PRs welcome; read the doctrine").

**Cascade catalog items:** none (docs-only).

**Gaps surfaced:** the CLI-quickstart config references `python:examples.minimal_agent.replay:run` while the dir is `examples/minimal-agent/` (module vs dir naming) — pre-existing, out of scope for this refresh; the quickstart uses stub adapters so the runner ref is illustrative.

**Doctrine moments:** kept `whatifd-datadog` OUT of the PyPI `uv pip install` line because it isn't published yet (would 404) — accuracy over completeness; listed it as available from source instead.

**Notes for next session:** P5 (Travis) is the last integrations item, offered and awaiting the owner's go.
