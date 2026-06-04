# whatifd for GitLab CI/CD

A GitLab **CI/CD Catalog component** that runs `whatifd fork` in a pipeline,
gates on the verdict, uploads the report artifacts, and posts the verdict as a
merge-request note — the GitLab analog of the `whatifd-fork` GitHub action.

Canonical source: `integrations/gitlab/templates/whatifd-fork.yml` in the
whatifd monorepo. **Publication** lives in a dedicated GitLab project (a
catalog resource) — see "Publishing" below; that part is owner-only (this repo
can't create GitLab projects).

## Usage (consumer `.gitlab-ci.yml`)

```yaml
include:
  - component: $CI_SERVER_FQDN/<group>/whatifd-gitlab/whatifd-fork@1
    inputs:
      config: whatifd.config.yaml
      pip-install: "whatifd whatifd-langfuse"   # + the adapter you use

# Provide adapter credentials + (optionally) GITLAB_TOKEN as masked CI vars.
```

### Inputs

| Input | Default | Purpose |
|---|---|---|
| `stage` | `test` | Pipeline stage to run in. |
| `image` | `python:3.12-slim` | Image (Python 3.11+). |
| `config` | `whatifd.config.yaml` | whatifd config path. |
| `pip-install` | `whatifd` | Space-separated install spec; add your adapter, e.g. `whatifd whatifd-datadog[live]`. |
| `fail-on-dont-ship` | `true` | Fail the job on Don't-Ship/Inconclusive (exit 1/2). |
| `comment-on-mr` | `true` | Post the verdict as an MR note (MR pipelines only). |

### Behavior

- Runs `whatifd fork --config <config> --print-paths`; the exit code
  (0=ship / 1=dont_ship / 2=inconclusive) is the gate.
- Uploads `reports/` as a job artifact (`when: always`).
- On MR pipelines, posts/updates a merge-request note, deduped by the
  `<!-- whatifd-fork -->` HTML marker (the same scheme as the GitHub action),
  found via the GitLab Notes API. One rolling note per MR — locale- and
  author-independent.

### Tokens (MR note)

Posting a note needs a token with notes scope:
- **`CI_JOB_TOKEN`** (built-in) is used by default and works on many GitLab
  setups.
- **`GITLAB_TOKEN`** (a project/group access token with `api` scope) takes
  precedence when set — required on instances where the job token can't post
  notes. Set it as a masked CI/CD variable.

No `curl`/`jq` needed: the note poster uses Python stdlib (`urllib`), so the
default slim image works.

## Publishing (owner-only)

GitLab CI/CD Catalog components must live in their own project marked as a
catalog resource:

1. Create a GitLab project `<group>/whatifd-gitlab` (public, or internal per
   your org).
2. Add `templates/whatifd-fork.yml` (copy from this monorepo path) + a README
   at the project root. The component path becomes
   `whatifd-fork` (file `templates/whatifd-fork.yml`).
3. In the project: **Settings → General → Visibility → CI/CD Catalog project**
   — enable "CI/CD Catalog resource".
4. Create a release (tag `v1.0.0` + a release via the `release:` keyword or the
   UI). Publishing a release lists/updates the component in the Catalog at the
   version + the `@1` major alias.
5. Consumers then `include: component: $CI_SERVER_FQDN/<group>/whatifd-gitlab/whatifd-fork@1`.

Keep `templates/whatifd-fork.yml` in sync with the monorepo source on each
release (manual copy, or a mirror job analogous to the GitHub
`sync-action.yml`).

## Status

| Surface | State |
|---|---|
| Component template (run + gate + artifacts) | ✅ |
| MR-note posting with marker dedup (Notes API, stdlib) | ✅ |
| CI_JOB_TOKEN default + GITLAB_TOKEN fallback | ✅ |
| Catalog project + publication | ❌ owner-only (steps above) |
