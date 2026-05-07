"""`whatif` CLI entry point.

Phase 8.2 of the v0.1 implementation plan. Typer-based command
surface:

  - `whatif fork [--config PATH] [--profile {default|review|minimal|forensic}]`
    — main entrypoint. Loads config, runs two-affirmation,
    threads `TwoAffirmationProof` to the (Phase 4 / Phase 9)
    adapter pipeline. v0.1 8.2 ships the CLI SHELL — argument
    parsing, config load, two-affirmation, exit-code dispatch.
    The actual fork execution is gated on Phase 4 adapter
    integration; missing adapter → exit 2 with a clear setup
    message, NOT a silent fallback.
  - `whatif report-migrate` (Phase 8.5 stub)
  - `whatif cache rebuild|unlock|verify` (Phase 8.3 stubs)
  - `whatif diff <prev.json> <new.json>` (Phase 8.4 stub)

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Ship verdict |
| `1` | Don't Ship verdict |
| `2` | Inconclusive verdict, setup failure, floor violation, OR config error |

Floor violations ALWAYS produce exit 2 regardless of policy
(cardinal #2). Setup failures (missing config, validation
errors, missing forensic affirmation) also produce exit 2
because they prevent producing a verdict at all.

## Two-affirmation invocation point

`assert_two_affirmation` is called IMMEDIATELY after
`load_config` returns and BEFORE any forensic-path code runs.
The returned `TwoAffirmationProof` is threaded to downstream
code that consumes the redaction profile (Phase 8.5+ /
Phase 4 adapter). Cascade-catalog entry "CLI must enforce
two-affirmation before forensic-path code" tracks this.

## Why a thin CLI shell now

The downstream pipeline (replay → score → decision → render)
still has open dependencies on Phase 4 (adapters) and Phase 9
(integration). Shipping the CLI shell now gets the CLI surface,
exit-code semantics, and config-load flow in place; the missing
adapter integration surfaces as a typed exit-2 setup failure,
NOT as a runtime crash that bypasses cardinal #1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from whatif.config import (
    ConfigFileError,
    ForensicAffirmationError,
    assert_two_affirmation,
    format_validation_errors,
    load_config,
)

# Default config-file path. Operators override via `--config`.
_DEFAULT_CONFIG_PATH = Path("whatif.config.yaml")

# Exit codes per the cardinal-#2 / phase-8 contract.
EXIT_SHIP = 0
EXIT_DONT_SHIP = 1
EXIT_INCONCLUSIVE_OR_SETUP_FAILURE = 2

app = typer.Typer(
    name="whatif",
    help=(
        "whatif: trust-first experiment runner for LLM behavior changes. "
        "Fork production traces, replay with a proposed change, score the "
        "diff, emit a defensible Ship / Don't Ship / Inconclusive verdict."
    ),
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# `whatif fork` — main entry
# ---------------------------------------------------------------------------


@app.command()
def fork(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to the whatif config file (.yaml/.yml/.json).",
        ),
    ] = _DEFAULT_CONFIG_PATH,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help=(
                "Reporting profile override; must match the config's "
                "reporting.profile. `forensic` requires the "
                "forensic_acknowledgment block per cardinal #7."
            ),
        ),
    ] = None,
) -> None:
    """Fork production traces, replay with the proposed change, emit
    a verdict. Exit code 0 = Ship, 1 = Don't Ship, 2 = Inconclusive
    or setup failure.
    """
    try:
        cfg = load_config(config)
    except ConfigFileError as exc:
        typer.echo(f"whatif: config error: {exc}", err=True)
        raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE) from exc
    except ValidationError as exc:
        typer.echo(format_validation_errors(exc), err=True)
        raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE) from exc

    # TODO(cardinal #7): the cascade-catalog entry "CLI must enforce
    # two-affirmation before forensic-path code" pins this call as
    # the load-bearing site. The witness-token threading downstream
    # is Phase 4 / Phase 9 work.
    try:
        proof = assert_two_affirmation(cfg, cli_profile=profile)
    except ForensicAffirmationError as exc:
        typer.echo(f"whatif: {exc}", err=True)
        raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE) from exc

    # Phase 8.2 stub: the downstream pipeline (replay → score →
    # decision → render) requires Phase 4 adapter integration. Until
    # that lands, exit 2 with a clear setup-failure message rather
    # than crashing with NotImplementedError. The proof is held in a
    # local so a future contributor wiring Phase 4 sees the threading
    # surface.
    _ = proof  # downstream consumers (Phase 4+) accept this
    typer.echo(
        "whatif: fork pipeline requires Phase 4 adapter integration, "
        "which is not yet wired into the v0.1 CLI. Config and "
        "two-affirmation passed; downstream replay/score/decision/"
        "render stages are pending. See cascade-catalog entries "
        '"Replay subpackage boundary" and "Render subpackage '
        'boundary" for the remaining wiring.',
        err=True,
    )
    raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE)


# ---------------------------------------------------------------------------
# Subcommand stubs (Phase 8.3 / 8.4 / 8.5)
# ---------------------------------------------------------------------------


cache_app = typer.Typer(help="Cache management subcommands (Phase 8.3).")
app.add_typer(cache_app, name="cache")


@cache_app.command("rebuild")
def cache_rebuild(
    force: Annotated[bool, typer.Option("--force", help="Skip safety checks (Phase 8.3).")] = False,
) -> None:
    """Rebuild the scorer cache (Phase 8.3 stub)."""
    typer.echo("whatif cache rebuild: not yet implemented (Phase 8.3).", err=True)
    raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE)


@cache_app.command("unlock")
def cache_unlock() -> None:
    """Remove a stale cache lock file (Phase 8.3 stub)."""
    typer.echo("whatif cache unlock: not yet implemented (Phase 8.3).", err=True)
    raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE)


@cache_app.command("verify")
def cache_verify() -> None:
    """Verify cache-entry integrity (Phase 8.3 stub)."""
    typer.echo("whatif cache verify: not yet implemented (Phase 8.3).", err=True)
    raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE)


@app.command()
def diff(
    prev: Annotated[Path, typer.Argument(help="Previous report.json")],
    new: Annotated[Path, typer.Argument(help="New report.json")],
) -> None:
    """Compare two whatif reports (Phase 8.4 stub)."""
    typer.echo(
        f"whatif diff: not yet implemented (Phase 8.4). prev={prev}, new={new}",
        err=True,
    )
    raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE)


@app.command("report-migrate")
def report_migrate(
    report: Annotated[Path, typer.Argument(help="Report file to migrate")],
) -> None:
    """Migrate a report to the current schema (Phase 8.5 stub).

    v0.1: no schema bumps yet, so this is a no-op stub. Real
    migration logic lands in v0.2+ when v0.2 schema diverges from
    v0.1.
    """
    typer.echo(
        f"whatif report-migrate: v0.1 has no migrations to apply ({report}). Phase 8.5 stub.",
        err=True,
    )
    raise typer.Exit(code=EXIT_INCONCLUSIVE_OR_SETUP_FAILURE)


def main() -> None:
    """Console-script entry point (`pyproject.toml` declares
    `whatif = whatif.cli:main`)."""
    app()


if __name__ == "__main__":
    main()
