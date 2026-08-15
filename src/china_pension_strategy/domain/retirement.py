"""Statutory retirement age derivation for the progressive delayed retirement.

Implements the pace table from the 2024 decision (effective 2025-01-01):
- male (original 60): +1 month delay every 4 birth-month cohorts, target 63
- female (original 50): +1 month delay every 2 birth-month cohorts, target 55
- female (original 55): +1 month delay every 4 birth-month cohorts, target 58
- elastic early retirement: at most 3 years earlier, never below the original
  statutory age; elastic delay: at most 3 years (employer agreement required,
  which is outside this deterministic engine).

The pace table mirrors `policy-data/packages/national-delayed-retirement.json`
(parameters rule `national-delayed-retirement-pace`); the numbers live in the
policy data and are re-verified by `tests/policy/test_official_packages.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from china_pension_strategy.domain.values import YearMonth

DELAY_START = YearMonth(2025, 1)
# gender/original-age -> (pace months per one-month delay, target age)
PACE_TABLE: dict[str, dict[int, tuple[int, int]]] = {
    "male": {60: (4, 63)},
    "female": {50: (2, 55), 55: (4, 58)},
}
ELASTIC_EARLY_MAX_MONTHS = 36
ELASTIC_DELAY_MAX_MONTHS = 36


@dataclass(frozen=True)
class RetirementSchedule:
    original_statutory: YearMonth  # birth + original age (pre-delay)
    statutory: YearMonth  # after progressive delay
    delay_months: int
    elastic_early_window: tuple[YearMonth, YearMonth]  # earliest .. statutory
    elastic_delay_window: tuple[YearMonth, YearMonth]  # statutory .. latest


def _months_between(earlier: YearMonth, later: YearMonth) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def _add_months(ym: YearMonth, months: int) -> YearMonth:
    total = ym.year * 12 + (ym.month - 1) + months
    return YearMonth(total // 12, total % 12 + 1)


def statutory_retirement(
    birth_year_month: YearMonth,
    gender: str,
    original_retirement_age: int,
) -> RetirementSchedule:
    """Derive the statutory retirement schedule under progressive delay.

    Raises ValueError for genders/ages outside the pace table (unknown
    categories are not modeled yet, e.g. special-work retirees).
    """
    try:
        pace, target_age = PACE_TABLE[gender][original_retirement_age]
    except KeyError as error:
        raise ValueError(
            f"unsupported retirement category: gender={gender!r}, "
            f"original_age={original_retirement_age!r}"
        ) from error

    original_statutory = _add_months(birth_year_month, original_retirement_age * 12)
    if original_statutory <= DELAY_START:
        delay = 0
    else:
        elapsed = _months_between(DELAY_START, original_statutory)
        delay = min(elapsed // pace, (target_age - original_retirement_age) * 12)
    statutory = _add_months(original_statutory, delay)

    earliest = _add_months(statutory, -ELASTIC_EARLY_MAX_MONTHS)
    if earliest < original_statutory:
        earliest = original_statutory
    latest = _add_months(statutory, ELASTIC_DELAY_MAX_MONTHS)
    return RetirementSchedule(
        original_statutory=original_statutory,
        statutory=statutory,
        delay_months=delay,
        elastic_early_window=(earliest, statutory),
        elastic_delay_window=(statutory, latest),
    )
