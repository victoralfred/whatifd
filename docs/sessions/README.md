# Session telemetry

This directory holds the agent's self-reported session logs.

Each significant work session produces a Markdown file named
`<YYYY-MM-DD>-<topic-slug>.md`. The agent is instructed in `CLAUDE.md`
to log session-start and session-end information following a structured
template.

## What goes here

- **`<YYYY-MM-DD>-<topic>.md`** — per-session telemetry (Layer 2). Committed.
- **`dashboard-<YYYY-MM-DD>.md`** — periodic dashboards (Layer 4). Committed.
- **`raw/`** — raw Claude Code transcript JSONL files (Layer 1). Optionally `.gitignore`-d.

## What does NOT go here

- Production traces, customer data, or any artifact containing user content.
  Per skill cardinal rule #5, sensitive data is wrapped, never raw.

## How to use

```bash
# Layer 1: collect transcripts after a session
./scripts/collect-transcripts.sh

# Layer 2: the agent writes session telemetry automatically
#         (see CLAUDE.md telemetry block)

# Layer 3: run benchmark prompts (weekly)
./scripts/run-skill-benchmark.sh
./scripts/grade-skill-benchmark.sh tests/skill-benchmarks/results/<latest>

# Layer 4: aggregate dashboard (weekly or after meaningful changes)
./scripts/skill-dashboard.sh > docs/sessions/dashboard-$(date +%Y-%m-%d).md
```

## Reading the data

The session telemetry is structured Markdown, designed for both human reading
and grep-based analysis. Some useful queries:

```bash
# Which references actually get read across all sessions?
grep -h "references/" *.md | grep -v dashboard | sort | uniq -c | sort -rn

# Which cardinal rules get cited?
grep -hE "Rule #[0-9]+" *.md | grep -v dashboard | sort | uniq -c | sort -rn

# Which sessions opened cascade catalog items?
grep -l "Opened:" *.md | grep -v dashboard

# Which sessions resolved cascade catalog items?
grep -l "Resolved:" *.md | grep -v dashboard
```

## When the data is stale

If sessions stop appearing here even though work is happening, the agent
has stopped following the telemetry protocol. Common causes:

- The `CLAUDE.md` telemetry block was removed or modified.
- The agent decided the session was "trivial" and skipped the log.
  (Check `CLAUDE.md` for the trivial-session exception clause.)
- The session was conducted outside Claude Code (e.g., via API or another
  client that doesn't auto-load CLAUDE.md).

If sessions exist but are sparse on detail, the template wasn't followed.
This is itself diagnostic: it means the protocol is too long or unclear.
Iterate on the CLAUDE.md telemetry block.
