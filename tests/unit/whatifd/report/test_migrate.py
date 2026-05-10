"""Tests for `whatifd.report.migrate` — Phase A (v0.1 → v0.2)."""

from __future__ import annotations

import pytest

from whatifd.report.migrate import MigrationError, migrate_report
from whatifd.report.models_v01 import REPORT_SCHEMA_URI, REPORT_SCHEMA_VERSION


class TestV01ToV02:
    def test_injects_experiment_shape(self) -> None:
        v0_1 = {
            "schema_version": "0.1",
            "schema_uri": "https://whatif.codes/schema/report/v0.1.json",
            "verdict_state": "ship",
        }
        migrated, changed = migrate_report(v0_1)
        assert changed is True
        assert migrated["experiment_shape"] == "failure_rescue"
        assert migrated["schema_version"] == "0.2"
        assert migrated["schema_uri"] == REPORT_SCHEMA_URI

    def test_preserves_other_fields(self) -> None:
        v0_1 = {
            "schema_version": "0.1",
            "schema_uri": "https://whatif.codes/schema/report/v0.1.json",
            "verdict_state": "dont_ship",
            "cohort_results": [{"name": "failure"}],
            "failures": [],
        }
        migrated, _ = migrate_report(v0_1)
        assert migrated["verdict_state"] == "dont_ship"
        assert migrated["cohort_results"] == [{"name": "failure"}]
        assert migrated["failures"] == []


class TestIdempotence:
    def test_v0_2_is_noop(self) -> None:
        v0_2 = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "schema_uri": REPORT_SCHEMA_URI,
            "experiment_shape": "failure_rescue",
            "verdict_state": "ship",
        }
        migrated, changed = migrate_report(v0_2)
        assert changed is False
        assert migrated is v0_2  # input returned unchanged


class TestStructuralErrors:
    def test_non_dict_input(self) -> None:
        with pytest.raises(MigrationError, match="must be a JSON object"):
            migrate_report([1, 2, 3])  # type: ignore[arg-type]

    def test_missing_schema_version(self) -> None:
        with pytest.raises(MigrationError, match="missing required `schema_version`"):
            migrate_report({"verdict_state": "ship"})

    def test_non_string_schema_version(self) -> None:
        with pytest.raises(MigrationError, match="must be a string"):
            migrate_report({"schema_version": 1})

    def test_unknown_source_version(self) -> None:
        with pytest.raises(MigrationError, match="no migration path"):
            migrate_report({"schema_version": "9.9"})


class TestRoundTripThroughTypedReport:
    """Migrating a v0.1 dict and using it to construct a typed
    ReportV01 fixture would fail without the migration. This is the
    structural reason `migrate_report` operates on dict, not on the
    typed ReportV01 (cardinal #6 boundary)."""

    def test_v0_1_lacks_experiment_shape(self) -> None:
        v0_1 = {
            "schema_version": "0.1",
            "schema_uri": "https://whatif.codes/schema/report/v0.1.json",
        }
        # Pre-migration v0.1 has no experiment_shape — confirms the field
        # is genuinely a v0.2 addition, not an old field being renamed.
        assert "experiment_shape" not in v0_1
        migrated, _ = migrate_report(v0_1)
        assert "experiment_shape" in migrated
