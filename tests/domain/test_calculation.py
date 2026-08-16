import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from china_pension_strategy.application.calculate_months import (
    assess_subsidy,
    calculate_gap,
    choose_applicable_rules,
    evaluate_expression,
    evaluate_rule,
    gap_from_rule,
    monthly_contributions,
)
from china_pension_strategy.domain.calculation import (
    GapResult,
    MonthlyContribution,
)
from china_pension_strategy.domain.eligibility import EligibilityStatus
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import (
    JurisdictionRole,
    LegalHierarchy,
    PolicyRule,
    RuleType,
)
from china_pension_strategy.domain.values import Money, RoundingMode, YearMonth

ROOT = Path(__file__).resolve().parents[2]
CNY = "CNY"


def load_rule(package_name: str, rule_id: str) -> PolicyRule:
    package = json.loads(
        (ROOT / "policy-data" / "packages" / f"{package_name}.json").read_text(encoding="utf-8")
    )
    record = next(rule for rule in package["rules"] if rule["rule_id"] == rule_id)

    def vector(entry: dict) -> dict:
        input_types = {
            declaration["input_id"]: declaration["value_type"] for declaration in record["inputs"]
        }
        result_types = {
            declaration["output_field"]: declaration["value_type"]
            for declaration in record["results"]
        }
        return {
            "vector_id": entry["vector_id"],
            "input": {
                key: scalar(input_types[key], value) for key, value in entry["input"].items()
            },
            "expected": {
                key: scalar(result_types[key], value) for key, value in entry["expected"].items()
            },
        }

    rule_type = RuleType(record["rule_type"])
    decision_rows = ()
    input_domains = None
    if rule_type is RuleType.DECISION_TABLE:
        input_types = {
            declaration["input_id"]: declaration["value_type"] for declaration in record["inputs"]
        }
        input_domains = {
            input_id: tuple(scalar(input_types[input_id], value) for value in values)
            for input_id, values in record["input_domains"].items()
        }
        decision_rows = tuple(
            {
                "row_id": row["row_id"],
                "conditions": tuple(condition(cond) for cond in row["conditions"]),
                "results": tuple(result(entry) for entry in row["results"]),
            }
            for row in record["decision_rows"]
        )
    return PolicyRule(
        rule_id=record["rule_id"],
        rule_type=rule_type,
        scheme=record["scheme"],
        topic=record["topic"],
        jurisdiction_role=JurisdictionRole(record["jurisdiction_role"]),
        population_scope=record["population_scope"],
        inputs=tuple(record["inputs"]),
        conditions=tuple(condition(cond) for cond in record["conditions"]),
        results=tuple(result(entry) for entry in record["results"]),
        exceptions=tuple(record["exceptions"]),
        effective_from=date.fromisoformat(record["effective_from"]),
        effective_to=date.fromisoformat(record["effective_to"]) if record["effective_to"] else None,
        transaction_from=datetime.fromisoformat(record["transaction_from"]),
        transaction_to=datetime.fromisoformat(record["transaction_to"])
        if record["transaction_to"]
        else None,
        legal_hierarchy=LegalHierarchy(record["legal_hierarchy"]),
        explicit_override_refs=tuple(record["explicit_override_refs"]),
        source_refs=tuple(record["source_refs"]),
        parameters={
            name: {**decl, "value": scalar(decl["value_type"], decl["value"])}
            for name, decl in record["parameters"].items()
        },
        test_vectors=tuple(vector(entry) for entry in record["test_vectors"]),
        input_domains=input_domains,
        decision_rows=decision_rows,
    )


def money(amount: str) -> Money:
    return Money(Decimal(amount), CNY)


def scalar(value_type: object, value: object) -> object:
    if value_type == "DECIMAL":
        return Decimal(str(value))
    if value_type == "YEAR_MONTH":
        year, month = str(value).split("-")
        return YearMonth(int(year), int(month))
    return value


def expression(ast: dict) -> dict:
    if ast.get("kind") == "LITERAL":
        return {**ast, "value": scalar(ast["value_type"], ast["value"])}
    if ast.get("kind") == "EXPRESSION":
        return {
            **ast,
            "operands": [expression(operand) for operand in ast["operands"]],
        }
    return ast


def condition(cond: dict) -> dict:
    return {**cond, "value": scalar(cond["value_type"], cond["value"])}


def result(entry: dict) -> dict:
    return {**entry, "value": expression(entry["value"])}


def sample_value(value_type: str) -> object:
    if value_type == "DECIMAL":
        return Decimal("1.00")
    if value_type == "INTEGER":
        return 1
    if value_type == "BOOLEAN":
        return True
    if value_type == "YEAR_MONTH":
        return YearMonth(2026, 1)
    if value_type == "DATE":
        return date(2026, 1, 1)
    if value_type == "STRING":
        return "sample"
    if value_type == "NULL":
        return None
    raise ValueError(f"unsupported value_type {value_type}")


def synthetic_rule(
    rule_id: str = "synthetic-rule",
    rule_type: RuleType = RuleType.POLICY_RULE,
    effective_from: date = date(2026, 1, 1),
    effective_to: date | None = None,
    inputs: tuple[dict, ...] = ({"input_id": "x", "value_type": "DECIMAL", "required": True},),
    conditions: tuple[dict, ...] = (
        {
            "condition_id": "positive",
            "input_ref": "x",
            "operator": ">",
            "value_type": "DECIMAL",
            "value": "0.00",
        },
    ),
    results: tuple[dict, ...] = (
        {
            "result_id": "double",
            "output_field": "y",
            "value_type": "DECIMAL",
            "value": {
                "kind": "EXPRESSION",
                "operator": "MULTIPLY",
                "value_type": "DECIMAL",
                "operands": [
                    {
                        "kind": "REFERENCE",
                        "reference_type": "INPUT",
                        "reference_id": "x",
                        "value_type": "DECIMAL",
                    },
                    {"kind": "LITERAL", "value_type": "DECIMAL", "value": "2.00"},
                ],
            },
        },
    ),
    parameters: dict | None = None,
    test_vectors: tuple[dict, ...] | None = None,
) -> PolicyRule:
    if test_vectors is None:
        input_values = {
            declaration["input_id"]: sample_value(declaration["value_type"])
            for declaration in inputs
        }
        expected = {entry["output_field"]: sample_value(entry["value_type"]) for entry in results}
        test_vectors = ({"vector_id": f"v-{rule_id}", "input": input_values, "expected": expected},)
    return PolicyRule(
        rule_id=rule_id,
        rule_type=rule_type,
        scheme="enterprise_employee_basic_pension",
        topic="test_topic",
        jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
        population_scope="test population",
        inputs=inputs,
        conditions=tuple(condition(cond) for cond in conditions),
        results=tuple(result(entry) for entry in results),
        exceptions=(),
        effective_from=effective_from,
        effective_to=effective_to,
        transaction_from=datetime(2026, 8, 11, tzinfo=UTC),
        transaction_to=None,
        legal_hierarchy=LegalHierarchy.MUNICIPAL_REGULATION,
        explicit_override_refs=(),
        source_refs=("source-a",),
        parameters={
            name: {**decl, "value": scalar(decl["value_type"], decl["value"])}
            for name, decl in (parameters or {}).items()
        },
        test_vectors=test_vectors,
    )


def test_gap_179_to_180_requires_one_month() -> None:
    result = calculate_gap("enterprise_employee_basic_pension", 180, 179, YearMonth(2026, 9))
    assert result.remaining_months == 1
    assert result.schedule == (YearMonth(2026, 9),)


def test_gap_180_closed() -> None:
    result = calculate_gap("enterprise_employee_basic_pension", 180, 180, YearMonth(2026, 9))
    assert result.remaining_months == 0
    assert result.schedule == ()


def test_gap_181_exceeds_requirement() -> None:
    result = calculate_gap("enterprise_employee_basic_pension", 180, 181, YearMonth(2026, 9))
    assert result.remaining_months == 0
    assert result.confirmed_months == 181


def test_gap_schedule_is_contiguous_from_as_of() -> None:
    result = calculate_gap("enterprise_employee_basic_pension", 183, 180, YearMonth(2026, 8))
    assert result.schedule == (
        YearMonth(2026, 8),
        YearMonth(2026, 9),
        YearMonth(2026, 10),
    )


def test_gap_result_validates_remaining_months() -> None:
    with pytest.raises(DomainValidationError):
        GapResult(
            scheme="enterprise_employee_basic_pension",
            requirement_months=180,
            confirmed_months=179,
            remaining_months=2,
            schedule=(YearMonth(2026, 9),),
        )
    with pytest.raises(DomainValidationError):
        calculate_gap("enterprise_employee_basic_pension", 180, -1, YearMonth(2026, 9))


def test_expression_evaluates_literal_reference_and_operators() -> None:
    parameters = {"rate": Decimal("0.20")}
    assert evaluate_expression(
        {"kind": "LITERAL", "value_type": "DECIMAL", "value": "7.50"}, {}, parameters
    ) == Decimal("7.50")
    assert evaluate_expression(
        {
            "kind": "REFERENCE",
            "reference_type": "PARAMETER",
            "reference_id": "rate",
            "value_type": "DECIMAL",
        },
        {},
        parameters,
    ) == Decimal("0.20")
    expression = {
        "kind": "EXPRESSION",
        "operator": "ADD",
        "value_type": "DECIMAL",
        "operands": [
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": "1.00"},
            {
                "kind": "EXPRESSION",
                "operator": "MULTIPLY",
                "value_type": "DECIMAL",
                "operands": [
                    {"kind": "LITERAL", "value_type": "DECIMAL", "value": "2.00"},
                    {"kind": "LITERAL", "value_type": "DECIMAL", "value": "3.00"},
                ],
            },
        ],
    }
    assert evaluate_expression(expression, {}, parameters) == Decimal("7.00")


def test_expression_min_max_and_divide() -> None:
    min_ast = {
        "kind": "EXPRESSION",
        "operator": "MIN",
        "value_type": "DECIMAL",
        "operands": [
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": "5.00"},
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": "3.00"},
        ],
    }
    assert evaluate_expression(min_ast, {}, {}) == Decimal("3.00")
    divide_ast = {
        "kind": "EXPRESSION",
        "operator": "DIVIDE",
        "value_type": "DECIMAL",
        "operands": [
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": "6.00"},
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": "4.00"},
        ],
    }
    assert evaluate_expression(divide_ast, {}, {}) == Decimal("1.50")
    zero_divide = {
        "kind": "EXPRESSION",
        "operator": "DIVIDE",
        "value_type": "DECIMAL",
        "operands": [
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": "6.00"},
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": "0.00"},
        ],
    }
    with pytest.raises(DomainValidationError):
        evaluate_expression(zero_divide, {}, {})


def test_real_beijing_pension_contribution_formula() -> None:
    rule = load_rule("beijing-flex-employment", "beijing-flex-pension-contribution")
    outputs = evaluate_rule(rule, {"contribution_base": Decimal("7000.00")})
    assert outputs is not None
    assert outputs["monthly_pension_contribution"] == Decimal("1400.00")


def test_real_beijing_unemployment_and_medical_formula() -> None:
    unemployment = load_rule("beijing-flex-employment", "beijing-flex-unemployment-contribution")
    medical = load_rule("beijing-flex-employment", "beijing-flex-medical-contribution")
    outputs = evaluate_rule(unemployment, {"contribution_base": Decimal("7000.00")})
    assert outputs["monthly_unemployment_contribution"] == Decimal("70.00")
    outputs = evaluate_rule(medical, {"contribution_base": Decimal("7000.00")})
    assert outputs["monthly_medical_contribution"] == Decimal("584.92")


def test_real_beijing_base_limits_table() -> None:
    rule = load_rule("beijing-flex-employment", "beijing-flex-base-limits")
    assert evaluate_rule(rule, {"contribution_base": Decimal("7162.00")}) is not None
    assert evaluate_rule(rule, {"contribution_base": Decimal("35811.00")}) is not None
    assert evaluate_rule(rule, {"contribution_base": Decimal("7161.00")}) is None
    assert evaluate_rule(rule, {"contribution_base": Decimal("35812.00")}) is None


def test_monthly_contributions_round_to_cent_half_up() -> None:
    rules = (
        load_rule("beijing-flex-employment", "beijing-flex-pension-contribution"),
        load_rule("beijing-flex-employment", "beijing-flex-medical-contribution"),
        load_rule("beijing-flex-employment", "beijing-flex-unemployment-contribution"),
    )
    months = (YearMonth(2026, 9), YearMonth(2026, 10))
    schedule = monthly_contributions(rules, Decimal("7000.00"), months, RoundingMode.HALF_UP)
    assert len(schedule) == 2
    first = schedule[0]
    assert first.pension == money("1400.00")
    assert first.medical == money("584.92")
    assert first.unemployment == money("70.00")
    assert first.subsidy == money("0.00")
    assert first.net_outflow == money("2054.92")
    assert first.month == YearMonth(2026, 9)
    assert schedule[1].month == YearMonth(2026, 10)


def test_monthly_contributions_require_pension_field() -> None:
    # Pension is mandatory; medical/unemployment are optional and default to
    # zero so regions without those coverages (e.g. Shanghai) still run.
    rules = (load_rule("shanghai-flex-employment", "shanghai-flex-pension-contribution"),)
    schedule = monthly_contributions(
        rules, Decimal("7460.00"), (YearMonth(2026, 9),), RoundingMode.HALF_UP
    )
    assert schedule[0].pension == money("1492.00")
    assert schedule[0].medical == money("0.00")
    assert schedule[0].unemployment == money("0.00")


def test_monthly_contribution_net_outflow_invariant() -> None:
    with pytest.raises(DomainValidationError):
        MonthlyContribution(
            scheme="enterprise_employee_basic_pension",
            month=YearMonth(2026, 9),
            pension=money("1400.00"),
            medical=money("584.92"),
            unemployment=money("70.00"),
            subsidy=money("0.00"),
            net_outflow=money("1.00"),
        )


def test_subsidy_eligible_full_period_and_amounts() -> None:
    rules = tuple(
        load_rule("beijing-flex-subsidy", rule_id)
        for rule_id in (
            "beijing-subsidy-eligibility",
            "beijing-subsidy-duration",
            "beijing-subsidy-start-offset",
            "beijing-subsidy-pension-amount",
            "beijing-subsidy-medical-amount",
            "beijing-subsidy-unemployment-amount",
        )
    )
    inputs = {
        "employment_difficulty_recognized": True,
        "employment_registration_days": 45,
        "has_earned_income": True,
        "paid_unemployment_premium_before": True,
        "months_to_retirement": 36,
        "subsidy_months_used": 0,
        "application_month": "2026-08",
        "pension_paid": True,
        "medical_paid": True,
        "unemployment_paid": True,
    }
    assessment = assess_subsidy(rules, inputs, YearMonth(2026, 8), RoundingMode.HALF_UP)
    assert assessment.status is EligibilityStatus.ELIGIBLE
    assert assessment.monthly_subsidy == money("1392.63")
    assert assessment.start_month == YearMonth(2026, 9)
    assert assessment.end_month == YearMonth(2029, 8)
    assert assessment.duration_months == 36
    assert "beijing-subsidy-eligibility" in assessment.rule_refs


def test_subsidy_duration_59_months_extends_to_retirement() -> None:
    eligibility = load_rule("beijing-flex-subsidy", "beijing-subsidy-eligibility")
    duration = load_rule("beijing-flex-subsidy", "beijing-subsidy-duration")
    offset = load_rule("beijing-flex-subsidy", "beijing-subsidy-start-offset")
    amount = load_rule("beijing-flex-subsidy", "beijing-subsidy-pension-amount")
    inputs = {
        "employment_difficulty_recognized": True,
        "employment_registration_days": 30,
        "has_earned_income": True,
        "paid_unemployment_premium_before": True,
        "months_to_retirement": 59,
        "subsidy_months_used": 0,
        "application_month": "2026-08",
        "pension_paid": True,
        "medical_paid": True,
        "unemployment_paid": True,
    }
    at_59 = assess_subsidy(
        (eligibility, duration, offset, amount), inputs, YearMonth(2026, 8), RoundingMode.HALF_UP
    )
    assert at_59.duration_months == 59
    assert at_59.end_month == YearMonth(2031, 7)
    inputs["months_to_retirement"] = 60
    at_60 = assess_subsidy(
        (eligibility, duration, offset, amount), inputs, YearMonth(2026, 8), RoundingMode.HALF_UP
    )
    assert at_60.duration_months == 36
    inputs["months_to_retirement"] = 61
    at_61 = assess_subsidy(
        (eligibility, duration, offset, amount), inputs, YearMonth(2026, 8), RoundingMode.HALF_UP
    )
    assert at_61.duration_months == 36


def test_subsidy_ineligible_when_not_recognized() -> None:
    eligibility = load_rule("beijing-flex-subsidy", "beijing-subsidy-eligibility")
    inputs = {
        "employment_difficulty_recognized": False,
        "employment_registration_days": 30,
        "has_earned_income": True,
        "paid_unemployment_premium_before": True,
    }
    assessment = assess_subsidy((eligibility,), inputs, YearMonth(2026, 8), RoundingMode.HALF_UP)
    assert assessment.status is EligibilityStatus.INELIGIBLE
    assert assessment.monthly_subsidy is None
    assert assessment.start_month is None


def test_subsidy_unknown_when_evidence_missing() -> None:
    eligibility = load_rule("beijing-flex-subsidy", "beijing-subsidy-eligibility")
    assessment = assess_subsidy(
        (eligibility,),
        {"employment_registration_days": 30},
        YearMonth(2026, 8),
        RoundingMode.HALF_UP,
    )
    assert assessment.status is EligibilityStatus.UNKNOWN
    assert assessment.monthly_subsidy is None


def test_annual_parameter_transition_selects_applicable_rules() -> None:
    first = synthetic_rule(
        rule_id="rate-2025",
        effective_from=date(2025, 1, 1),
        effective_to=date(2026, 1, 1),
        parameters={"rate": {"value_type": "DECIMAL", "value": "0.19"}},
        results=(
            {
                "result_id": "pension",
                "output_field": "monthly_pension_contribution",
                "value_type": "DECIMAL",
                "value": {
                    "kind": "EXPRESSION",
                    "operator": "MULTIPLY",
                    "value_type": "DECIMAL",
                    "operands": [
                        {
                            "kind": "REFERENCE",
                            "reference_type": "INPUT",
                            "reference_id": "x",
                            "value_type": "DECIMAL",
                        },
                        {
                            "kind": "REFERENCE",
                            "reference_type": "PARAMETER",
                            "reference_id": "rate",
                            "value_type": "DECIMAL",
                        },
                    ],
                },
            },
        ),
    )
    second = synthetic_rule(
        rule_id="rate-2026",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        parameters={"rate": {"value_type": "DECIMAL", "value": "0.20"}},
        results=first.results,
    )
    rules = (first, second)
    assert [rule.rule_id for rule in choose_applicable_rules(rules, YearMonth(2025, 12))] == [
        "rate-2025"
    ]
    assert [rule.rule_id for rule in choose_applicable_rules(rules, YearMonth(2026, 1))] == [
        "rate-2026"
    ]
    outputs = evaluate_rule(
        choose_applicable_rules(rules, YearMonth(2025, 12))[0], {"x": Decimal("1000.00")}
    )
    assert outputs["monthly_pension_contribution"] == Decimal("190.00")
    outputs = evaluate_rule(
        choose_applicable_rules(rules, YearMonth(2026, 1))[0], {"x": Decimal("1000.00")}
    )
    assert outputs["monthly_pension_contribution"] == Decimal("200.00")


def test_rule_without_match_returns_none() -> None:
    rule = synthetic_rule()
    assert evaluate_rule(rule, {"x": Decimal("1.00")}) is not None
    assert evaluate_rule(rule, {"x": Decimal("-1.00")}) is None


def test_decision_table_evaluates_first_matching_row() -> None:
    rule = load_rule("beijing-flex-subsidy", "beijing-subsidy-duration")
    outputs = evaluate_rule(rule, {"months_to_retirement": 59, "subsidy_months_used": 0})
    assert outputs is not None
    assert outputs["subsidy_duration_months"] == 59
    outputs = evaluate_rule(rule, {"months_to_retirement": 60, "subsidy_months_used": 0})
    assert outputs["subsidy_duration_months"] == 36
    outputs = evaluate_rule(rule, {"months_to_retirement": 40, "subsidy_months_used": 0})
    assert outputs is None


def test_gap_from_rule_reads_requirement() -> None:
    rule = synthetic_rule(
        inputs=({"input_id": "confirmed_months", "value_type": "INTEGER", "required": True},),
        conditions=(
            {
                "condition_id": "nonnegative",
                "input_ref": "confirmed_months",
                "operator": ">=",
                "value_type": "INTEGER",
                "value": 0,
            },
        ),
        results=(
            {
                "result_id": "minimum",
                "output_field": "minimum_months",
                "value_type": "INTEGER",
                "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 180},
            },
        ),
    )
    result = gap_from_rule(rule, 179, YearMonth(2026, 9))
    assert result.remaining_months == 1
    assert result.schedule == (YearMonth(2026, 9),)


@given(st.integers(min_value=0, max_value=240), st.integers(min_value=0, max_value=240))
@settings(max_examples=100)
def test_one_more_confirmed_month_never_increases_gap(confirmed, extra) -> None:
    before = calculate_gap("scheme", 180, confirmed, YearMonth(2026, 9)).remaining_months
    after = calculate_gap("scheme", 180, confirmed + extra + 1, YearMonth(2026, 9)).remaining_months
    assert after <= before


@given(
    st.decimals(min_value=Decimal("100.00"), max_value=Decimal("10000.00"), places=2),
    st.decimals(min_value=Decimal("50.00"), max_value=Decimal("3000.00"), places=2),
    st.decimals(min_value=Decimal("50.00"), max_value=Decimal("3000.00"), places=2),
)
@settings(max_examples=100)
def test_higher_subsidy_never_increases_net_outflow(base, low_subsidy, high_subsidy) -> None:
    def contribution_rule() -> PolicyRule:
        def literal(field: str, amount: str) -> dict:
            return {
                "result_id": field,
                "output_field": f"monthly_{field}_contribution",
                "value_type": "DECIMAL",
                "value": {"kind": "LITERAL", "value_type": "DECIMAL", "value": amount},
            }

        return synthetic_rule(
            rule_id="contribution-rule",
            inputs=({"input_id": "contribution_base", "value_type": "DECIMAL", "required": True},),
            conditions=(
                {
                    "condition_id": "positive",
                    "input_ref": "contribution_base",
                    "operator": ">",
                    "value_type": "DECIMAL",
                    "value": "0.00",
                },
            ),
            results=(
                literal("pension", str(base)),
                literal("medical", "0.00"),
                literal("unemployment", "0.00"),
            ),
        )

    def net_for(amount: Decimal) -> Decimal:
        subsidy_rule = synthetic_rule(
            rule_id="subsidy-rule",
            results=(
                {
                    "result_id": "eligible",
                    "output_field": "subsidy_eligible",
                    "value_type": "BOOLEAN",
                    "value": {"kind": "LITERAL", "value_type": "BOOLEAN", "value": True},
                },
                {
                    "result_id": "duration",
                    "output_field": "subsidy_duration_months",
                    "value_type": "INTEGER",
                    "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 12},
                },
                {
                    "result_id": "offset",
                    "output_field": "subsidy_start_offset_months",
                    "value_type": "INTEGER",
                    "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 1},
                },
                {
                    "result_id": "subsidy",
                    "output_field": "monthly_subsidy_pension",
                    "value_type": "DECIMAL",
                    "value": {"kind": "LITERAL", "value_type": "DECIMAL", "value": str(amount)},
                },
            ),
        )
        assessment = assess_subsidy(
            (subsidy_rule,), {"x": Decimal("1.00")}, YearMonth(2026, 8), RoundingMode.HALF_UP
        )
        assert assessment.status is EligibilityStatus.ELIGIBLE
        gross = monthly_contributions(
            (contribution_rule(),), Decimal("1.00"), (YearMonth(2026, 9),), RoundingMode.HALF_UP
        )[0].net_outflow.amount
        return gross - assessment.monthly_subsidy.amount

    assert net_for(max(low_subsidy, high_subsidy)) <= net_for(min(low_subsidy, high_subsidy))


def test_identical_inputs_yield_identical_canonical_results() -> None:
    rules = (
        load_rule("beijing-flex-employment", "beijing-flex-pension-contribution"),
        load_rule("beijing-flex-employment", "beijing-flex-medical-contribution"),
        load_rule("beijing-flex-employment", "beijing-flex-unemployment-contribution"),
    )
    months = (YearMonth(2026, 9), YearMonth(2026, 10))
    first = monthly_contributions(rules, Decimal("7000.00"), months, RoundingMode.HALF_UP)
    second = monthly_contributions(rules, Decimal("7000.00"), months, RoundingMode.HALF_UP)
    assert first == second
    assert [entry.net_outflow.amount for entry in first] == [
        entry.net_outflow.amount for entry in second
    ]
