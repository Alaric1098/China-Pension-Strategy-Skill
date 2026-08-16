"""Deterministic pension benefit estimation orchestration.

Pure functions over `PolicyRule` tuples from the benefit rule packages
(national-pension-benefit, beijing-pension-benefit). Every value comes from
rule evaluation — no policy numbers are hardcoded here.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from china_pension_strategy.application.calculate_months import evaluate_rule
from china_pension_strategy.domain.benefit import (
    PensionEstimate,
    ProjectionAssumption,
    StatutoryRetirement,
)
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import PolicyRule
from china_pension_strategy.domain.values import Money, RoundingMode, YearMonth

_CENT = Decimal("0.01")
_TENTH = Decimal("0.1")

_GENDER_RULES = {
    "MALE": "national-delayed-retirement-male",
    "FEMALE_55": "national-delayed-retirement-female-55",
    "FEMALE_50": "national-delayed-retirement-female-50",
}


def _by_rule_id(rules, rule_id: str) -> PolicyRule:
    for rule in rules:
        if rule.rule_id == rule_id:
            return rule
    raise DomainValidationError(f"benefit rule not found: {rule_id}")


def _parameter(rule: PolicyRule, name: str) -> object:
    declaration = rule.parameters.get(name)
    if not isinstance(declaration, Mapping) and not hasattr(declaration, "get"):
        raise DomainValidationError(f"parameter {name} not declared on {rule.rule_id}")
    return declaration["value"]  # type: ignore[index]


def derive_statutory_retirement(
    rules: tuple[PolicyRule, ...],
    birth: YearMonth,
    gender_category: str,
) -> StatutoryRetirement:
    """Derive the statutory retirement schedule from the delay rules."""
    rule_id = _GENDER_RULES.get(gender_category)
    if rule_id is None:
        raise DomainValidationError(f"unsupported gender category {gender_category!r}")
    rule = _by_rule_id(rules, rule_id)
    outputs = evaluate_rule(rule, {"birth_year": birth.year, "birth_month": birth.month})
    if not outputs or "delay_months" not in outputs:
        raise DomainValidationError(f"delay rule {rule_id} did not produce delay_months")
    delay = cast(int, outputs["delay_months"])
    statutory_months = cast(int, _parameter(rule, "statutory_months"))
    retirement = birth.add_months(statutory_months + delay)
    return StatutoryRetirement(
        birth=birth,
        gender_category=gender_category,
        original_statutory_months=statutory_months,
        delay_months=delay,
        retirement=retirement,
    )


def payment_months_for_age(
    rules: tuple[PolicyRule, ...],
    age_years: int,
    age_months: int,
) -> Decimal:
    """Payment months for a non-integer age via linear interpolation."""
    rule = _by_rule_id(rules, "national-payment-months-table")
    lower = evaluate_rule(rule, {"age_years": age_years})
    upper = evaluate_rule(rule, {"age_years": age_years + 1})
    if not lower or not upper:
        raise DomainValidationError(
            f"payment months table missing rows for {age_years} or {age_years + 1}"
        )
    lo = Decimal(str(lower["payment_months"]))
    hi = Decimal(str(upper["payment_months"]))
    fraction = Decimal(age_months) / Decimal(12)
    value = lo - (lo - hi) * fraction
    return value.quantize(_TENTH, rounding=ROUND_HALF_UP)


def c_ping_for_retirement(
    rules: tuple[PolicyRule, ...],
    retirement_year: int,
    override: Decimal | None = None,
) -> tuple[Money, int]:
    """Resolve the pension calculation base (C平) for a retirement year."""
    if override is not None:
        return Money(override, "CNY"), retirement_year
    rule = _by_rule_id(rules, "beijing-c-ping-table")
    outputs = evaluate_rule(rule, {"retirement_year": retirement_year})
    if not outputs or "c_ping" not in outputs:
        raise DomainValidationError(f"no c_ping published for retirement year {retirement_year}")
    return Money(Decimal(str(outputs["c_ping"])), "CNY"), retirement_year


def project_stored_balance(
    rules: tuple[PolicyRule, ...],
    balance: Money,
    as_of: YearMonth,
    retirement: YearMonth,
    rate: Decimal,
) -> Money:
    """Project the personal-account balance to retirement with monthly growth."""
    months = (retirement.year - as_of.year) * 12 + (retirement.month - as_of.month)
    months = max(months, 0)
    rule = _by_rule_id(rules, "national-account-growth-formula")
    outputs = evaluate_rule(
        rule,
        {
            "balance": str(balance.amount),
            "months": str(Decimal(months)),
            "rate": str(rate),
        },
    )
    if not outputs or "stored_balance" not in outputs:
        raise DomainValidationError("account growth rule did not produce stored_balance")
    stored = Decimal(str(outputs["stored_balance"]))
    return Money(stored, "CNY").quantize(_CENT, RoundingMode.HALF_UP)


def estimate_pension(
    rules: tuple[PolicyRule, ...],
    *,
    birth: YearMonth,
    gender_category: str,
    total_contribution_months: int,
    average_contribution_index: Decimal,
    account_balance: Money,
    account_as_of: YearMonth,
    c_ping_override: Decimal | None = None,
    interest_rate_override: Decimal | None = None,
    deemed_years: Decimal | None = None,
    transition_years_98: Decimal | None = None,
) -> PensionEstimate:
    """Orchestrate a full pension estimate."""
    statutory = derive_statutory_retirement(rules, birth, gender_category)

    payment_months = payment_months_for_age(
        rules, statutory.age_months // 12, statutory.age_months % 12
    )

    c_ping, c_ping_year = c_ping_for_retirement(rules, statutory.retirement.year, c_ping_override)

    rate = interest_rate_override
    assumptions = []
    if rate is None:
        rate_rule = _by_rule_id(rules, "national-record-interest-rate")
        rate_outputs = evaluate_rule(rate_rule, {"months": 12})
        rate = Decimal(str(cast(Mapping[str, object], rate_outputs)["record_interest_rate"]))
        assumptions.append(
            ProjectionAssumption(
                name="record_interest_rate",
                value=str(rate),
                source_type="PUBLISHED",
                source_refs=tuple(rate_rule.source_refs),
                note="2025年度披露值；2026及以后为用户假设",
            )
        )
    else:
        assumptions.append(
            ProjectionAssumption(
                name="record_interest_rate", value=str(rate), source_type="OVERRIDE"
            )
        )

    stored = project_stored_balance(
        rules, account_balance, account_as_of, statutory.retirement, rate
    )

    basic = evaluate_rule(
        _by_rule_id(rules, "national-basic-pension-formula"),
        {
            "c_ping": str(c_ping.amount),
            "avg_index": str(average_contribution_index),
            "total_months": str(Decimal(total_contribution_months)),
        },
    )
    monthly_basic = (
        Money(Decimal(str(basic["monthly_basic_pension"])), "CNY").quantize(
            _CENT, RoundingMode.HALF_UP
        )
        if basic
        else None
    )

    account = evaluate_rule(
        _by_rule_id(rules, "national-personal-account-pension-formula"),
        {"stored_balance": str(stored.amount), "payment_months": str(payment_months)},
    )
    monthly_account = (
        Money(Decimal(str(account["monthly_account_pension"])), "CNY").quantize(
            _CENT, RoundingMode.HALF_UP
        )
        if account
        else None
    )

    monthly_transition = None
    if deemed_years is not None:
        try:
            transition = evaluate_rule(
                _by_rule_id(rules, "beijing-transition-pension-formula"),
                {
                    "c_ping": str(c_ping.amount),
                    "avg_index": str(average_contribution_index),
                    "deemed_years": str(deemed_years),
                    "transition_years_98": str(transition_years_98 or Decimal("0.0")),
                },
            )
            if transition:
                monthly_transition = Money(
                    Decimal(str(transition["monthly_transition_pension"])), "CNY"
                ).quantize(_CENT, RoundingMode.HALF_UP)
        except DomainValidationError:
            monthly_transition = None

    parts = [v for v in (monthly_basic, monthly_account, monthly_transition) if v is not None]
    monthly_total = (
        Money(sum((p.amount for p in parts), Decimal("0.00")), "CNY").quantize(
            _CENT, RoundingMode.HALF_UP
        )
        if parts
        else None
    )

    return PensionEstimate(
        statutory=statutory,
        payment_months=payment_months,
        c_ping=c_ping,
        c_ping_year=c_ping_year,
        record_interest_rate=rate,
        account_balance=account_balance,
        stored_balance=stored,
        monthly_basic_pension=monthly_basic,
        monthly_account_pension=monthly_account,
        monthly_transition_pension=monthly_transition,
        monthly_total=monthly_total,
        assumptions=tuple(assumptions),
    )
