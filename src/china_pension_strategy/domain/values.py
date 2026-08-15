"""Immutable calendar and monetary domain values."""

from dataclasses import dataclass
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    Decimal,
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    localcontext,
)
from enum import Enum
from typing import Iterator

from china_pension_strategy.domain.errors import (
    CurrencyMismatchError,
    DomainValidationError,
)


@dataclass(frozen=True, order=True)
class YearMonth:
    """A calendar month without day or timezone ambiguity."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.year, bool)
            or not isinstance(self.year, int)
            or not 1 <= self.year <= 9_999
        ):
            raise DomainValidationError("year must be an integer from 1 through 9999")
        if (
            isinstance(self.month, bool)
            or not isinstance(self.month, int)
            or not 1 <= self.month <= 12
        ):
            raise DomainValidationError("month must be an integer from 1 through 12")

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def add_months(self, months: int) -> "YearMonth":
        if isinstance(months, bool) or not isinstance(months, int):
            raise TypeError("months must be an integer")
        month_index = self.year * 12 + self.month - 1 + months
        year, zero_based_month = divmod(month_index, 12)
        if year < 1:
            raise DomainValidationError("resulting year must be positive")
        return YearMonth(year, zero_based_month + 1)


@dataclass(frozen=True)
class YearMonthRange:
    """A closed range that includes both its start and end months."""

    start: YearMonth
    end: YearMonth

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise DomainValidationError("end month cannot precede start month")

    @property
    def month_count(self) -> int:
        return (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1

    def __iter__(self) -> Iterator[YearMonth]:
        for offset in range(self.month_count):
            yield self.start.add_months(offset)


class RoundingMode(str, Enum):
    """Supported explicit Decimal rounding policies."""

    HALF_UP = ROUND_HALF_UP
    HALF_EVEN = ROUND_HALF_EVEN
    DOWN = ROUND_DOWN


@dataclass(frozen=True)
class Money:
    """A Decimal amount whose arithmetic preserves its currency."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("amount must be a Decimal")
        if not self.amount.is_finite():
            raise DomainValidationError("amount must be finite")
        if (
            not isinstance(self.currency, str)
            or len(self.currency) != 3
            or not self.currency.isalpha()
            or not self.currency.isupper()
        ):
            raise DomainValidationError("currency must be a three-letter uppercase code")

    def quantize(self, unit: Decimal, rounding: RoundingMode) -> "Money":
        if not isinstance(unit, Decimal):
            raise TypeError("unit must be a Decimal")
        if not unit.is_finite() or unit <= 0:
            raise DomainValidationError("rounding unit must be finite and positive")
        unit_parts = unit.as_tuple()
        trailing_zeros = 0
        significant_digits = unit_parts.digits
        while significant_digits[-1:] == (0,):
            significant_digits = significant_digits[:-1]
            trailing_zeros += 1
        normalized_unit = Decimal(
            (unit_parts.sign, significant_digits, unit_parts.exponent + trailing_zeros)
        )
        if normalized_unit.as_tuple().digits != (1,):
            raise DomainValidationError("rounding unit must be a power of ten")
        if not isinstance(rounding, RoundingMode):
            raise TypeError("rounding must be an explicit RoundingMode")
        amount_parts = self.amount.as_tuple()
        target_exponent = normalized_unit.as_tuple().exponent
        precision = max(
            len(amount_parts.digits)
            + max(amount_parts.exponent - target_exponent, 0),
            self.amount.adjusted() - target_exponent + 2,
            1,
        )
        with localcontext() as context:
            context.clear_traps()
            context.prec = precision
            context.Emax = MAX_EMAX
            context.Emin = MIN_EMIN
            context.clamp = 0
            result = self.amount.quantize(
                normalized_unit, rounding=rounding.value
            )
        return Money(result, self.currency)

    def __add__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self._add_exact(other.amount), self.currency)

    def __sub__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self._add_exact(other.amount.copy_negate()), self.currency)

    def _add_exact(self, other: Decimal) -> Decimal:
        left_parts = self.amount.as_tuple()
        right_parts = other.as_tuple()
        common_exponent = min(left_parts.exponent, right_parts.exponent)
        precision = max(
            len(left_parts.digits) + left_parts.exponent - common_exponent,
            len(right_parts.digits) + right_parts.exponent - common_exponent,
        ) + 1
        with localcontext() as context:
            context.clear_traps()
            context.prec = precision
            context.Emax = MAX_EMAX
            context.Emin = MIN_EMIN
            context.clamp = 0
            return self.amount + other

    def _require_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"cannot combine {self.currency} and {other.currency} amounts"
            )
