"""FLOOR_DIVIDE and POWER operator tests (benefit estimation prerequisites)."""

import math
from decimal import Decimal, localcontext

import pytest

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.application.calculate_months import (
    evaluate_expression,
)


def expr(operator, operands, value_type="DECIMAL"):
    return {
        "kind": "EXPRESSION",
        "operator": operator,
        "value_type": value_type,
        "operands": operands,
    }


def lit(value, value_type="DECIMAL"):
    return {"kind": "LITERAL", "value_type": value_type, "value": value}


def test_floor_divide_positive() -> None:
    result = evaluate_expression(
        expr("FLOOR_DIVIDE", [lit("7"), lit("4")], "INTEGER"), {}, {}
    )
    assert result == 1
    result = evaluate_expression(
        expr("FLOOR_DIVIDE", [lit("1"), lit("4")], "INTEGER"), {}, {}
    )
    assert result == 0


def test_floor_divide_negative_floor_semantics() -> None:
    # Python // semantics: floor, not truncation.
    assert evaluate_expression(
        expr("FLOOR_DIVIDE", [lit("-1"), lit("4")], "INTEGER"), {}, {}
    ) == -1
    assert evaluate_expression(
        expr("FLOOR_DIVIDE", [lit("-5"), lit("2")], "INTEGER"), {}, {}
    ) == -3


def test_floor_divide_decimal_operands() -> None:
    result = evaluate_expression(
        expr("FLOOR_DIVIDE", [lit("7.5"), lit("2.0")], "INTEGER"), {}, {}
    )
    assert result == 3


def test_floor_divide_by_zero_rejected() -> None:
    with pytest.raises(DomainValidationError):
        evaluate_expression(expr("FLOOR_DIVIDE", [lit("7"), lit("0")], "INTEGER"), {}, {})


def test_floor_divide_non_numeric_rejected() -> None:
    with pytest.raises(DomainValidationError):
        evaluate_expression(expr("FLOOR_DIVIDE", [lit("x", "STRING"), lit("2")], "INTEGER"), {}, {})


def test_power_basic() -> None:
    result = evaluate_expression(expr("POWER", [lit("1.05"), lit("2")]), {}, {})
    assert result == Decimal("1.1025")


def test_power_monthly_compounding() -> None:
    # (1 + 0.0262/12)^12
    result = evaluate_expression(
        expr("POWER", [expr("ADD", [lit("1.0"), expr("DIVIDE", [lit("0.0262"), lit("12.0")])]), lit("12")]),
        {},
        {},
    )
    with localcontext() as context:
        context.prec = 40
        expected = (Decimal("1.0") + Decimal("0.0262") / Decimal("12.0")) ** Decimal("12")
    assert abs(result - expected) < Decimal("1e-10")


def test_power_negative_exponent_rejected() -> None:
    with pytest.raises(DomainValidationError):
        evaluate_expression(expr("POWER", [lit("2.0"), lit("-1")]), {}, {})


def test_power_invalid_operand_rejected() -> None:
    with pytest.raises(DomainValidationError):
        evaluate_expression(expr("POWER", [lit("x", "STRING"), lit("2")]), {}, {})
