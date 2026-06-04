"""Structural pins for the GitLab CI/CD component (integrations P4).

`integrations/gitlab/templates/whatifd-fork.yml` is the GitLab analog of the
`whatifd-fork` GitHub action. We don't run a GitLab pipeline here; these tests
pin the load-bearing structure — the component spec, the verdict gate, the
marker-based MR-note dedup, the token model — and verify both embedded Python
fragments compile (they live inside YAML block scalars + a heredoc, which is
exactly where indentation bugs hide).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMPONENT = _REPO_ROOT / "integrations" / "gitlab" / "templates" / "whatifd-fork.yml"


def _docs() -> tuple[dict[str, Any], dict[str, Any]]:
    spec, job = yaml.safe_load_all(_COMPONENT.read_text(encoding="utf-8"))
    return spec, job


def _job() -> dict[str, Any]:
    return _docs()[1]["whatifd-fork"]


def _script_text() -> str:
    return "\n".join(_job()["script"])


def test_component_has_two_documents_and_spec_inputs() -> None:
    spec, job = _docs()
    assert "spec" in spec and "inputs" in spec["spec"]
    assert {"stage", "image", "config", "pip-install", "fail-on-dont-ship", "comment-on-mr"} <= set(
        spec["spec"]["inputs"]
    )
    assert "whatifd-fork" in job, "the component must define the `whatifd-fork` job."


def test_job_runs_fork_with_print_paths() -> None:
    script = _script_text()
    assert "whatifd fork --config" in script and "--print-paths" in script, (
        "component must run `whatifd fork --print-paths` (the #93 surface)."
    )


def test_job_gates_on_exit_code() -> None:
    script = _script_text()
    assert 'exit "$exit_code"' in script, (
        "component must gate the pipeline on the verdict exit code."
    )
    assert "WHATIFD_FAIL_ON_DONT_SHIP" in script, "gate must respect the fail-on-dont-ship input."


def test_job_uploads_reports_artifact() -> None:
    job = _job()
    artifacts = job.get("artifacts", {})
    assert artifacts.get("when") == "always"
    assert "reports/" in artifacts.get("paths", [])


def test_mr_note_uses_marker_dedup() -> None:
    script = _script_text()
    assert "<!-- whatifd-fork -->" in script, (
        "MR-note must embed the shared `<!-- whatifd-fork -->` marker for dedup (#94 parity)."
    )
    assert "merge_requests/" in script and "/notes" in script, (
        "MR-note must target the GitLab Notes API."
    )
    # Only on MR pipelines.
    assert "CI_MERGE_REQUEST_IID" in script


def test_mr_note_token_model() -> None:
    script = _script_text()
    # PAT precedence + job-token default, both header forms present.
    assert "GITLAB_TOKEN" in script and "CI_JOB_TOKEN" in script
    assert "PRIVATE-TOKEN" in script and "JOB-TOKEN" in script


def test_embedded_python_fragments_compile() -> None:
    """Both Python fragments (the path-parse `python3 -c` and the MR-note
    heredoc) must compile — they live inside YAML block scalars where a
    dedent/indent bug would otherwise only surface at pipeline runtime."""
    script = _script_text()

    heredoc = re.search(r"<<'PYEOF'\n(.*?)\nPYEOF", script, re.S)
    assert heredoc, "MR-note PYEOF heredoc not found"
    compile(heredoc.group(1), "<mr-note>", "exec")

    inline = re.search(r"python3 -c '\n(.*?)\n\s*'\)", script, re.S)
    assert inline, "inline `python3 -c` path-parse not found"
    compile(inline.group(1), "<path-parse>", "exec")


def test_path_parse_extracts_report_md() -> None:
    """The inline path-parse fragment must extract report_md from a real
    --print-paths JSON line (functional, not just structural)."""
    script = _script_text()
    code = re.search(r"python3 -c '\n(.*?)\n\s*'\)", script, re.S).group(1)
    sample = 'progress line\n{"report_json":"r.json","report_md":"reports/r.md","verdict":"ship"}'
    result = subprocess.run(
        ["python3", "-c", code], input=sample, capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "reports/r.md"
