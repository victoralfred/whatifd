"""Phase I integration tests — `whatifd-fork` composite GitHub Action.

The action is a thin shell-script wrapper; the tested surface is:

1. The `action.yml` is structurally valid YAML and declares the
   inputs/outputs/runs sections the README documents.
2. The exit-code → verdict mapping covers the CLI's three outcomes.
3. The PR-comment guard fires only on `pull_request` events.
4. The `fail-on-dont-ship` guard fires only when exit_code != '0'.

We don't run the action end-to-end here — that requires a real GitHub
runner. The structural pins catch the most common refactor regressions
(missing input/output, broken guard expression) without that infra.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTION_YML = _REPO_ROOT / ".github" / "actions" / "whatifd-fork" / "action.yml"


@pytest.fixture(scope="module")
def action() -> dict[str, Any]:
    return yaml.safe_load(_ACTION_YML.read_text(encoding="utf-8"))


class TestActionStructure:
    def test_action_yml_exists(self) -> None:
        assert _ACTION_YML.is_file(), f"action.yml missing at {_ACTION_YML}"

    def test_top_level_keys(self, action: dict[str, Any]) -> None:
        for key in ("name", "description", "inputs", "outputs", "runs"):
            assert key in action, f"action.yml missing top-level key: {key}"

    def test_runs_using_composite(self, action: dict[str, Any]) -> None:
        assert action["runs"]["using"] == "composite", (
            "Action must be a composite action — the v0.2 plan calls for a "
            "thin wrapper, not a Docker action."
        )

    def test_runs_has_steps(self, action: dict[str, Any]) -> None:
        steps = action["runs"]["steps"]
        assert isinstance(steps, list) and len(steps) >= 2, (
            "Composite action needs at least 2 steps (run whatifd fork + "
            "PR comment / fail-handler)."
        )


class TestInputs:
    """Every input the README documents must exist in action.yml,
    with the documented default."""

    @pytest.mark.parametrize(
        "name,default",
        [
            ("config", "whatifd.config.yaml"),
            ("profile", ""),
            ("comment-on-pr", "true"),
            ("fail-on-dont-ship", "true"),
        ],
    )
    def test_input_default(self, action: dict[str, Any], name: str, default: str) -> None:
        inputs = action["inputs"]
        assert name in inputs, f"action.yml missing input: {name}"
        assert inputs[name].get("default") == default, (
            f"input {name} default drifted: action.yml={inputs[name].get('default')!r}, "
            f"README documents {default!r}"
        )

    def test_github_token_input_present(self, action: dict[str, Any]) -> None:
        # `github-token` doesn't have a static default we can pin
        # (it's a `${{ github.token }}` expression). Just assert it
        # exists and is documented as defaulting to the workflow
        # token.
        assert "github-token" in action["inputs"]


class TestOutputs:
    """Every output the README documents must exist in action.yml
    and reference a step output."""

    @pytest.mark.parametrize(
        "name",
        ["verdict", "exit-code", "report-json", "report-md"],
    )
    def test_output_present(self, action: dict[str, Any], name: str) -> None:
        outputs = action["outputs"]
        assert name in outputs, f"action.yml missing output: {name}"
        # The value field must reference a step output expression.
        value = outputs[name].get("value", "")
        assert "${{ steps." in value, (
            f"output {name} value must reference a step output, got: {value!r}"
        )


class TestStepGuards:
    """The PR-comment + fail-on-dont-ship steps have load-bearing
    `if:` guards. A future refactor that drops the guard would
    silently post comments on push events (noisy) or fail every
    workflow (broken)."""

    @staticmethod
    def _step_by_name(action: dict[str, Any], name_prefix: str) -> dict[str, Any]:
        for step in action["runs"]["steps"]:
            if step.get("name", "").startswith(name_prefix):
                return step
        raise AssertionError(f"step starting with {name_prefix!r} not found")

    def test_pr_comment_guard_includes_pull_request_event(self, action: dict[str, Any]) -> None:
        step = self._step_by_name(action, "Post PR comment")
        guard = step.get("if", "")
        assert "github.event_name == 'pull_request'" in guard, (
            "PR-comment step must guard on github.event_name == 'pull_request' "
            "so push events don't trigger spurious comments."
        )
        assert "inputs.comment-on-pr == 'true'" in guard, (
            "PR-comment step must respect the `comment-on-pr` input toggle."
        )

    def test_pr_comment_guard_skips_when_no_report(self, action: dict[str, Any]) -> None:
        step = self._step_by_name(action, "Post PR comment")
        guard = step.get("if", "")
        assert "steps.fork.outputs.report_md != ''" in guard, (
            "PR-comment step must skip when no Markdown report was emitted "
            "(setup-failure path, where the CLI exits before writing artifacts)."
        )

    def test_fail_step_guard_respects_input_and_exit_code(self, action: dict[str, Any]) -> None:
        step = self._step_by_name(action, "Fail on Don't Ship")
        guard = step.get("if", "")
        assert "inputs.fail-on-dont-ship == 'true'" in guard, (
            "fail-on-dont-ship step must respect the input toggle."
        )
        assert "steps.fork.outputs.exit_code != '0'" in guard, (
            "fail-on-dont-ship step must only fire when the CLI exit code is non-zero."
        )


class TestExitCodeMapping:
    """The shell script in the `Run whatifd fork` step maps exit
    codes 0/1/2 to verdict strings ship/dont_ship/inconclusive.
    A future contributor adding a new exit code (or renaming a
    verdict) must update both the CLI and this mapping in lockstep.
    """

    @staticmethod
    def _fork_step_run(action: dict[str, Any]) -> str:
        for step in action["runs"]["steps"]:
            if step.get("id") == "fork":
                return step["run"]
        raise AssertionError("fork step not found")

    def test_exit_zero_maps_to_ship(self, action: dict[str, Any]) -> None:
        run = self._fork_step_run(action)
        assert '0) verdict="ship"' in run

    def test_exit_one_maps_to_dont_ship(self, action: dict[str, Any]) -> None:
        run = self._fork_step_run(action)
        assert '1) verdict="dont_ship"' in run

    def test_exit_other_maps_to_inconclusive(self, action: dict[str, Any]) -> None:
        run = self._fork_step_run(action)
        # Exit 2 (and any future non-0/1) → inconclusive. Pinned
        # via the `*)` catch-all branch.
        assert '*) verdict="inconclusive"' in run


class TestExampleWorkflow:
    def test_example_workflow_present(self) -> None:
        # The .example suffix prevents GitHub Actions from running
        # this workflow on the whatifd repo itself (which lacks the
        # adapter credentials the example uses).
        example = _REPO_ROOT / ".github" / "workflows" / "example-whatifd-fork.yml.example"
        assert example.is_file()

    def test_example_uses_local_action_path(self) -> None:
        example = _REPO_ROOT / ".github" / "workflows" / "example-whatifd-fork.yml.example"
        text = example.read_text(encoding="utf-8")
        # Repo-relative path so the example works as a self-contained
        # demonstration. Operators copying the workflow can either
        # vendor the action or switch to a published-Marketplace
        # reference once Phase I.x ships that.
        assert "uses: ./.github/actions/whatifd-fork" in text
