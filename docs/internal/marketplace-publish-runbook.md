# GitHub Marketplace publication runbook (`whatifd-fork` action)

Integrations-plan **P3**. The composite action lives in this monorepo at
`.github/actions/whatifd-fork/`, but GitHub Marketplace requires an action's
`action.yml` at the **root of its own repository**. So publication uses a
dedicated public repo, kept in sync by `.github/workflows/sync-action.yml`.

This runbook lists the **owner-only** steps (creating repos, accepting the
Marketplace agreement, publishing the listing, and provisioning the sync
token). The sync workflow is already in the monorepo but **inert** until the
token secret exists — so nothing here blocks normal releases.

---

## One-time setup

### 1. Create the public action repo
- Create `github.com/victoralfred/whatifd-action` (public, empty — no README).
- It will be populated entirely by the sync workflow; do not hand-edit it.

### 2. Create a cross-repo sync token
The sync workflow needs write access to `whatifd-action` from inside a
`whatifd` workflow run. Two options:
- **Fine-grained PAT (simplest):** create a PAT scoped to **only**
  `victoralfred/whatifd-action` with **Contents: read & write**. Store it in
  the **whatifd** repo as the secret **`ACTION_SYNC_TOKEN`**
  (Settings → Secrets and variables → Actions → New repository secret).
- **GitHub App (tighter, optional):** install an app on `whatifd-action` with
  Contents:write and mint a token in the workflow. Heavier; the PAT is fine to
  start.

> Until `ACTION_SYNC_TOKEN` exists, `sync-action.yml` no-ops with a `::notice`.
> The `${{ github.token }}` default canNOT push cross-repo — that's why a
> dedicated token is required.

### 3. Seed the action repo
- Either push one release tag (`git tag v0.2.2 && git push origin v0.2.2`,
  matching the pyproject versions — the release tag↔version guard applies) and
  let `sync-action.yml` populate `whatifd-action`,
- or run the workflow manually: **Actions → "sync whatifd-action" →
  Run workflow → ref = `v0.2.2`**.
- Confirm `whatifd-action` now has `action.yml` + `README.md` at root and tags
  `v0.2.2` + `v0` (the moving major tag consumers pin).

### 4. Accept the Marketplace Developer Agreement & publish
- In `whatifd-action`, open the latest release (the sync tags it; you may need
  to **create a GitHub Release** from the `v0.2.2` tag — Marketplace publishes
  from a Release, not a bare tag).
- On the release page, check **"Publish this Action to the GitHub
  Marketplace"**, accept the **Marketplace Developer Agreement** (one-time,
  legal), pick the primary + secondary categories (e.g. *Continuous
  Integration* / *Code quality*), and publish.
- The `branding:` block (`icon: shield`, `color: blue`) is already in
  `action.yml`, which Marketplace requires — no extra step.

---

## Ongoing (after setup)

- **Every release tag** (`v*.*.*`) automatically triggers `sync-action.yml`,
  which copies the current `action.yml` + README into `whatifd-action`, tags
  the exact version, and moves the major tag. You then **publish a new
  Marketplace release** from that tag (GitHub does not auto-publish; it's a
  per-release checkbox).
- **Consumers** reference `uses: victoralfred/whatifd-action@v0` (major pin) or
  a SHA for hardened setups. The synced README already documents the published
  `uses:` form (the sync `sed`-rewrites the monorepo's local-path example).

## What the sync workflow does NOT do
- It does not create the repo, accept the agreement, or publish the listing —
  those are the steps above.
- It does not push if there are no changes (idempotent re-runs are safe).
- It is guarded: no `ACTION_SYNC_TOKEN` → no-op, so it can't break releases
  before P3 is provisioned.

## Verifying it works
- After step 3, `whatifd-action` root has `action.yml` + `README.md`; tags
  `v0.2.2` and `v0` resolve.
- A throwaway consumer workflow using `uses: victoralfred/whatifd-action@v0`
  runs the action end-to-end (needs `whatifd` installed + adapter creds, same
  as the monorepo's `example-whatifd-fork.yml.example`).
- The Marketplace listing page renders the README and the `shield`/`blue`
  branding.
