"""Deterministic monthly contribution, gap, and subsidy results."""

from dataclasses import dataclass

from china_pension_strategy.domain.eligibility import EligibilityStatus
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.values import Money, YearMonth


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True)
class GapResult:
    """Minimum-months requirement versus reconciled confirmed months."""

    scheme: str
    requirement_months: int
    confirmed_months: int
    remaining_months: int
    schedule: tuple[YearMonth, ...]

    def __post_init__(self) -> None:
        _require_text(self.scheme, "scheme")
        for field_name in (
            "requirement_months",
            "confirmed_months",
            "remaining_months",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DomainValidationError(
                    f"{field_name} must be a non-negative integer"
                )
        if self.remaining_months != max(self.requirement_months - self.confirmed_months, 0):
            raise DomainValidationError("remaining_months must be requirement minus confirmed")
        if not isinstance(self.schedule, tuple) or not all(
            isinstance(month, YearMonth) for month in self.schedule
        ):
            raise DomainValidationError("schedule must contain YearMonth values")
        if len(self.schedule) != self.remaining_months:
            raise DomainValidationError("schedule length must equal remaining months")


@dataclass(frozen=True)
class MonthlyContribution:
    """One month of gross contributions, subsidy, and net outflow."""

    scheme: str
    month: YearMonth
    pension: Money
    medical: Money
    unemployment: Money
    subsidy: Money
    net_outflow: Money

    def __post_init__(self) -> None:
        _require_text(self.scheme, "scheme")
        if not isinstance(self.month, YearMonth):
            raise DomainValidationError("month must be a YearMonth")
        for field_name in ("pension", "medical", "unemployment", "subsidy", "net_outflow"):
            value = getattr(self, field_name)
            if not isinstance(value, Money):
                raise DomainValidationError(f"{field_name} must be a Money value")
            if value.amount < 0:
                raise DomainValidationError(f"{field_name} cannot be negative")
        expected = (
            self.pension.amount
            + self.medical.amount
            + self.unemployment.amount
            - self.subsidy.amount
        )
        if self.net_outflow.amount != expected:
            raise DomainValidationError(
                "net_outflow must equal gross contributions minus subsidy"
            )


@dataclass(frozen=True)
class SubsidyAssessment:
    """Subsidy eligibility and, when eligible, its monthly amount and period."""

    status: EligibilityStatus
    monthly_subsidy: Money | None
    start_month: YearMonth | None
    end_month: YearMonth | None
    duration_months: int | None
    rule_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, EligibilityStatus):
            raise DomainValidationError("status must be an EligibilityStatus")
        if not isinstance(self.rule_refs, tuple) or not all(
            isinstance(ref, str) and ref.strip() for ref in self.rule_refs
        ):
            raise DomainValidationError("rule_refs must contain non-empty strings")
        if self.status is EligibilityStatus.ELIGIBLE:
            required = (
                self.monthly_subsidy,
                self.start_month,
                self.end_month,
                self.duration_months,
            )
            if not all(value is not None for value in required):
                raise DomainValidationError(
                    "ELIGIBLE subsidy requires amount, period, and duration"
                )
            if not isinstance(self.monthly_subsidy, Money):
                raise DomainValidationError("monthly_subsidy must be a Money value")
            if not isinstance(self.duration_months, int) or self.duration_months < 1:
                raise DomainValidationError("duration_months must be positive")
            if self.end_month < self.start_month:  # type: ignore[operator]
                raise DomainValidationError("end_month cannot precede start_month")
        elif any(
            value is not None
            for value in (
                self.monthly_subsidy,
                self.start_month,
                self.end_month,
                self.duration_months,
            )
        ):
            raise DomainValidationError(
                "non-ELIGIBLE assessments cannot carry subsidy details"
            )
