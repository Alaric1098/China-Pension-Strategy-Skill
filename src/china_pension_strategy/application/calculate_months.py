"""Deterministic evaluator over resolved policy rules, parameters, and decision tables."""

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import ROUND_FLOOR, Decimal, InvalidOperation, localcontext
from typing import Any, cast

from china_pension_strategy.domain.calculation import (
    GapResult,
    MonthlyContribution,
    SubsidyAssessment,
)
from china_pension_strategy.domain.eligibility import EligibilityStatus
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import PolicyRule, RuleType
from china_pension_strategy.domain.values import Money, RoundingMode, YearMonth

CNY = "CNY"
CENT = Decimal("0.01")


def canonical_scalar(value_type: object, value: object) -> object:
    """Coerce JSON-encoded or domain-typed scalar to its canonical Python value."""
    if value_type == "DECIMAL":
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    if value_type == "YEAR_MONTH":
        if isinstance(value, YearMonth):
            return value
        year, month = str(value).split("-")
        return YearMonth(int(year), int(month))
    if value_type == "DATE":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value))
    if value_type == "INTEGER":
        if isinstance(value, bool) or not isinstance(value, int):
            raise DomainValidationError("INTEGER value must be an integer")
        return value
    if value_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise DomainValidationError("BOOLEAN value must be a boolean")
        return value
    if value_type == "STRING":
        if not isinstance(value, str):
            raise DomainValidationError("STRING value must be a string")
        return value
    if value_type == "NULL":
        return None
    raise DomainValidationError(f"unsupported value_type {value_type!r}")


def _order_key(value: object) -> tuple[Any, ...]:
    if isinstance(value, YearMonth):
        return (value.year * 12 + value.month,)
    if isinstance(value, date):
        return (value.toordinal(),)
    if isinstance(value, bool):
        return (int(value),)
    if isinstance(value, int):
        return (value,)
    if isinstance(value, Decimal):
        return (value,)
    if isinstance(value, str):
        return (value,)
    if value is None:
        return (None,)
    raise DomainValidationError(f"value {value!r} is not comparable")


def _condition_matches(condition: Mapping[str, object], inputs: Mapping[str, object]) -> bool:
    input_ref = condition.get("input_ref")
    if input_ref not in inputs:
        return False
    actual = canonical_scalar(condition.get("value_type"), inputs[cast(str, input_ref)])
    expected = canonical_scalar(condition.get("value_type"), condition.get("value"))
    operator = condition.get("operator")
    if operator in ("=", "!="):
        equal = actual == expected
        return not equal if operator == "!=" else equal
    if operator in ("<", "<=", ">", ">="):
        left, right = _order_key(actual), _order_key(expected)
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        return left >= right
    raise DomainValidationError(f"unsupported operator {operator!r}")


def _parameter_value(rule: PolicyRule, name: str) -> object:
    declaration = rule.parameters.get(name)
    if not isinstance(declaration, Mapping):
        raise DomainValidationError(f"parameter {name} not declared")
    return canonical_scalar(declaration.get("value_type"), declaration.get("value"))


def evaluate_expression(
    expression: Mapping[str, object],
    inputs: Mapping[str, object],
    parameters: Mapping[str, object],
) -> object:
    """Evaluate a policy expression AST into a typed Python value."""
    kind = expression.get("kind")
    value_type = expression.get("value_type")
    if kind == "LITERAL":
        return canonical_scalar(value_type, expression.get("value"))
    if kind == "REFERENCE":
        reference_type = expression.get("reference_type")
        reference_id = expression.get("reference_id")
        if reference_type == "INPUT":
            if reference_id not in inputs:
                raise DomainValidationError(f"input reference {reference_id} is not provided")
            return canonical_scalar(value_type, inputs[cast(str, reference_id)])
        if reference_type == "PARAMETER":
            if reference_id not in parameters:
                raise DomainValidationError(f"parameter reference {reference_id} is not declared")
            return canonical_scalar(value_type, parameters[cast(str, reference_id)])
        raise DomainValidationError(f"unsupported reference_type {reference_type!r}")
    if kind == "EXPRESSION":
        operands = [
            evaluate_expression(operand, inputs, parameters)
            for operand in cast(tuple[Mapping[str, object], ...], expression.get("operands", ()))
        ]
        operator = expression.get("operator")
        if operator == "ADD":
            result = _add(operands)
        elif operator == "SUBTRACT":
            result = _subtract(operands)
        elif operator == "MULTIPLY":
            result = _multiply(operands)
        elif operator == "DIVIDE":
            result = _divide(operands)
        elif operator == "FLOOR_DIVIDE":
            result = _floor_divide(operands)
        elif operator == "POWER":
            result = _power(operands)
        elif operator == "MIN":
            result = _min_of(operands)
        elif operator == "MAX":
            result = _max_of(operands)
        else:
            raise DomainValidationError(f"unsupported expression operator {operator!r}")
        return _cast_result(result, value_type)
    raise DomainValidationError(f"unsupported expression kind {kind!r}")


def _cast_result(value: object, value_type: object) -> object:
    if value_type == "DECIMAL":
        if isinstance(value, bool):
            raise DomainValidationError("DECIMAL result cannot be boolean")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    if value_type == "INTEGER":
        if isinstance(value, bool):
            raise DomainValidationError("INTEGER result cannot be boolean")
        if isinstance(value, Decimal):
            return int(value)
        return int(Decimal(str(value)))
    if value_type == "BOOLEAN":
        return bool(value)
    if value_type == "STRING":
        return str(value)
    return value


def _numbers(operands: list[object]) -> list[Decimal]:
    values = []
    for operand in operands:
        if isinstance(operand, bool) or not isinstance(operand, (int, Decimal)):
            raise DomainValidationError("expression operands must be numeric")
        values.append(Decimal(operand))
    return values


def _add(operands: list[object]) -> object:
    values = _numbers(operands)
    if not values:
        raise DomainValidationError("ADD requires at least one operand")
    result = values[0]
    for value in values[1:]:
        result += value
    return result


def _subtract(operands: list[object]) -> object:
    values = _numbers(operands)
    if len(values) != 2:
        raise DomainValidationError("SUBTRACT requires two operands")
    return values[0] - values[1]


def _multiply(operands: list[object]) -> object:
    values = _numbers(operands)
    if not values:
        raise DomainValidationError("MULTIPLY requires at least one operand")
    result = values[0]
    for value in values[1:]:
        result *= value
    return result


def _divide(operands: list[object]) -> object:
    values = _numbers(operands)
    if len(values) != 2:
        raise DomainValidationError("DIVIDE requires two operands")
    if values[1] == 0:
        raise DomainValidationError("DIVIDE by zero")
    return values[0] / values[1]


def _floor_divide(operands: list[object]) -> object:
    values = _numbers(operands)
    if len(values) != 2:
        raise DomainValidationError("FLOOR_DIVIDE requires two operands")
    if values[1] == 0:
        raise DomainValidationError("FLOOR_DIVIDE by zero")
    # Floor division with Python // semantics (-5 // 2 == -3). Decimal's
    # context-dependent division can round the quotient before flooring, so
    # take the exact quotient under high precision then round toward -inf.
    with localcontext() as context:
        context.prec = 40
        quotient = values[0] / values[1]
    return int(quotient.to_integral_value(rounding=ROUND_FLOOR))


def _power(operands: list[object]) -> object:
    values = _numbers(operands)
    if len(values) != 2:
        raise DomainValidationError("POWER requires two operands")
    base, exponent = values
    if exponent < 0:
        raise DomainValidationError("POWER exponent must be non-negative")
    with localcontext() as context:
        context.prec = 40
        try:
            return base**exponent
        except (ValueError, InvalidOperation) as error:
            raise DomainValidationError(f"POWER evaluation failed: {error}") from error


def _min_of(operands: list[object]) -> object:
    if not operands:
        raise DomainValidationError("MIN requires at least one operand")
    return min(operands, key=_order_key)


def _max_of(operands: list[object]) -> object:
    if not operands:
        raise DomainValidationError("MAX requires at least one operand")
    return max(operands, key=_order_key)


def _rule_outputs(rule: PolicyRule, inputs: Mapping[str, object]) -> dict[str, object]:
    parameters = {name: _parameter_value(rule, name) for name in rule.parameters}
    if rule.rule_type is RuleType.DECISION_TABLE:
        for row in rule.decision_rows:
            if all(
                _condition_matches(condition, inputs)
                for condition in cast(tuple[Mapping[str, object], ...], row["conditions"])
            ):
                return {
                    cast(str, result["output_field"]): evaluate_expression(
                        cast(Mapping[str, object], result["value"]), inputs, parameters
                    )
                    for result in cast(tuple[Mapping[str, object], ...], row["results"])
                }
        return {}
    if all(_condition_matches(condition, inputs) for condition in rule.conditions):
        return {
            cast(str, result["output_field"]): evaluate_expression(
                cast(Mapping[str, object], result["value"]), inputs, parameters
            )
            for result in rule.results
        }
    return {}


def evaluate_rule(rule: PolicyRule, inputs: Mapping[str, object]) -> Mapping[str, object] | None:
    """Evaluate one rule; None when its conditions do not match."""
    outputs = _rule_outputs(rule, inputs)
    return outputs if outputs else None


def choose_applicable_rules(
    rules: Iterable[PolicyRule], month: YearMonth
) -> tuple[PolicyRule, ...]:
    """Select rules whose effective interval covers the given month."""
    month_start = date(month.year, month.month, 1)
    selected = []
    for rule in rules:
        if rule.effective_from <= month_start and (
            rule.effective_to is None or month_start < rule.effective_to
        ):
            selected.append(rule)
    return tuple(selected)


def calculate_gap(
    scheme: str,
    requirement_months: int,
    confirmed_months: int,
    as_of: YearMonth,
) -> GapResult:
    if isinstance(requirement_months, bool) or not isinstance(requirement_months, int):
        raise DomainValidationError("requirement_months must be an integer")
    if isinstance(confirmed_months, bool) or not isinstance(confirmed_months, int):
        raise DomainValidationError("confirmed_months must be an integer")
    if requirement_months < 0 or confirmed_months < 0:
        raise DomainValidationError("month counts cannot be negative")
    remaining = max(requirement_months - confirmed_months, 0)
    schedule = tuple(as_of.add_months(offset) for offset in range(remaining))
    return GapResult(
        scheme=scheme,
        requirement_months=requirement_months,
        confirmed_months=confirmed_months,
        remaining_months=remaining,
        schedule=schedule,
    )


def gap_from_rule(
    rule: PolicyRule,
    confirmed_months: int,
    as_of: YearMonth,
    requirement_field: str = "minimum_months",
) -> GapResult:
    outputs = _rule_outputs(rule, {"confirmed_months": confirmed_months})
    if requirement_field not in outputs:
        raise DomainValidationError(f"rule {rule.rule_id} does not produce {requirement_field}")
    requirement = outputs[requirement_field]
    if isinstance(requirement, bool) or not isinstance(requirement, int):
        raise DomainValidationError("requirement must be an integer")
    return calculate_gap(rule.scheme, requirement, confirmed_months, as_of)


def _money(amount: object, rounding: RoundingMode) -> Money:
    if isinstance(amount, bool) or not isinstance(amount, (int, Decimal)):
        raise DomainValidationError("contribution amounts must be numeric")
    return Money(Decimal(amount), CNY).quantize(CENT, rounding)


def monthly_contributions(
    rules: Iterable[PolicyRule],
    contribution_base: Decimal,
    months: Iterable[YearMonth],
    rounding: RoundingMode,
) -> tuple[MonthlyContribution, ...]:
    """Evaluate contribution rules per month; outputs are summed by field name."""
    rule_list = tuple(rules)
    if not rule_list:
        raise DomainValidationError("at least one contribution rule is required")
    schemes = {rule.scheme for rule in rule_list}
    if len(schemes) != 1:
        raise DomainValidationError("contribution rules must share one scheme")
    scheme = next(iter(schemes))
    outputs = {}
    for rule in rule_list:
        for output_field, value in _rule_outputs(
            rule, {"contribution_base": contribution_base}
        ).items():
            if output_field in outputs:
                raise DomainValidationError(f"duplicate contribution output {output_field}")
            outputs[output_field] = value

    def field(name: str) -> Money:
        if name not in outputs:
            raise DomainValidationError(f"contribution rules do not produce {name}")
        return _money(outputs[name], rounding)

    def optional_field(name: str) -> Money:
        # Regions differ in which insurances flex workers join (e.g. Shanghai
        # flex employment excludes unemployment insurance). A missing output
        # means "not covered / not modeled yet" and contributes zero rather
        # than failing the whole scenario.
        if name not in outputs:
            return Money(Decimal("0.00"), CNY)
        return _money(outputs[name], rounding)

    pension = field("monthly_pension_contribution")
    medical = optional_field("monthly_medical_contribution")
    unemployment = optional_field("monthly_unemployment_contribution")
    zero = Money(Decimal("0.00"), CNY)
    result = []
    for month in months:
        net = Money(pension.amount + medical.amount + unemployment.amount, CNY)
        result.append(
            MonthlyContribution(
                scheme=scheme,
                month=month,
                pension=pension,
                medical=medical,
                unemployment=unemployment,
                subsidy=zero,
                net_outflow=net,
            )
        )
    return tuple(result)


def assess_subsidy(
    rules: Iterable[PolicyRule],
    inputs: Mapping[str, object],
    application_month: YearMonth,
    rounding: RoundingMode,
) -> SubsidyAssessment:
    """Merge matched subsidy rule outputs into one SubsidyAssessment."""
    merged: dict[str, object] = {}
    rule_ids: list[str] = []
    for rule in rules:
        outputs = _rule_outputs(rule, inputs)
        if not outputs:
            continue
        rule_ids.append(rule.rule_id)
        for output_field, value in outputs.items():
            if output_field in merged:
                raise DomainValidationError(f"competing subsidy outputs for {output_field}")
            merged[output_field] = value

    eligible = merged.get("subsidy_eligible")
    if eligible is None:
        if merged:
            return SubsidyAssessment(
                status=EligibilityStatus.UNKNOWN,
                monthly_subsidy=None,
                start_month=None,
                end_month=None,
                duration_months=None,
                rule_refs=tuple(rule_ids),
            )
        fully_evaluable = any(
            all(declaration.get("input_id") in inputs for declaration in rule.inputs)
            for rule in rules
        )
        status = EligibilityStatus.INELIGIBLE if fully_evaluable else EligibilityStatus.UNKNOWN
        return SubsidyAssessment(
            status=status,
            monthly_subsidy=None,
            start_month=None,
            end_month=None,
            duration_months=None,
            rule_refs=tuple(rule_ids),
        )
    if eligible is not True:
        return SubsidyAssessment(
            status=EligibilityStatus.INELIGIBLE,
            monthly_subsidy=None,
            start_month=None,
            end_month=None,
            duration_months=None,
            rule_refs=tuple(rule_ids),
        )
    duration = merged.get("subsidy_duration_months")
    start_offset = merged.get("subsidy_start_offset_months")
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise DomainValidationError("subsidy_duration_months must be an integer")
    if not isinstance(start_offset, int) or isinstance(start_offset, bool):
        raise DomainValidationError("subsidy_start_offset_months must be an integer")
    amount_fields = [
        (field, value)
        for field, value in merged.items()
        if field.startswith("monthly_subsidy_") and field != "monthly_subsidy"
    ]
    if not amount_fields:
        raise DomainValidationError("eligible subsidy requires monthly amounts")
    total = Decimal("0.00")
    for field, value in amount_fields:
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            raise DomainValidationError(f"{field} must be numeric")
        total += Decimal(value)
    start_month = application_month.add_months(start_offset)
    end_month = start_month.add_months(duration - 1)
    return SubsidyAssessment(
        status=EligibilityStatus.ELIGIBLE,
        monthly_subsidy=_money(total, rounding),
        start_month=start_month,
        end_month=end_month,
        duration_months=duration,
        rule_refs=tuple(rule_ids),
    )
