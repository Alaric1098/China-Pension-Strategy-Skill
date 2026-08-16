"""Statutory retirement derivation tests (progressive delayed retirement)."""

import pytest

from china_pension_strategy.domain.retirement import (
    statutory_retirement,
)
from china_pension_strategy.domain.values import YearMonth


def ym(y: int, m: int) -> YearMonth:
    return YearMonth(y, m)


def test_male_first_cohort_no_delay() -> None:
    # Born 1965-01, reaches 60 at 2025-01 = delay start -> no delay.
    s = statutory_retirement(ym(1965, 1), "male", 60)
    assert s.statutory == ym(2025, 1)
    assert s.delay_months == 0


def test_male_every_four_birth_months_plus_one_delay() -> None:
    # Born 1965-05, reaches 60 at 2025-05; elapsed 4 -> +1 month.
    s = statutory_retirement(ym(1965, 5), "male", 60)
    assert s.delay_months == 1
    assert s.statutory == ym(2025, 6)
    # Born 1965-09, reaches 60 at 2025-09; elapsed 8 -> +2 months.
    s2 = statutory_retirement(ym(1965, 9), "male", 60)
    assert s2.delay_months == 2
    assert s2.statutory == ym(2025, 11)


def test_male_cap_at_63() -> None:
    # Born 1977-01, reaches 60 at 2037-01; elapsed 144 -> cap 36 months.
    s = statutory_retirement(ym(1977, 1), "male", 60)
    assert s.delay_months == 36
    assert s.statutory == ym(2040, 1)
    # Later births stay at 63.
    s2 = statutory_retirement(ym(1990, 6), "male", 60)
    assert s2.statutory == ym(2053, 6)


def test_female_50_every_two_birth_months() -> None:
    # Born 1975-01, reaches 50 at 2025-01 -> no delay.
    assert statutory_retirement(ym(1975, 1), "female", 50).statutory == ym(2025, 1)
    # Born 1975-03, reaches 50 at 2025-03; elapsed 2 -> +1 month.
    s = statutory_retirement(ym(1975, 3), "female", 50)
    assert s.delay_months == 1
    assert s.statutory == ym(2025, 4)
    # Cap at 55: born 1985-01 -> reaches 50 at 2035-01; elapsed 120 -> cap 60.
    s2 = statutory_retirement(ym(1985, 1), "female", 50)
    assert s2.delay_months == 60
    assert s2.statutory == ym(2040, 1)


def test_female_55_pace_four_target_58() -> None:
    # Born 1970-01, reaches 55 at 2025-01 -> no delay.
    assert statutory_retirement(ym(1970, 1), "female", 55).statutory == ym(2025, 1)
    # Born 1970-05 -> reaches 55 at 2025-05; elapsed 4 -> +1 -> 2025-06.
    s = statutory_retirement(ym(1970, 5), "female", 55)
    assert s.delay_months == 1
    assert s.statutory == ym(2025, 6)


def test_elastic_windows() -> None:
    s = statutory_retirement(ym(1966, 1), "male", 60)  # 2026-01, delay 3 -> 2026-04
    assert s.statutory == ym(2026, 4)
    # Early window: at most 3 years earlier but never below original 60 (2026-01).
    assert s.elastic_early_window == (ym(2026, 1), ym(2026, 4))
    assert s.elastic_delay_window == (ym(2026, 4), ym(2029, 4))
    # A late-born male's early window can go 3 years below statutory.
    s2 = statutory_retirement(ym(1980, 1), "male", 60)  # statutory 2043-01
    assert s2.elastic_early_window == (ym(2040, 1), ym(2043, 1))


def test_unsupported_category_raises() -> None:
    with pytest.raises(ValueError):
        statutory_retirement(ym(1965, 1), "male", 55)
    with pytest.raises(ValueError):
        statutory_retirement(ym(1965, 1), "other", 60)
