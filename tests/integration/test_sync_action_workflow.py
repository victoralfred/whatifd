"""Structural pins for `.github/workflows/sync-action.yml` (integrations P3).

The workflow syncs the composite action to the dedicated `whatifd-action`
repo for Marketplace publication. It's inert until provisioned (guarded on the
`ACTION_SYNC_TOKEN` secret), so these tests pin the load-bearing structure —
the guard, the target repo, and the version/major tagging — without a real
cross-repo run. See docs/internal/marketplace-publish-runbook.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYNC_YML = _REPO_ROOT / ".github" / "workflows" / "sync-action.yml"


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(_SYNC_YML.read_text(encoding="utf-8"))


def _sync_job_runs() -> str:
    wf = _workflow()
    steps = wf["jobs"]["sync"]["steps"]
    return "\n".join(s.get("run", "") for s in steps)


def test_workflow_is_valid_yaml() -> None:
    wf = _workflow()
    assert isinstance(wf, dict)
    assert "jobs" in wf and "sync" in wf["jobs"]


def test_triggers_on_release_tags_and_dispatch() -> None:
    wf = _workflow()
    # `on:` parses to Python True under YAML 1.1 (unquoted on/off bool quirk).
    on = wf.get("on", wf.get(True))
    assert "push" in on and on["push"]["tags"] == ["v*.*.*"], (
        "sync must trigger on release tags so each release refreshes the action repo."
    )
    assert "workflow_dispatch" in on, (
        "sync must also be manually dispatchable for the initial seed."
    )


def test_guarded_on_sync_token() -> None:
    runs = _sync_job_runs()
    assert "ACTION_SYNC_TOKEN" in runs, (
        "sync job must guard on the ACTION_SYNC_TOKEN secret so it no-ops "
        "(not errors) before P3 is provisioned."
    )
    # Every working step is gated on the guard's skip output.
    steps = _workflow()["jobs"]["sync"]["steps"]
    gated = [s for s in steps if s.get("id") != "guard"]
    assert all("steps.guard.outputs.skip == 'false'" in s.get("if", "") for s in gated), (
        "every non-guard step must be gated on steps.guard.outputs.skip == 'false'."
    )


def test_targets_dedicated_action_repo() -> None:
    steps = _workflow()["jobs"]["sync"]["steps"]
    checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout")]
    repos = [s.get("with", {}).get("repository") for s in checkouts if s.get("with")]
    assert "victoralfred/whatifd-action" in repos, (
        "sync must check out the dedicated whatifd-action repo (Marketplace "
        "needs a root-level action.yml)."
    )


def test_syncs_action_and_readme_with_version_and_major_tags() -> None:
    runs = _sync_job_runs()
    assert "action-repo/action.yml" in runs, "sync must copy action.yml to the target root."
    assert "action-repo/README.md" in runs, "sync must produce a marketplace README."
    # Exact version tag + moving major tag (consumers pin @v<major>).
    assert 'git tag -f "v${ver}"' in runs, "sync must tag the exact version."
    assert 'git tag -f "${major}"' in runs, "sync must move the major tag for @v<major> pins."
    # README usage is rewritten from the monorepo local path to the published ref.
    assert "uses: victoralfred/whatifd-action@" in runs, (
        "sync must rewrite the README's local-path usage to the published reference."
    )
