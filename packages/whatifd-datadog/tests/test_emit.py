"""Tests for the P1b verdict-metrics emitter (`whatifd_datadog.emit`).

No network: `report_to_metrics` is pure, and the CLI/`emit_report` paths are
exercised with `dry_run` or error inputs. The metric projection is pinned
against a real-shaped `ReportV01` JSON (the fields confirmed in
`src/whatifd/types/cohort.py` + a live report sample).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whatifd_datadog.emit import (
    VERDICT_CODE,
    Metric,
    emit_report,
    main,
    report_to_metrics,
)


def _report(verdict: str = "inconclusive") -> dict[str, Any]:
    """A real-shaped ReportV01 dict (subset the emitter reads)."""
    return {
        "verdict_state": verdict,
        "experiment_shape": "failure_rescue",
        "cohort_results": [
            {
                "name": "failure",
                "selected": 20,
                "replayed": 20,
                "scored": 20,
                "improved_count": 14,
                "regressed_count": 2,
                "unchanged_count": 4,
                "median_delta": 0.31,
                "ci_lower": 0.18,
                "ci_upper": 0.44,
                "floor_passed": True,
            },
            {
                "name": "baseline",
                "selected": 20,
                "replayed": 20,
                "scored": 20,
                "improved_count": 3,
                "regressed_count": 1,
                "unchanged_count": 16,
                "median_delta": 0.02,
                "ci_lower": None,
                "ci_upper": None,
                "floor_passed": False,
            },
        ],
        "decision_findings": [
            {"code": "baseline_regression_above_threshold", "severity": "blocks_ship"},
            {"code": "improvement_observed", "severity": "info"},
            {"code": "ci_unavailable_for_required_cohort", "severity": "blocks_all"},
        ],
    }


def _by_name(metrics: list[Metric], name: str) -> list[Metric]:
    return [m for m in metrics if m.name == name]


def test_verdict_code_mapping() -> None:
    assert VERDICT_CODE == {"ship": 0, "dont_ship": 1, "inconclusive": 2}
    for verdict, code in VERDICT_CODE.items():
        [vc] = _by_name(report_to_metrics(_report(verdict)), "whatifd.verdict.code")
        assert vc.value == float(code)
        assert f"verdict:{verdict}" in vc.tags


def test_cohort_metrics_tagged_and_complete() -> None:
    metrics = report_to_metrics(_report())
    failure = [m for m in metrics if "cohort:failure" in m.tags]
    names = {m.name for m in failure}
    assert {
        "whatifd.cohort.selected",
        "whatifd.cohort.scored",
        "whatifd.cohort.improved",
        "whatifd.cohort.regressed",
        "whatifd.cohort.median_delta",
        "whatifd.cohort.floor_passed",
        "whatifd.cohort.regression_ratio",
        "whatifd.cohort.improvement_ratio",
    } <= names
    [floor] = _by_name(failure, "whatifd.cohort.floor_passed")
    assert floor.value == 1.0
    [reg_ratio] = _by_name(failure, "whatifd.cohort.regression_ratio")
    assert reg_ratio.value == pytest.approx(2 / 20)


def test_null_numerics_skipped_not_zeroed() -> None:
    # baseline has ci_lower/ci_upper = None → those metrics must be absent,
    # not emitted as 0.0.
    baseline = [m for m in report_to_metrics(_report()) if "cohort:baseline" in m.tags]
    assert _by_name(baseline, "whatifd.cohort.ci_lower") == []
    assert _by_name(baseline, "whatifd.cohort.ci_upper") == []
    # floor_passed=False still emits an explicit 0.0 (it's a real signal).
    [floor] = _by_name(baseline, "whatifd.cohort.floor_passed")
    assert floor.value == 0.0


def test_zero_scored_skips_ratios() -> None:
    # scored=0 → no divide; ratios must be absent (not 0/0 or a crash).
    report = {
        "verdict_state": "inconclusive",
        "cohort_results": [
            {
                "name": "failure",
                "scored": 0,
                "improved_count": 0,
                "regressed_count": 0,
                "floor_passed": False,
            },
        ],
    }
    metrics = report_to_metrics(report)
    assert _by_name(metrics, "whatifd.cohort.regression_ratio") == []
    assert _by_name(metrics, "whatifd.cohort.improvement_ratio") == []


def test_non_numeric_scored_skips_ratios() -> None:
    # A non-numeric `scored` (None) must also skip ratios, not coerce to 0
    # and silently pass the guard with a wrong denominator.
    report = {
        "verdict_state": "inconclusive",
        "cohort_results": [
            {"name": "failure", "scored": None, "improved_count": 5, "floor_passed": True},
        ],
    }
    metrics = report_to_metrics(report)
    assert _by_name(metrics, "whatifd.cohort.regression_ratio") == []
    # scored itself is null → its count metric is skipped too.
    assert _by_name(metrics, "whatifd.cohort.scored") == []


def test_absent_floor_passed_skipped_not_ghost_zero() -> None:
    # When a cohort dict omits `floor_passed` entirely, the metric must be
    # SKIPPED — not emitted as a ghost 0.0 (null-skip guarantee, cardinal #1).
    report = {
        "verdict_state": "ship",
        "cohort_results": [{"name": "failure", "scored": 3, "improved_count": 3}],
    }
    metrics = report_to_metrics(report)
    assert _by_name(metrics, "whatifd.cohort.floor_passed") == []


def test_blocking_findings_counted() -> None:
    [blocking] = _by_name(report_to_metrics(_report()), "whatifd.findings.blocking")
    # blocks_ship + blocks_all = 2; the info finding is excluded.
    assert blocking.value == 2.0


def test_extra_tags_attached_everywhere() -> None:
    metrics = report_to_metrics(_report(), extra_tags=("service:my-agent", "ci:gh"))
    assert all("service:my-agent" in m.tags and "ci:gh" in m.tags for m in metrics)


def test_emit_report_dry_run_no_network(tmp_path: Path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps(_report("ship")))
    metrics = emit_report(p, api_key=None, timestamp=123, dry_run=True)
    assert any(m.name == "whatifd.verdict.code" and m.value == 0.0 for m in metrics)


def test_emit_report_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        emit_report(tmp_path / "nope.json", api_key="k", timestamp=1)


def test_emit_report_malformed_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        emit_report(p, api_key="k", timestamp=1)


def test_emit_report_missing_api_key_raises_when_submitting(tmp_path: Path) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps(_report()))
    with pytest.raises(RuntimeError, match="DD_API_KEY"):
        emit_report(p, api_key=None, timestamp=1, dry_run=False)


def test_cli_dry_run_prints_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "report.json"
    p.write_text(json.dumps(_report("dont_ship")))
    rc = main([str(p), "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "whatifd.verdict.code 1.0" in out


def test_cli_soft_fails_on_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    # Default: a missing report must NOT fail the CI step (exit 0).
    rc = main(["/nonexistent/report.json"])
    assert rc == 0
    assert "soft-fail" in capsys.readouterr().err


def test_cli_strict_fails_on_missing_file() -> None:
    rc = main(["/nonexistent/report.json", "--strict"])
    assert rc == 1
