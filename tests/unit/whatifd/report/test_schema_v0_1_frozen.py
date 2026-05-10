"""v0.1.schema.json is FROZEN — Phase A invariant.

Once a schema version is published to consumers, the file at that
version path must never change. New fields, renames, or any structural
edits go into a NEW versioned schema file (v0.2, v0.3, ...). v0.1
reports must continue to validate against the v0.1 schema in
perpetuity.

This test pins the v0.1 file's content hash. If a future contributor
edits `v0.1.schema.json` directly (vs creating `v0.X.schema.json`),
this test fails with a clear message about the doctrine.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_V0_1_SCHEMA = _REPO_ROOT / "src" / "whatifd" / "report" / "schema" / "v0.1.schema.json"

# SHA-256 of the v0.1 schema file as published with the v0.1.0 release.
# Only update this hash if v0.1 itself is being intentionally amended
# during the v0.1.x patch window — and a patch must be additive in the
# JSON-Schema-non-semantic sense (description text, examples). Any
# structural change requires a new vX.Y.schema.json file, not an edit.
_V0_1_SHA256 = "f35cf7e3623cfabc879d8fdfa30182597dae076a3f8c9b6c54cb1153d5e40bf9"


def test_v0_1_schema_file_is_frozen() -> None:
    """The v0.1 schema file is byte-frozen. Edits go to a new version."""
    raw = _V0_1_SCHEMA.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    assert actual == _V0_1_SHA256, (
        f"v0.1.schema.json was modified (sha256={actual}). v0.1 is "
        f"published; structural edits must land in a new v0.X.schema.json. "
        f"If this is an intentional patch within v0.1.x's lifetime, "
        f"update _V0_1_SHA256 in this test with explicit justification."
    )


def test_v0_1_schema_id_unchanged() -> None:
    """The v0.1 $id URL is the published consumer contract."""
    schema = json.loads(_V0_1_SCHEMA.read_text(encoding="utf-8"))
    assert schema["$id"] == "https://whatif.codes/schema/report/v0.1.json"
    assert schema["schema_version"] == "0.1"


def test_v0_1_lacks_experiment_shape() -> None:
    """Sanity: v0.1 truly does not have the v0.2-only experiment_shape
    field. Defends against an accidental edit that would silently merge
    the v0.2 shape into the v0.1 file."""
    schema = json.loads(_V0_1_SCHEMA.read_text(encoding="utf-8"))
    assert "experiment_shape" not in schema["properties"]
    assert "experiment_shape" not in schema["required"]
