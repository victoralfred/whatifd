"""Phase I integration tests — `whatifd-fork` composite GitHub Action.

The action is a thin shell-script wrapper; the tested surface is:

1. The `action.yml` is structurally valid YAML and declares the
   inputs/outputs/runs sections the README documents.
2. The exit-code → verdict mapping covers the CLI's three outcomes.
3. The fork step reads report paths from `whatifd fork --print-paths` (#93)
   rather than a fragile glob+mtime scan.
4. The PR-comment step dedups via an HTML marker + `gh api` search (#94),
   not the locale-fragile `--edit-last` stderr heuristic.
5. The PR-comment guard fires only on `pull_request` events; the
   `fail-on-dont-ship` guard fires only when exit_code != '0'.

We don't run the action end-to-end here — that requires a real GitHub
runner. The structural pins catch the most common refactor regressions
(missing input/output, broken guard expression) without that infra.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict, cast

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTION_YML = _REPO_ROOT / ".github" / "actions" / "whatifd-fork" / "action.yml"


# Typed shape for the parsed action.yml. The outer Mapping signals
# read-only intent (project convention). `Any` remains at the leaf where
# YAML scalars can be str/int/bool/None and `extra` keys may appear.
class ActionStepDict(TypedDict, total=False):
    name: str
    id: str
    run: str
    uses: str
    shell: str
    env: Mapping[str, str]


class ActionInputSpec(TypedDict, total=False):
    description: str
    required: bool
    default: str


class ActionOutputSpec(TypedDict, total=False):
    description: str
    value: str


class ActionRunsBlock(TypedDict, total=False):
    using: str
    steps: list[Mapping[str, Any]]


class ActionBrandingBlock(TypedDict, total=False):
    icon: str
    color: str


class ActionYmlData(TypedDict, total=False):
    name: str
    description: str
    inputs: Mapping[str, ActionInputSpec]
    outputs: Mapping[str, ActionOutputSpec]
    runs: ActionRunsBlock
    branding: ActionBrandingBlock


@pytest.fixture(scope="module")
def action() -> ActionYmlData:
    raw = yaml.safe_load(_ACTION_YML.read_text(encoding="utf-8"))
    return cast(ActionYmlData, raw)


def _step_by_id(action: ActionYmlData, step_id: str) -> Mapping[str, Any]:
    for step in action["runs"]["steps"]:
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"step with id {step_id!r} not found")


def _step_by_name(action: ActionYmlData, name_prefix: str) -> Mapping[str, Any]:
    for step in action["runs"]["steps"]:
        if step.get("name", "").startswith(name_prefix):
            return step
    raise AssertionError(f"step starting with {name_prefix!r} not found")


class TestMarketplaceReadiness:
    """Marketplace listings require a `branding:` block with `icon` and
    `color`. Verifying it now prevents a last-minute schema surprise during
    the marketplace-publication PR (integrations-plan P3)."""

    def test_branding_block_present(self, action: ActionYmlData) -> None:
        assert "branding" in action, (
            "action.yml must declare a `branding:` block for Marketplace "
            "publication (icon + color)."
        )
        assert isinstance(action["branding"], dict), "branding must be a YAML mapping"

    def test_branding_has_icon_and_color(self, action: ActionYmlData) -> None:
        branding = action["branding"]
        assert "icon" in branding, "branding.icon is required for Marketplace listings"
        assert "color" in branding, "branding.color is required for Marketplace listings"
        accepted_colors = {
            "white",
            "yellow",
            "blue",
            "green",
            "orange",
            "red",
            "purple",
            "gray-dark",
        }
        assert branding["color"] in accepted_colors, (
            f"branding.color={branding['color']!r} not in GitHub's accepted set: "
            f"{sorted(accepted_colors)}"
        )


class TestActionStructure:
    def test_action_yml_exists(self) -> None:
        assert _ACTION_YML.is_file(), f"action.yml missing at {_ACTION_YML}"

    def test_top_level_keys(self, action: ActionYmlData) -> None:
        for key in ("name", "description", "inputs", "outputs", "runs"):
            assert key in action, f"action.yml missing top-level key: {key}"

    def test_runs_using_composite(self, action: ActionYmlData) -> None:
        assert action["runs"]["using"] == "composite", (
            "Action must be a composite action — a thin wrapper, not a Docker action."
        )

    def test_runs_has_steps(self, action: ActionYmlData) -> None:
        steps = action["runs"]["steps"]
        assert isinstance(steps, list) and len(steps) >= 2, (
            "Composite action needs at least 2 steps (run whatifd fork + "
            "PR comment / fail-handler)."
        )

    def test_runs_steps_is_list_not_map(self, action: ActionYmlData) -> None:
        assert isinstance(action["runs"]["steps"], list), (
            "runs.steps must be a YAML sequence (list of step mappings). "
            "Got a dict — likely a missing `- ` prefix on a step key."
        )

    def test_inputs_and_outputs_are_maps_of_maps(self, action: ActionYmlData) -> None:
        for section in ("inputs", "outputs"):
            value = action[section]
            assert isinstance(value, dict), f"{section} must be a YAML mapping"
            for name, spec in value.items():
                assert isinstance(spec, dict), (
                    f"{section}.{name} must be a mapping, got {type(spec).__name__}"
                )
                assert "description" in spec, (
                    f"{section}.{name} missing required `description` field"
                )


class TestInputs:
    """Every input the README documents must exist with the documented default."""

    @pytest.mark.parametrize(
        "name,default",
        [
            ("config", "whatifd.config.yaml"),
            ("profile", ""),
            ("comment-on-pr", "true"),
            ("fail-on-dont-ship", "true"),
        ],
    )
    def test_input_default(self, action: ActionYmlData, name: str, default: str) -> None:
        inputs = action["inputs"]
        assert name in inputs, f"action.yml missing input: {name}"
        assert inputs[name].get("default") == default, (
            f"input {name} default drifted: action.yml={inputs[name].get('default')!r}, "
            f"README documents {default!r}"
        )

    def test_github_token_input_default_pinned(self, action: ActionYmlData) -> None:
        assert "github-token" in action["inputs"]
        assert action["inputs"]["github-token"].get("default") == "${{ github.token }}", (
            "github-token default drifted away from `${{ github.token }}`."
        )


class TestOutputs:
    """Every output the README documents must exist and reference a step output."""

    @pytest.mark.parametrize(
        "name",
        ["verdict", "exit-code", "report-json", "report-md"],
    )
    def test_output_present(self, action: ActionYmlData, name: str) -> None:
        outputs = action["outputs"]
        assert name in outputs, f"action.yml missing output: {name}"
        value = outputs[name].get("value", "")
        assert "${{ steps." in value, (
            f"output {name} value must reference a step output, got: {value!r}"
        )


class TestIfExpressionWrapping:
    """Multi-line `if:` expressions with `&&` must use `${{ }}` interpolation
    (GitHub's safe form)."""

    def test_pr_comment_if_uses_interpolation_wrapper(self, action: ActionYmlData) -> None:
        guard = _step_by_name(action, "Post PR comment").get("if", "")
        assert guard.startswith("${{") and guard.rstrip().endswith("}}"), (
            "PR-comment step's `if:` must be wrapped in `${{ ... }}`."
        )

    def test_fail_step_if_uses_interpolation_wrapper(self, action: ActionYmlData) -> None:
        guard = _step_by_name(action, "Fail on Don't Ship").get("if", "")
        assert guard.startswith("${{") and guard.rstrip().endswith("}}"), (
            "fail-on-dont-ship step's `if:` must be wrapped in `${{ ... }}`."
        )


class TestExitCodeMapping:
    """The `Run whatifd fork` step maps exit codes 0/1/2 → ship/dont_ship/
    inconclusive. The CLI and this mapping must move in lockstep."""

    def test_exit_zero_maps_to_ship(self, action: ActionYmlData) -> None:
        assert '0) verdict="ship"' in _step_by_id(action, "fork")["run"]

    def test_exit_one_maps_to_dont_ship(self, action: ActionYmlData) -> None:
        assert '1) verdict="dont_ship"' in _step_by_id(action, "fork")["run"]

    def test_exit_other_maps_to_inconclusive(self, action: ActionYmlData) -> None:
        assert '*) verdict="inconclusive"' in _step_by_id(action, "fork")["run"]


class TestPrintPathsPathDiscovery:
    """#93: the fork step learns the report paths from `whatifd fork
    --print-paths` (a JSON object on stdout), NOT a glob+mtime scan."""

    def test_fork_step_invokes_print_paths(self, action: ActionYmlData) -> None:
        run = _step_by_id(action, "fork")["run"]
        assert "--print-paths" in run, (
            "fork step must run `whatifd fork --print-paths` so it reads the "
            "exact written report paths instead of discovering them (#93)."
        )

    def test_fork_step_does_not_glob_reports(self, action: ActionYmlData) -> None:
        run = _step_by_id(action, "fork")["run"]
        assert "glob.glob('reports" not in run and 'glob.glob("reports' not in run, (
            "fork step must not fall back to glob('reports/*') discovery — "
            "--print-paths supersedes it (#93)."
        )

    def test_fork_step_parses_paths_from_json(self, action: ActionYmlData) -> None:
        run = _step_by_id(action, "fork")["run"]
        # The paths come from the --print-paths JSON, parsed with jq
        # (preinstalled on GitHub-hosted runners) and written to GITHUB_OUTPUT.
        assert "jq -r" in run, "fork step must parse the --print-paths JSON with jq."
        assert ".report_json" in run and ".report_md" in run, (
            "fork step must extract report_json / report_md from the JSON."
        )
        assert "report_json=" in run and "report_md=" in run, (
            "fork step must export report_json / report_md to GITHUB_OUTPUT."
        )


class TestStepGuards:
    """Load-bearing `if:` guards on the PR-comment + fail steps."""

    def test_pr_comment_guard_includes_pull_request_event(self, action: ActionYmlData) -> None:
        guard = _step_by_name(action, "Post PR comment").get("if", "")
        assert "github.event_name == 'pull_request'" in guard, (
            "PR-comment step must guard on github.event_name == 'pull_request'."
        )
        assert "inputs.comment-on-pr == 'true'" in guard, (
            "PR-comment step must respect the `comment-on-pr` input toggle."
        )

    def test_pr_comment_guard_skips_when_no_report(self, action: ActionYmlData) -> None:
        guard = _step_by_name(action, "Post PR comment").get("if", "")
        assert "steps.fork.outputs.report_md != ''" in guard, (
            "PR-comment step must skip when no Markdown report was emitted (setup-failure path)."
        )

    def test_fail_step_guard_respects_input_and_exit_code(self, action: ActionYmlData) -> None:
        guard = _step_by_name(action, "Fail on Don't Ship").get("if", "")
        assert "inputs.fail-on-dont-ship == 'true'" in guard, (
            "fail-on-dont-ship step must respect the input toggle."
        )
        assert "steps.fork.outputs.exit_code != '0'" in guard, (
            "fail-on-dont-ship step must only fire when the CLI exit code is non-zero."
        )


class TestMarkerBasedComment:
    """#94: the PR-comment step dedups via an HTML marker + `gh api` search,
    NOT `gh pr comment --edit-last` + a locale-fragile stderr grep."""

    def test_comment_embeds_html_marker(self, action: ActionYmlData) -> None:
        run = _step_by_name(action, "Post PR comment")["run"]
        assert "<!-- whatifd-fork -->" in run, (
            "PR-comment step must embed the `<!-- whatifd-fork -->` marker so "
            "the prior comment is found exactly (locale-independent)."
        )

    def test_comment_finds_prior_via_api_search(self, action: ActionYmlData) -> None:
        run = _step_by_name(action, "Post PR comment")["run"]
        assert "gh api" in run, "PR-comment step must search comments via `gh api`."
        assert "issues/${PR_NUMBER}/comments" in run or "issues/$PR_NUMBER/comments" in run, (
            "PR-comment step must list the PR's comments to find the marked one."
        )
        assert "contains(" in run, (
            "PR-comment step must select the comment whose body contains the marker."
        )

    def test_comment_edits_existing_or_creates(self, action: ActionYmlData) -> None:
        run = _step_by_name(action, "Post PR comment")["run"]
        assert "--method PATCH" in run, (
            "PR-comment step must PATCH the existing marked comment (edit in place)."
        )
        assert "gh pr comment" in run, (
            "PR-comment step must create a fresh comment when no marked one exists."
        )

    def test_comment_does_not_use_edit_last_heuristic(self, action: ActionYmlData) -> None:
        run = _step_by_name(action, "Post PR comment")["run"]
        assert "--edit-last" not in run, (
            "PR-comment step must not use `--edit-last` — the marker search replaces it (#94)."
        )
        assert "grep -qiE" not in run, (
            "PR-comment step must not grep `gh` stderr — locale-fragile (#94)."
        )


class TestNoHardcodedTmpPath:
    """The PR-comment step uses a per-job temp dir, not a hardcoded /tmp path
    (matrix-job collision safety)."""

    def test_pr_comment_step_uses_runner_temp(self, action: ActionYmlData) -> None:
        run = _step_by_name(action, "Post PR comment")["run"]
        assert "$RUNNER_TEMP" in run or "${RUNNER_TEMP" in run, (
            "PR-comment step must reference $RUNNER_TEMP for matrix-safe temp paths."
        )
        assert "/tmp/whatifd-pr-comment" not in run, (
            "PR-comment step contains a hardcoded /tmp path; use $RUNNER_TEMP."
        )


class TestFailStepDoesNotDuplicateAnnotation:
    """The fork step already emits `::error` for dont_ship/inconclusive; the
    fail step only sets the exit code."""

    def test_fail_step_has_no_error_echo(self, action: ActionYmlData) -> None:
        run = _step_by_name(action, "Fail on Don't Ship")["run"]
        assert "::error" not in run, (
            "Fail step must not emit ::error — the fork step already emitted one."
        )


class TestExampleWorkflow:
    def test_example_workflow_present(self) -> None:
        example = _REPO_ROOT / ".github" / "workflows" / "example-whatifd-fork.yml.example"
        assert example.is_file()

    def test_example_uses_local_action_path(self) -> None:
        example = _REPO_ROOT / ".github" / "workflows" / "example-whatifd-fork.yml.example"
        text = example.read_text(encoding="utf-8")
        assert "uses: ./.github/actions/whatifd-fork" in text

    def test_example_workflow_is_valid_yaml(self) -> None:
        example = _REPO_ROOT / ".github" / "workflows" / "example-whatifd-fork.yml.example"
        parsed = yaml.safe_load(example.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)
        assert "name" in parsed
        on_key = next((k for k in parsed if k in ("on", True)), None)
        assert on_key is not None, (
            "example workflow missing the `on:` trigger key (or its boolean-True YAML 1.1 alias)"
        )
        assert "jobs" in parsed
        assert isinstance(parsed["jobs"], dict)


class TestEveryStepDeclaresBashShell:
    """Every `run:` step declares `shell: bash` so Windows runners use Git
    Bash rather than defaulting to PowerShell."""

    def test_every_run_step_has_shell_bash(self, action: ActionYmlData) -> None:
        offenders: list[str] = []
        for step in action["runs"]["steps"]:
            if "run" in step and step.get("shell") != "bash":
                name = step.get("name", step.get("id", "<unnamed>"))
                offenders.append(f"{name!r} (shell={step.get('shell')!r})")
        assert not offenders, (
            "Every `run:` step must declare `shell: bash`. Offenders:\n  " + "\n  ".join(offenders)
        )
