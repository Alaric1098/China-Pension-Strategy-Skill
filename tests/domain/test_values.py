from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, ROUND_CEILING, Rounded, localcontext

import pytest
from hypothesis import given
from hypothesis import strategies as st

from china_pension_strategy.domain.errors import (
    CurrencyMismatchError,
    DomainValidationError,
)
from china_pension_strategy.domain.values import (
    Money,
    RoundingMode,
    YearMonth,
    YearMonthRange,
)


def test_year_month_has_canonical_text_and_calendar_ordering() -> None:
    january = YearMonth(2026, 1)

    assert str(january) == "2026-01"
    assert january < YearMonth(2026, 2)


@pytest.mark.parametrize(
    "year, month", [(0, 1), (10_000, 1), (2026, 0), (2026, 13)]
)
def test_year_month_rejects_invalid_calendar_values(year: int, month: int) -> None:
    with pytest.raises(DomainValidationError):
        YearMonth(year, month)


def test_closed_year_month_range_counts_both_endpoints() -> None:
    period = YearMonthRange(YearMonth(2025, 12), YearMonth(2026, 2))

    assert period.month_count == 3
    assert tuple(period) == (
        YearMonth(2025, 12),
        YearMonth(2026, 1),
        YearMonth(2026, 2),
    )


def test_year_month_range_rejects_end_before_start() -> None:
    with pytest.raises(DomainValidationError, match="end"):
        YearMonthRange(YearMonth(2026, 2), YearMonth(2026, 1))


@given(
    start_index=st.integers(min_value=12, max_value=117_588),
    first_extension=st.integers(min_value=0, max_value=1_200),
    second_extension=st.integers(min_value=0, max_value=1_200),
)
def test_inclusive_month_count_is_monotonic_when_end_is_extended(
    start_index: int, first_extension: int, second_extension: int
) -> None:
    start = YearMonth(start_index // 12, start_index % 12 + 1)
    nearer_end = start.add_months(first_extension)
    farther_end = nearer_end.add_months(second_extension)

    nearer_count = YearMonthRange(start, nearer_end).month_count
    farther_count = YearMonthRange(start, farther_end).month_count

    assert farther_count >= nearer_count
    assert farther_count - nearer_count == second_extension


@given(
    year=st.integers(min_value=1, max_value=9_999),
    month=st.integers(min_value=1, max_value=12),
)
def test_year_month_serialization_is_canonical_four_digit_text(
    year: int, month: int
) -> None:
    serialized = str(YearMonth(year, month))

    assert serialized == f"{year:04d}-{month:02d}"
    assert len(serialized) == 7


def test_money_requires_decimal_and_explicit_rounding() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        Money(12.345, "CNY")  # type: ignore[arg-type]

    amount = Money(Decimal("12.345"), "CNY")

    assert amount.quantize(
        Decimal("0.01"), RoundingMode.HALF_UP
    ) == Money(Decimal("12.35"), "CNY")
    assert amount.quantize(
        Decimal("0.01"), RoundingMode.DOWN
    ) == Money(Decimal("12.34"), "CNY")


@pytest.mark.parametrize(
    "unit, expected",
    [
        (Decimal("1"), Decimal("12")),
        (Decimal("0.1"), Decimal("12.3")),
        (Decimal("0.01"), Decimal("12.35")),
    ],
)
def test_money_accepts_power_of_ten_rounding_units(
    unit: Decimal, expected: Decimal
) -> None:
    amount = Money(Decimal("12.345"), "CNY")

    assert amount.quantize(unit, RoundingMode.HALF_UP).amount == expected


def test_money_rejects_non_power_of_ten_rounding_unit() -> None:
    amount = Money(Decimal("12.345"), "CNY")

    with pytest.raises(DomainValidationError, match="power of ten"):
        amount.quantize(Decimal("0.05"), RoundingMode.HALF_UP)


@pytest.mark.parametrize(
    "canonical, equivalent",
    [
        (Decimal("0.1"), Decimal("0.10")),
        (Decimal("1"), Decimal("1.0")),
    ],
)
def test_money_normalizes_equivalent_power_of_ten_units(
    canonical: Decimal, equivalent: Decimal
) -> None:
    amount = Money(Decimal("12.345"), "CNY")

    assert amount.quantize(
        equivalent, RoundingMode.HALF_UP
    ) == amount.quantize(canonical, RoundingMode.HALF_UP)


def test_money_arithmetic_preserves_currency_and_rejects_mismatch() -> None:
    assert Money(Decimal("10.00"), "CNY") + Money(
        Decimal("2.25"), "CNY"
    ) == Money(Decimal("12.25"), "CNY")

    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("10.00"), "CNY") + Money(Decimal("2.25"), "USD")


def test_money_arithmetic_is_independent_of_ambient_decimal_context() -> None:
    left = Money(Decimal("123456789.123456789"), "CNY")
    right = Money(Decimal("0.000000001"), "CNY")

    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_CEILING

        assert left + right == Money(Decimal("123456789.123456790"), "CNY")
        assert left - right == Money(Decimal("123456789.123456788"), "CNY")
        assert Money(Decimal("10"), "CNY") - Money(
            Decimal("0.123456789"), "CNY"
        ) == Money(Decimal("9.876543211"), "CNY")


def test_money_quantize_is_independent_of_ambient_decimal_context() -> None:
    amount = Money(Decimal("123456789.125"), "CNY")

    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_CEILING

        assert amount.quantize(
            Decimal("0.01"), RoundingMode.HALF_UP
        ) == Money(Decimal("123456789.13"), "CNY")


def test_money_operations_do_not_inherit_ambient_decimal_traps() -> None:
    left = Money(Decimal("123456789.125"), "CNY")
    right = Money(Decimal("0.005"), "CNY")

    with localcontext() as ambient:
        ambient.prec = 2
        ambient.traps[Inexact] = True
        ambient.traps[Rounded] = True

        assert left + right == Money(Decimal("123456789.130"), "CNY")
        assert left - right == Money(Decimal("123456789.120"), "CNY")
        assert left.quantize(
            Decimal("0.01"), RoundingMode.HALF_UP
        ) == Money(Decimal("123456789.13"), "CNY")
        assert ambient.traps[Inexact] is True
        assert ambient.traps[Rounded] is True


def test_domain_values_are_frozen() -> None:
    month = YearMonth(2026, 1)
    money = Money(Decimal("1.00"), "CNY")

    with pytest.raises(FrozenInstanceError):
        month.month = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        money.amount = Decimal("2.00")  # type: ignore[misc]
