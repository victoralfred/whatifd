"""Tests for `parse_decimal_string` (early-shipped Phase 5 helper)."""

from __future__ import annotations

import pytest

from whatif.exceptions import InvariantViolationError
from whatif.serialization.decimal import parse_decimal_string
from whatif.types.primitives import DecimalString


class TestParseDecimalString:
    def test_parses_positive_decimal(self) -> None:
        assert parse_decimal_string(DecimalString("0.310"), field="x") == 0.310

    def test_parses_negative_decimal(self) -> None:
        assert parse_decimal_string(DecimalString("-0.050"), field="x") == -0.050

    def test_parses_zero(self) -> None:
        assert parse_decimal_string(DecimalString("0.000"), field="x") == 0.0

    def test_parses_integer_form(self) -> None:
        # `float("42")` works fine; the contract doesn't require a decimal
        # point — DecimalString is "fixed-precision decimal string", and
        # an integer form is a valid representation of a whole number.
        assert parse_decimal_string(DecimalString("42"), field="x") == 42.0

    def test_parses_scientific_notation(self) -> None:
        # `float("1e-3")` succeeds. We don't constrain the format beyond
        # "parseable by float()" — Phase 5 may tighten this when
        # `format_decimal_string` lands and pins the canonical shape.
        assert parse_decimal_string(DecimalString("1e-3"), field="x") == 0.001


class TestParseDecimalStringRaisesOnMalformed:
    def test_raises_on_non_numeric(self) -> None:
        with pytest.raises(InvariantViolationError, match="parseable as a number"):
            parse_decimal_string(DecimalString("not-a-number"), field="x")

    def test_error_message_includes_field_label(self) -> None:
        with pytest.raises(InvariantViolationError, match=r"CohortResult\.median_delta"):
            parse_decimal_string(
                DecimalString("garbage"),
                field="CohortResult.median_delta",
            )

    def test_error_message_includes_offending_value(self) -> None:
        with pytest.raises(InvariantViolationError, match="garbage"):
            parse_decimal_string(DecimalString("garbage"), field="x")

    def test_chains_underlying_value_error(self) -> None:
        with pytest.raises(InvariantViolationError) as exc_info:
            parse_decimal_string(DecimalString("garbage"), field="x")
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_raises_on_empty_string(self) -> None:
        with pytest.raises(InvariantViolationError):
            parse_decimal_string(DecimalString(""), field="x")
