# whatifd-fork action

Composite GitHub Action wrapping `whatifd fork --config <path>`. Phase I of
the v0.2 roadmap.

The CLI is already CI-ready (config-file driven, structured exit codes,
deterministic artifacts under `./reports/`); this Action saves the
boilerplate of capturing the artifacts, posting the verdict to the PR, and
mapping the exit code to a status annotation.

## Usage

```yaml
# .github/workflows/whatifd-pr-check.yml
name: whatifd PR verdict

on:
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: write   # required for the PR comment

jobs:
  whatifd:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up uv
        uses: astral-sh/setup-uv@v7
        with:
          python-version: "3.12"

      - name: Install whatifd
        run: uv pip install whatifd whatifd-langfuse whatifd-inspect-ai

      - name: Run whatifd fork
        uses: ./.github/actions/whatifd-fork
        with:
          config: whatifd.config.yaml
          # Optional inputs (defaults shown):
          # profile: ""
          # comment-on-pr: "true"
          # fail-on-dont-ship: "true"
          # github-token: ${{ github.token }}
        env:
          # Adapter credentials per cfg.source / cfg.scorer.
          LANGFUSE_HOST: ${{ secrets.LANGFUSE_HOST }}
          LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
          LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `config` | `whatifd.config.yaml` | Path to the whatifd config file. |
| `profile` | `""` | Reporting profile override (must match `cfg.reporting.profile`; `forensic` requires the acknowledgment block per cardinal #7). |
| `comment-on-pr` | `"true"` | Post the rendered Markdown verdict as a PR comment on `pull_request` events. |
| `github-token` | `${{ github.token }}` | Token used by `gh pr comment`. Override with a PAT to author from a bot account. |
| `fail-on-dont-ship` | `"true"` | Fail the workflow when the verdict is Don't Ship (1) or Inconclusive / setup failure (2). Set to `"false"` to expose the verdict as an output and let downstream steps decide. |

## Outputs

| Output | Description |
|---|---|
| `verdict` | `ship` / `dont_ship` / `inconclusive`. Mirrors the CLI exit code. |
| `exit-code` | Raw exit code: `0` / `1` / `2`. |
| `report-json` | Path to the emitted `ReportV01` JSON file. |
| `report-md` | Path to the emitted Markdown verdict file. |

## Permissions

When `comment-on-pr: true` (the default) the action posts to the PR via
`gh pr comment`. The workflow that uses this action must grant
`pull-requests: write` on the `permissions:` block, otherwise the comment
step fails with a 403.

## Cardinal alignment

- **#1 (failure-as-data):** the action surfaces every outcome as a
  GitHub annotation (`::notice` / `::warning` / `::error`) carrying the
  verdict string. No stack traces leak through the workflow log unless the
  CLI itself crashes (which would be a real bug, not a verdict).
- **#2 (trust floor):** floor-failure Inconclusives produce exit 2,
  which the action maps to `verdict=inconclusive`. The same workflow
  behavior fires whether the floor failed or the policy fired — both are
  "not Ship and not a clean reject" from the CI gate's perspective.
- **#7 (two-affirmation):** when `profile: forensic` is set on the
  action, the CLI's two-affirmation check still fires against the
  config's `forensic_acknowledgment` block. The action does NOT bypass
  cardinal #7.

## Security: pinning third-party actions

The whatifd repo's pinning convention — and the rationale — lives
in [`CONTRIBUTING.md` § "Third-party action pinning convention"](../../../CONTRIBUTING.md#third-party-action-pinning-convention).
Read that section for the canonical guidance; this README and the
example workflow's inline comment both defer to it.

**Short version for operators copying the example into production:**
the whatifd repo uses `@v7` tag pins. For security-hardened
production forks, follow GitHub's recommendation and switch each
`uses: ...@v7` to `uses: ...@<sha>  # v7.x.y` before checking in.

## Edge cases

### `--edit-last` and token-author identity

The PR-comment step uses `gh pr comment --edit-last`, which updates
the most-recent comment **authored by the supplied token**. If the
`github-token` input changes between workflow runs on the same PR
(e.g., a workflow swaps from the default `${{ github.token }}` to a
custom PAT, or vice versa), `--edit-last` searches only for comments
authored by the new token. The previous comment authored by the old
token stays put, and a fresh comment from the new token gets added —
producing a two-comment stack instead of one rolling comment.

If you need consistent identity across runs, pin the token (PAT or
default) and don't switch between them mid-PR. Or, accept the
two-comment outcome as the cost of changing comment authorship.

## What this Action does NOT do

- **Upload `./reports/` as a workflow artifact.** The action emits
  `report-json` and `report-md` as outputs (paths to the rendered
  files) but does not call `actions/upload-artifact`. Operators who
  want the JSON/Markdown available for download from the workflow
  run UI should add an explicit upload step:
  ```yaml
  - uses: actions/upload-artifact@v4
    if: always()
    with:
      name: whatifd-report
      path: reports/
  ```
  The `if: always()` makes the upload run even when the verdict
  fails the workflow (the report is most useful precisely on
  Don't Ship and Inconclusive verdicts).
- Manage adapter credentials. Set `LANGFUSE_*` / `ANTHROPIC_API_KEY` in
  the workflow's `env:` from your repo secrets.
- Install whatifd. Use a separate `pip install` step (see usage example);
  the action assumes `whatifd` is on `$PATH`.
- Render or annotate diff against a previous report. Use `whatifd diff`
  in a downstream step if you want a regression-vs-baseline view.

## Status

| Surface | v0.2 |
|---|---|
| Composite action wrapping `whatifd fork` | ✅ |
| PR comment with rendered verdict (with `--edit-last` rolling-update) | ✅ |
| Status annotation (notice / error) | ✅ |
| Exit-code mapping → `verdict` output | ✅ |
| Linux runners (`ubuntu-latest`) | ✅ |
| macOS runners (`macos-latest`) | ✅ — path discovery is portable Python |
| Windows runners (`windows-latest`) | ⚠️ — works because every step declares `shell: bash` (Git Bash is preinstalled). PowerShell-only runners are unsupported. |
| Marketplace publication (separate repo) | ❌ — v0.3+ |
| `whatifd diff` regression workflow | ❌ — v0.3+ |
| Marker-based PR-comment dedup (locale-independent) | ❌ — issue #94 (current `--edit-last` + grep heuristic works on English-locale runners) |
