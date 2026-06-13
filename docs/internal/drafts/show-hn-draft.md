# Show HN draft — whatifd

> **Status:** DRAFT for ledger unit **H-16** · lane `DOCS` (draft) →
> **publication is HUMAN-gated** (it's your name and account on the post).
> Proposed repo location: `docs/internal/show-hn-draft.md`.
> Pre-flight before posting: H-01/H-02 docs drift must be DONE (HN *will*
> click the site and the README within minutes; a "planned v0.3" table under
> a v0.3.0 release is the first comment you'll get), and the 60-second demo
> must run verbatim from a clean venv (H-08).

---

## Title (pick one; all ≤ 80 chars, no superlatives — HN strips/punishes them)

1. `Show HN: Whatifd – replay production LLM traces against a change, get a verdict`
2. `Show HN: Whatifd – a regression gate for LLM behavior changes (Ship/Don't Ship)`
3. `Show HN: Whatifd – fork prod traces, replay your prompt change, score the diff`

Recommendation: **#1** — "replay production traces" is the hook; "verdict" is
the differentiator. URL: `https://whatif.codes/` (the docs site converts
better than the bare repo; the repo is one click away).

## Body

---

Hi HN — I built whatifd because every time I changed a prompt or swapped a
model, "did this actually make things better?" was answered with vibes and
three cherry-picked examples.

Every step of the workflow already has a tool — Langfuse/Phoenix for traces,
Inspect AI for scoring, GitHub for PRs. The *experiment* doesn't. whatifd is
that missing piece: it forks production traces (the failures that motivated
your fix, plus a representative baseline), replays them through your agent
with the proposed change while serving the original tool outputs from cache
(so side effects don't re-fire), scores the diff, and emits a JSON + Markdown
verdict you attach to the PR: Ship, Don't Ship, or Inconclusive, with exit
codes so CI can gate on it.

The part I care most about: **it refuses to give you a verdict it can't
defend.** If the sample is too small, replay validity is below the floor, or
the cache is corrupt, you get Inconclusive (exit 2) with the reason — not a
confident number. Every report embeds its own methodology disclosure: the
bootstrap method and seed, what the judge was, what *wasn't* measured
(judge calibration, validity), and the exact causal scope it can claim. In
v0.1 we shipped the statistics with `method: "unavailable"` because the
implementation was an empirical-percentile shortcut — the report said so
truthfully until v0.2 replaced it with a real paired-percentile bootstrap.
That honesty-first design is the whole product.

Try it in ~60 seconds, fully offline (stub adapters, no keys, no traces):

    uv pip install whatifd whatifd-langfuse whatifd-inspect-ai
    # 3 small files + one command — full snippet on the site
    whatifd fork --config whatifd.config.yaml
    cat reports/whatifd-fork-*.md

You'll get an Inconclusive verdict on purpose — the stub source is empty, and
the trust floor won't render Ship/Don't Ship without data. Point
`source.adapter` at Langfuse, Arize Phoenix, or Datadog LLM Observability and
the same pipeline runs on your real traces; your agent plugs in behind a
small runner contract (a Python callable today; a language-agnostic
JSON-over-stdio lane is specced next).

What it's deliberately not: not a tracer, not an eval framework (it wraps
Inspect AI), not a dashboard, not an agent runtime. It composes the tools you
already have into an experiment with a defensible result.

Honest status: alpha, v0.3.0, Apache-2.0, solo maintainer, ~zero users —
which is exactly why I'm posting. The design doctrine (trust floor, witness
tokens, byte-deterministic report subset) is documented in the repo and is
the part I'd most like challenged. Known gaps I'm working on: cluster-paired
bootstrap for multi-turn traces, judge-calibration as a floor input, and a
pre-run power check so Inconclusive is predictable instead of disappointing.

Repo: https://github.com/victoralfred/whatifd
Docs: https://whatif.codes/

What would make you trust — or refuse to trust — an automated Ship/Don't-Ship
verdict on an LLM change? That's the question the whole design hangs on.

---

## Prepared first comment (post within ~5 min; HN rewards author presence)

> A design choice worth flagging since it's the one people push back on:
> small cohorts (the default is 20 failures + 20 baseline) very often produce
> Inconclusive. That's intentional — a tool that always prints a delta on
> n=20 is lying about its confidence interval — but I'm adding a pre-run
> power check ("at N=20 you can detect effects ≥ X") so the outcome is
> predictable before you spend the tokens. Curious whether people would
> rather have honest Inconclusives or a number with a giant CI attached.

## Launch ops (for the human)

- Post Tue–Thu, 14:00–16:00 UTC; stay in-thread for the first 3–4 hours.
- Expected hard questions + the honest line: *"Braintrust/LangSmith/Datadog
  already do trace→test→CI"* → yes, inside their platforms; whatifd is the
  neutral, OSS, exit-code-gated layer that composes any tracer/scorer and
  refuses unverifiable verdicts. *"LLM judge = garbage in"* → agreed; judge
  identity is hash-pinned and calibration is disclosed-as-unmeasured today,
  floor-gated calibration is the active gap (H-05). *"Solo project risk"* →
  true; Apache-2.0, schema is versioned with a stability contract, reports
  are plain JSON — the exit cost is low by design.
- Do not link the AI-Act evidence map from the post (compliance framing
  draws a different, worse crowd on HN); keep it for the site.
- Datadog-adjacent questions: stick to "there's a read-only adapter," no
  positioning commentary (cardinal rule 10 — that brief is yours, not the
  thread's).
