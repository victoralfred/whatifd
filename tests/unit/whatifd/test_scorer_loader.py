"""Tests for `whatifd.scorer_loader` — Phase B."""

from __future__ import annotations

import pytest

from whatifd.scorer_loader import ScorerLoadError, load_score_fn


class TestHappyPath:
    def test_resolves_python_module_attr(self) -> None:
        # `builtins:len` is a guaranteed-callable stand-in; the
        # loader's contract is "callable resolution," not "Inspect
        # AI score-fn shape."
        fn = load_score_fn("python:builtins:len")
        assert fn is len

    def test_returns_attribute_not_module(self) -> None:
        # Defends against a loader bug returning `module` instead of
        # `getattr(module, attr)`. The two assertions are needed
        # together: `fn is json.dumps` would pass even if `json` were
        # somehow returned (because `getattr` resolves at access
        # time), so we also assert `fn is not json` to pin the
        # attribute-vs-module distinction structurally.
        import json
        import types

        fn = load_score_fn("python:json:dumps")
        assert fn is json.dumps
        assert fn is not json
        assert not isinstance(fn, types.ModuleType)


class TestStructuralErrors:
    def test_empty_reference(self) -> None:
        with pytest.raises(ScorerLoadError, match="non-empty string"):
            load_score_fn("")

    def test_non_string_reference(self) -> None:
        with pytest.raises(ScorerLoadError, match="non-empty string"):
            load_score_fn(None)  # type: ignore[arg-type]

    def test_missing_python_prefix(self) -> None:
        with pytest.raises(ScorerLoadError, match="unsupported scheme"):
            load_score_fn("builtins:len")

    def test_extra_colon_separators(self) -> None:
        with pytest.raises(ScorerLoadError, match="malformed"):
            load_score_fn("python:builtins:len:extra")

    def test_no_colon_after_prefix(self) -> None:
        with pytest.raises(ScorerLoadError, match="malformed"):
            load_score_fn("python:builtins")

    def test_empty_module_path(self) -> None:
        with pytest.raises(ScorerLoadError, match="missing the module path"):
            load_score_fn("python::len")

    def test_empty_attr(self) -> None:
        with pytest.raises(ScorerLoadError, match="missing the attribute name"):
            load_score_fn("python:builtins:")


class TestImportFailures:
    def test_unimportable_module(self) -> None:
        with pytest.raises(ScorerLoadError, match="could not be imported"):
            load_score_fn("python:nonexistent_pkg_xyz_999:fn")

    def test_missing_attribute(self) -> None:
        with pytest.raises(ScorerLoadError, match="has no attribute"):
            load_score_fn("python:builtins:does_not_exist_xyz")

    def test_resolved_attribute_not_callable(self) -> None:
        # `sys.version` is a string, not callable.
        with pytest.raises(ScorerLoadError, match="is not callable"):
            load_score_fn("python:sys:version")
