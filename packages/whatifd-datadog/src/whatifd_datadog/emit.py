"""Emit whatifd verdict + cohort metrics to Datadog (the P1b "sink").

This is a **CI-side emitter, deliberately OUT of whatifd core** — it reads the
`ReportV01` JSON that `whatifd fork` already wrote and pushes a handful of
gauges to Datadog's metrics API so dashboards/monitors can track verdict and
regression trends. It does NOT touch the verdict path: the verdict is the
`whatifd fork` exit code; this runs afterward and only reports.

## Why soft-fail by default

A metrics emitter must never turn a green verdict red. `emit_report` (and the
`whatifd-datadog-emit` CLI) default to **soft-fail**: any submission error is
logged to stderr and the process exits 0. Pass `--strict` (CLI) /
`strict=True` to surface emission failures as a non-zero exit instead.

## Transport

Agentless HTTP to `POST https://api.{site}/api/v1/series` with the `DD-API-KEY`
header (the metrics intake needs only the API key, not the Application key —
unlike the Export API the read adapter uses). `httpx` is the `[live]` extra,
lazily imported.

## Cardinal alignment

- Out of core (the "more defensible verdict?" test fails for a sink, so it
  lives in the optional adapter package, never in `whatifd` core).
- #1: a missing report file / unreadable JSON is a structured, actionable
  error; emission transport errors are logged, not silently swallowed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Verdict → numeric code, matching the `whatifd fork` exit codes (0/1/2) so a
# monitor can alert on `whatifd.verdict.code > 0`.
VERDICT_CODE: dict[str, int] = {"ship": 0, "dont_ship": 1, "inconclusive": 2}

_SERIES_PATH = "/api/v1/series"


@dataclass(frozen=True, slots=True)
class Metric:
    """One gauge point: name, value, and tags (already `key:value` strings)."""

    name: str
    value: float
    tags: tuple[str, ...] = field(default_factory=tuple)


def _num(value: Any) -> float | None:
    """Coerce a JSON number to float; None/non-numeric → None (skip the metric
    rather than emit a bogus 0)."""
    if isinstance(value, bool):  # bool is an int subclass — exclude it here
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def report_to_metrics(report: dict[str, Any], *, extra_tags: Sequence[str] = ()) -> list[Metric]:
    """Project a `ReportV01` dict into a flat list of gauge metrics.

    Run-level: `whatifd.verdict.code` (0/1/2) + `whatifd.findings.blocking`.
    Per cohort (tagged `cohort:<name>`): selected / replayed / scored /
    improved / regressed / unchanged counts, `median_delta`, `floor_passed`
    (1/0), `ci_lower`/`ci_upper` when present, and `regression_ratio` /
    `improvement_ratio` (scored>0). Null numerics are skipped, not zeroed.
    """
    base = tuple(extra_tags)
    verdict = str(report.get("verdict_state", "unknown"))
    shape = str(report.get("experiment_shape", "unknown"))
    run_tags = (*base, f"verdict:{verdict}", f"experiment_shape:{shape}")

    metrics: list[Metric] = [
        Metric("whatifd.verdict.code", float(VERDICT_CODE.get(verdict, -1)), run_tags)
    ]

    for cohort in report.get("cohort_results") or []:
        name = str(cohort.get("name", "unknown"))
        ctags = (*base, f"cohort:{name}", f"verdict:{verdict}")
        count_fields = (
            ("selected", "selected"),
            ("replayed", "replayed"),
            ("scored", "scored"),
            ("improved_count", "improved"),
            ("regressed_count", "regressed"),
            ("unchanged_count", "unchanged"),
        )
        for src_key, metric_suffix in count_fields:
            v = _num(cohort.get(src_key))
            if v is not None:
                metrics.append(Metric(f"whatifd.cohort.{metric_suffix}", v, ctags))

        for src_key in ("median_delta", "ci_lower", "ci_upper"):
            v = _num(cohort.get(src_key))
            if v is not None:
                metrics.append(Metric(f"whatifd.cohort.{src_key}", v, ctags))

        # Only emit when the key is present: an ABSENT `floor_passed` means the
        # cohort never ran floor evaluation, and emitting 0.0 would be a ghost
        # metric (null-skip guarantee, cardinal #1). An explicit `False` still
        # emits 0.0 — that's a real signal.
        if "floor_passed" in cohort:
            metrics.append(
                Metric(
                    "whatifd.cohort.floor_passed",
                    1.0 if cohort["floor_passed"] else 0.0,
                    ctags,
                )
            )

        # Explicit None check (not `_num(...) or 0.0`) so the null-skip intent
        # is unambiguous: a null/non-numeric `scored` skips the ratios rather
        # than coercing to a 0.0 denominator. Numerators default to 0 only when
        # `scored > 0` is already established.
        scored = _num(cohort.get("scored"))
        if scored is not None and scored > 0:
            regressed = _num(cohort.get("regressed_count"))
            improved = _num(cohort.get("improved_count"))
            metrics.append(
                Metric("whatifd.cohort.regression_ratio", (regressed or 0.0) / scored, ctags)
            )
            metrics.append(
                Metric("whatifd.cohort.improvement_ratio", (improved or 0.0) / scored, ctags)
            )

    findings = report.get("decision_findings") or []
    blocking = sum(1 for f in findings if str(f.get("severity", "")).startswith("blocks"))
    metrics.append(Metric("whatifd.findings.blocking", float(blocking), run_tags))
    return metrics


@dataclass(frozen=True, slots=True)
class DatadogMetricsClient:
    """Minimal agentless client for the Datadog v1 metrics intake."""

    api_key: str
    site: str = "datadoghq.com"
    timeout_seconds: float = 10.0

    def submit(self, metrics: Sequence[Metric], *, timestamp: int) -> None:
        """POST `metrics` as gauges. Raises on transport/HTTP error (callers
        decide whether to soft-fail). No-op for an empty metric list."""
        if not metrics:
            return
        try:
            import httpx  # type: ignore[import-not-found,unused-ignore]
        except ImportError as exc:  # pragma: no cover - only without [live]
            raise RuntimeError(
                "whatifd-datadog's metrics emitter requires `httpx`. Install "
                "with `pip install whatifd-datadog[live]`."
            ) from exc

        body = {
            "series": [
                {
                    "metric": m.name,
                    "type": "gauge",
                    "points": [[timestamp, m.value]],
                    "tags": list(m.tags),
                }
                for m in metrics
            ]
        }
        # Use httpx's `json=` kwarg (it serializes and sets Content-Type)
        # rather than `json.dumps` — keeps `json.dumps` confined to
        # `whatifd/serialization/` per the project's banned-import discipline.
        resp = httpx.post(
            f"https://api.{self.site}{_SERIES_PATH}",
            headers={"DD-API-KEY": self.api_key},
            json=body,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()


def emit_report(
    report_path: str | Path,
    *,
    api_key: str | None,
    site: str = "datadoghq.com",
    extra_tags: Sequence[str] = (),
    timestamp: int,
    dry_run: bool = False,
) -> list[Metric]:
    """Read a report JSON, project to metrics, and (unless `dry_run`) submit.

    Returns the metrics regardless of `dry_run` so callers/tests can inspect
    them. Raises `FileNotFoundError`/`ValueError` for a missing/malformed
    report (cardinal #1 — an actionable error), and (when not dry-run and no
    `api_key`) a `RuntimeError`. Transport errors propagate; the CLI layer
    decides soft- vs strict-fail.
    """
    path = Path(report_path)
    if not path.is_file():
        raise FileNotFoundError(f"report not found: {path}")
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"report is not valid JSON: {path} ({exc})") from exc

    metrics = report_to_metrics(report, extra_tags=extra_tags)
    if dry_run:
        return metrics
    if not api_key:
        raise RuntimeError("DD_API_KEY is required to submit metrics (or pass --dry-run).")
    DatadogMetricsClient(api_key=api_key, site=site).submit(metrics, timestamp=timestamp)
    return metrics


def main(argv: Sequence[str] | None = None) -> int:
    """`whatifd-datadog-emit` console entry point. Soft-fail by default."""
    import os
    import time

    parser = argparse.ArgumentParser(
        prog="whatifd-datadog-emit",
        description="Emit whatifd verdict + cohort metrics from a ReportV01 JSON to Datadog.",
    )
    parser.add_argument(
        "report", help="Path to the whatifd ReportV01 JSON (reports/whatifd-fork-*.json)."
    )
    parser.add_argument("--site", default=os.environ.get("DD_SITE", "datadoghq.com"))
    parser.add_argument(
        "--tag",
        action="append",
        default=None,
        metavar="KEY:VALUE",
        help="Extra tag to attach to every metric (repeatable), e.g. --tag service:my-agent.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Project + print metrics; do not submit."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on emission failure. Default soft-fails (exit 0) so a "
        "metrics hiccup never blocks the verdict.",
    )
    args = parser.parse_args(argv)

    try:
        metrics = emit_report(
            args.report,
            api_key=os.environ.get("DD_API_KEY"),
            site=args.site,
            extra_tags=tuple(args.tag or ()),
            timestamp=int(time.time()),
            dry_run=args.dry_run,
        )
    # The soft-fail boundary (deliberate, not a generic swallow): ANY emission
    # problem — a missing report, a transport error, an unexpected HTTP status —
    # must not block the verdict, which is the `whatifd fork` exit code, not
    # this reporter's. `except Exception` catches emission errors while letting
    # `BaseException` (KeyboardInterrupt / SystemExit) propagate. `--strict`
    # turns this into a non-zero exit for callers that want emission to gate.
    except Exception as exc:
        msg = f"whatifd-datadog-emit: {type(exc).__name__}: {exc}"
        if args.strict:
            print(msg, file=sys.stderr)
            return 1
        print(f"{msg} (soft-fail; pass --strict to fail the step)", file=sys.stderr)
        return 0

    if args.dry_run:
        for m in metrics:
            print(f"{m.name} {m.value} {list(m.tags)}")
    else:
        print(f"whatifd-datadog-emit: submitted {len(metrics)} metrics to {args.site}")
    return 0


__all__ = [
    "VERDICT_CODE",
    "DatadogMetricsClient",
    "Metric",
    "emit_report",
    "main",
    "report_to_metrics",
]


if __name__ == "__main__":
    raise SystemExit(main())
