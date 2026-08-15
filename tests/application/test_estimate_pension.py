"""Pension benefit estimation application tests (Task 4)."""

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from china_pension_strategy.application.estimate_pension import (
    c_ping_for_retirement,
    derive_statutory_retirement,
    estimate_pension,
    payment_months_for_age,
    project_stored_balance,
)
from china_pension_strategy.domain.benefit import PensionEstimate
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import PolicyRule
from china_pension_strategy.domain.values import Money, YearMonth

ROOT = Path(__file__).resolve().parents[2]
CNY = "CNY"


def load_rules(package_name: str) -> tuple[PolicyRule, ...]:
    package = json.loads(
        (ROOT / "policy-data" / "packages" / f"{package_name}.json").read_text(
            encoding="utf-8"
        )
    )
    return tuple(_rule(record) for record in package["rules"])


def _convert_scalar(value_type: str, value: object) -> object:
    from china_pension_strategy.domain.values import YearMonth as YM

    if value_type == "DECIMAL":
        return Decimal(value)
    if value_type == "YEAR_MONTH":
        y, m = str(value).split("-")
        return YM(int(y), int(m))
    if value_type == "DATE":
        return date.fromisoformat(str(value))
    return value


def _convert_expression(expr: dict) -> dict:
    if expr.get("kind") == "LITERAL":
        return {**expr, "value": _convert_scalar(expr["value_type"], expr["value"])}
    if expr.get("kind") == "EXPRESSION":
        return {**expr, "operands": [_convert_expression(op) for op in expr["operands"]]}
    return expr


def _rule(record: dict) -> PolicyRule:
    from china_pension_strategy.domain.policy import (
        JurisdictionRole,
        LegalHierarchy,
        PolicyRule as PR,
        RuleType,
    )

    rule_type = RuleType(record["rule_type"])
    input_types = {decl["input_id"]: decl["value_type"] for decl in record["inputs"]}
    result_types = {r["output_field"]: r["value_type"] for r in record["results"]}
    parameters = {
        name: {**decl, "value": _convert_scalar(decl["value_type"], decl["value"])}
        for name, decl in record["parameters"].items()
    }
    conditions = tuple(
        {**c, "value": _convert_scalar(c["value_type"], c["value"])} for c in record["conditions"]
    )
    results = tuple(
        {**res, "value": _convert_expression(res["value"])} for res in record["results"]
    )
    test_vectors = tuple(
        {
            "vector_id": v["vector_id"],
            "input": {k: _convert_scalar(input_types[k], val) for k, val in v["input"].items()},
            "expected": {k: _convert_scalar(result_types[k], val) for k, val in v["expected"].items()},
        }
        for v in record["test_vectors"]
    )
    decision_rows = ()
    input_domains = None
    if rule_type is RuleType.DECISION_TABLE:
        input_domains = {
            input_id: tuple(
                _convert_scalar(input_types[input_id], val) for val in record["input_domains"][input_id]
            )
            for input_id in record["input_domains"]
        }
        decision_rows = tuple(
            {
                "row_id": row["row_id"],
                "conditions": tuple(
                    {**c, "value": _convert_scalar(c["value_type"], c["value"])} for c in row["conditions"]
                ),
                "results": tuple(
                    {**res, "value": _convert_expression(res["value"])} for res in row["results"]
                ),
            }
            for row in record["decision_rows"]
        )
    return PR(
        rule_id=record["rule_id"],
        rule_type=rule_type,
        scheme=record["scheme"],
        topic=record["topic"],
        jurisdiction_role=JurisdictionRole(record["jurisdiction_role"]),
        population_scope=record["population_scope"],
        inputs=tuple(record["inputs"]),
        conditions=conditions,
        results=results,
        exceptions=tuple(record["exceptions"]),
        effective_from=date.fromisoformat(record["effective_from"]),
        effective_to=date.fromisoformat(record["effective_to"]) if record["effective_to"] else None,
        transaction_from=datetime.fromisoformat(record["transaction_from"]),
        transaction_to=datetime.fromisoformat(record["transaction_to"]) if record["transaction_to"] else None,
        legal_hierarchy=LegalHierarchy(record["legal_hierarchy"]),
        explicit_override_refs=tuple(record["explicit_override_refs"]),
        source_refs=tuple(record["source_refs"]),
        parameters=parameters,
        test_vectors=test_vectors,
        input_domains=input_domains,
        decision_rows=decision_rows,
    )


def rules() -> tuple[PolicyRule, ...]:
    return load_rules("national-pension-benefit") + load_rules("beijing-pension-benefit")


def ym(y: int, m: int) -> YearMonth:
    return YearMonth(y, m)


def test_derive_male_first_cohort() -> None:
    s = derive_statutory_retirement(rules(), ym(1965, 1), "MALE")
    assert s.delay_months == 0
    assert s.retirement == ym(2025, 1)
    assert s.age_months == 720


def test_derive_male_1976() -> None:
    s = derive_statutory_retirement(rules(), ym(1976, 2), "MALE")
    # birth + 60y = 2036-02; elapsed 133 months from 2025-01; floor(133/4)=33
    assert s.delay_months == 33
    assert s.retirement == ym(2038, 11)
    assert s.age_months == 753


def test_derive_female_50() -> None:
    s = derive_statutory_retirement(rules(), ym(1975, 1), "FEMALE_50")
    assert s.delay_months == 0
    assert s.retirement == ym(2025, 1)


def test_payment_months_whole_years() -> None:
    assert payment_months_for_age(rules(), 60, 0) == Decimal("139")
    assert payment_months_for_age(rules(), 50, 0) == Decimal("195")
    assert payment_months_for_age(rules(), 40, 0) == Decimal("233")


def test_payment_months_interpolation() -> None:
    assert payment_months_for_age(rules(), 60, 1) == Decimal("138.4")
    assert payment_months_for_age(rules(), 50, 1) == Decimal("194.6")
    assert payment_months_for_age(rules(), 58, 1) == Decimal("151.4")
    assert payment_months_for_age(rules(), 62, 10) == Decimal("118.3")


def test_c_ping_table_and_override() -> None:
    c_ping, year = c_ping_for_retirement(rules(), 2025)
    assert c_ping.amount == Decimal("12049.00")
    assert year == 2025
    c_ping2, year2 = c_ping_for_retirement(rules(), 2038, Decimal("13000.00"))
    assert c_ping2.amount == Decimal("13000.00")
    with pytest.raises(DomainValidationError):
        c_ping_for_retirement(rules(), 2038)


def test_project_stored_balance() -> None:
    balance = Money(Decimal("100000.00"), CNY)
    stored = project_stored_balance(
        rules(), balance, ym(2026, 8), ym(2038, 11), Decimal("0.0262")
    )
    assert stored.amount > Decimal("100000.00")
    assert stored.currency == CNY


def test_estimate_pension_golden() -> None:
    estimate = estimate_pension(
        rules(),
        birth=ym(1976, 2),
        gender_category="MALE",
        total_contribution_months=360,
        average_contribution_index=Decimal("0.8"),
        account_balance=Money(Decimal("100000.00"), CNY),
        account_as_of=ym(2026, 8),
        c_ping_override=Decimal("12049.00"),
        deemed_years=Decimal("3.0"),
    )
    assert isinstance(estimate, PensionEstimate)
    assert estimate.statutory.retirement == ym(2038, 11)
    assert estimate.c_ping.amount == Decimal("12049.00")
    assert estimate.monthly_basic_pension is not None
    assert estimate.monthly_basic_pension.amount == Decimal("3253.23")
    assert estimate.monthly_transition_pension is not None
    assert estimate.monthly_transition_pension.amount == Decimal("361.47")
    assert estimate.monthly_total is not None
    assert estimate.monthly_total.amount > Decimal("4000.00")


def test_estimate_missing_c_ping_raises() -> None:
    with pytest.raises(DomainValidationError):
        estimate_pension(
            rules(),
            birth=ym(1976, 2),
            gender_category="MALE",
            total_contribution_months=360,
            average_contribution_index=Decimal("0.8"),
            account_balance=Money(Decimal("100000.00"), CNY),
            account_as_of=ym(2026, 8),
        )
