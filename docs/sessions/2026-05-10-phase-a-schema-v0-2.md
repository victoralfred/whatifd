---
session_id: 2026-05-10-phase-a-schema-v0-2
started_at: 2026-05-10T00:00:00Z
---

## Session start

**User request:** Begin v0.2 coding — Phase A (schema bump groundwork): introduce `experiment_shape` field, bump schema to v0.2, give `whatifd report-migrate` real v0.1→v0.2 logic.

**Skill files read:**
- .claude/skills/whatifd-design/SKILL.md (project guide via CLAUDE.md)
- .claude/skills/whatifd-design/references/contracts.md §"Public report schema versioning" (versioning rules, extension points, promotion path)

**Cardinal rules cited:**
- Rule #6 (public schema hand-written): `experiment_shape` added by hand to `ReportV01` and the v0.2 schema JSON — no auto-derived dict[str, Any].
- Rule #1 (failure-as-data): migrator failures (e.g. malformed v0.1 input) must produce structured errors, not exceptions.
- Rule #4 (determinism opt-in): `experiment_shape` is part of the deterministic subset (config-derived).

**Clarifying questions asked:**
- Schema bump strategy (immediate v0.2 vs additive-only vs split-PR). User selected: immediate v0.2.

**Phase plan position (per references/phases.md and v0.2-roadmap.md):**
- Phase: A — Schema bump groundwork (v0.1 → v0.2)
- Sub-item: A.1 introduce experiment_shape + freeze v0.1 schema + create v0.2 schema + migrator
- Prerequisites status: v0.1.0 shipped on PyPI; main is clean; cardinal rules unbroken.

## Session end

**Artifacts produced:**
- `src/whatifd/types/manifest.py`: added `ExperimentShape` literal and threaded `experiment_shape: ExperimentShape = "failure_rescue"` field onto `RunManifest`.
- `src/whatifd/report/models_v01.py`: bumped `REPORT_SCHEMA_VERSION` → `"0.2"`, `REPORT_SCHEMA_URI` → `https://whatif.codes/schema/report/v0.2.json`; added required top-level `experiment_shape` to `ReportV01`.
- `src/whatifd/report/projection.py`: projects `runtime.experiment_shape` to top-level on `ReportV01`.
- `src/whatifd/report/migrate.py` (new): `migrate_report` dispatcher + `_migrate_v0_1_to_v0_2` + `MigrationError` typed exception.
- `src/whatifd/report/schema/v0.2.schema.json` (new, generated): the published v0.2 wire schema.
- `src/whatifd/report/schema/v0.1.schema.json`: byte-frozen (pinned by sha256 test).
- `src/whatifd/serialization/determinism.py`: loads schema by current `REPORT_SCHEMA_VERSION`.
- `src/whatifd/cli.py`: `report-migrate` subcommand replaced with real logic; uses `canonical_json_bytes` for the artifact write (cardinal #5 boundary).
- `scripts/generate_schema.py`: filename derived from current schema version.
- Tests: `test_migrate.py` (new, 8 tests), `test_schema_v0_1_frozen.py` (new, 3 tests). Updated `test_models_v01.py`, `test_schema.py`, `test_cli.py`, `test_encoder.py`, `test_determinism.py` for the v0.2 shape.
- `CHANGELOG.md`: Phase A entry under [Unreleased].
- `docs/sessions/2026-05-10-phase-a-schema-v0-2.md`: this file.

**Cascade catalog items:**
- Resolved: "Phase A v0.2 schema groundwork — experiment_shape + frozen v0.1 + real report-migrate" — added 2026-05-10 in `references/cascade-catalog.md` under "Resolved cascades", documenting the rippled invariants (v0.1 schema sha256 freeze, schema-gen filename derivation, `_MIGRATIONS` dispatcher with chain-integrity guard, dict-vs-typed boundary placement, `experiment_shape` deterministic-subset placement, `load_report_json` mirroring `canonical_json_bytes`).

**Gaps surfaced:**
- The `whatifd report-migrate` CLI uses `canonical_json_bytes` which is compact (no indentation). For human consumers, an indented variant would be friendlier — file as a follow-up cascade if any operator complains.
- Stale-install state of the workspace venv (`whatifd-langfuse==0.1.0rc2`) was caught and resolved by `uv sync --extra dev --all-packages`. Worth documenting as a setup-recovery note.

**Doctrine moments:**
- Asked whether to bump v0.2 immediately vs additive-only on v0.1; user picked immediate v0.2. This locks in the v0.1 schema as a frozen artifact, which is the cardinal #6 doctrine: published schemas are immutable contracts.
- Considered putting `experiment_shape` directly on `RunManifest` (config-derived, conceptually manifest-y) but moved the canonical wire copy to `ReportV01` top-level so consumers don't have to descend into `runtime` (which is non-deterministic per cardinal #4). Manifest carries it for audit; projection copies it up.
- The migrator operates on `dict[str, Any]` (not on typed `ReportV01`) because a v0.1 dict is missing the v0.2-required `experiment_shape` field — instantiating the typed dataclass would fail before the migration could inject it. Keeps the cardinal #6 boundary clean.

**Notes for the next session:**
- Phase B (config-loaded `score_fn`) is the next biggest user-facing unlock. Closes the v0.1 setup-failure error.
- Cascade-catalog Phase A entry to add: `experiment_shape` introduced; v0.2 schema now the canonical; v0.1 schema frozen by sha256.
- Remember: `uv sync --extra dev --all-packages` after any branch switch in this workspace, not bare `uv sync`.
