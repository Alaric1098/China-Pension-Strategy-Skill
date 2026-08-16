"""Benefit estimation domain model (frozen value objects)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from china_pension_strategy.domain.values import Money, YearMonth


@dataclass(frozen=True)
class StatutoryRetirement:
    """Statutory retirement schedule under progressive delayed retirement."""

    birth: YearMonth
    gender_category: str  # MALE | FEMALE_55 | FEMALE_50
    original_statutory_months: int
    delay_months: int
    retirement: YearMonth

    @property
    def age_months(self) -> int:
        return self.original_statutory_months + self.delay_months


@dataclass(frozen=True)
class ProjectionAssumption:
    """One recorded assumption behind an estimate (rate, c_ping, source refs)."""

    name: str
    value: object
    source_type: str  # OVERRIDE | PUBLISHED | DEFAULT
    source_refs: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class PensionEstimate:
    """Deterministic pension benefit estimate for one person at retirement."""

    statutory: StatutoryRetirement
    payment_months: Decimal
    c_ping: Money
    c_ping_year: int
    record_interest_rate: Decimal
    account_balance: Money
    stored_balance: Money
    monthly_basic_pension: Money | None = None
    monthly_account_pension: Money | None = None
    monthly_transition_pension: Money | None = None
    monthly_total: Money | None = None
    assumptions: tuple[ProjectionAssumption, ...] = ()
