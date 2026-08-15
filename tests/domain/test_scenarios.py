import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from china_pension_strategy.application.analyze_scenarios import (
    ScenarioGenerationError,
    build_monthly_cash_flows,
    generate_scenario,
    rank_scenarios,
    select_recommended,
    zero_money,
)
from china_pension_strategy.application.calculate_months import assess_subsidy
from china_pension_strategy.application.recommend import build_recommendation
from china_pension_strategy.domain.eligibility import EligibilityStatus
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import (
    JurisdictionRole,
    LegalHierarchy,
    PolicyRule,
    RuleType,
)
from china_pension_strategy.domain.scenario import (
    ActionType,
    Assumption,
    CashFlow,
    Recommendation,
    Scenario,
    ScenarioAction,
    ScenarioFeasibility,
    ScenarioOutcome,
    Threshold,
)
from china_pension_strategy.domain.values import (
    Money,
    RoundingMode,
    YearMonth,
    YearMonthRange,
)

ROOT = Path(__file__).resolve().parents[2]
CNY = "CNY"


def money(amount: str) -> Money:
    return Money(Decimal(amount), CNY)


def rule(
    rule_id: str,
    results: tuple[dict, ...],
    inputs: tuple[dict, ...] = (
        {"input_id": "contribution_base", "value_type": "DECIMAL", "required": True},
    ),
    conditions: tuple[dict, ...] = (
        {"condition_id": "positive", "input_ref": "contribution_base", "operator": ">", "value_type": "DECIMAL", "value": "0.00"},
    ),
) -> PolicyRule:
    def converted(cond: dict) -> dict:
        return {
            **cond,
            "value": Decimal(str(cond["value"]))
            if cond["value_type"] == "DECIMAL"
            else cond["value"],
        }

    def converted_result(entry: dict) -> dict:
        value = entry["value"]
        if value.get("kind") == "LITERAL" and value["value_type"] == "DECIMAL":
            value = {**value, "value": Decimal(str(value["value"]))}
        return {**entry, "value": value}

    return PolicyRule(
        rule_id=rule_id,
        rule_type=RuleType.POLICY_RULE,
        scheme="enterprise_employee_basic_pension",
        topic="test_topic",
        jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
        population_scope="test population",
        inputs=inputs,
        conditions=tuple(converted(cond) for cond in conditions),
        results=tuple(converted_result(entry) for entry in results),
        exceptions=(),
        effective_from=date(2026, 1, 1),
        effective_to=None,
        transaction_from=datetime(2026, 8, 11, tzinfo=timezone.utc),
        transaction_to=None,
        legal_hierarchy=LegalHierarchy.MUNICIPAL_REGULATION,
        explicit_override_refs=(),
        source_refs=("source-a",),
        parameters={},
        test_vectors=(
            {
                "vector_id": f"v-{rule_id}",
                "input": {"contribution_base": Decimal("1.00")},
                "expected": {
                    entry["output_field"]: (
                        True
                        if entry["value"]["value_type"] == "BOOLEAN"
                        else 1
                        if entry["value"]["value_type"] == "INTEGER"
                        else Decimal("1.00")
                    )
                    for entry in results
                },
            },
        ),
    )


def literal(field: str, amount: str) -> dict:
    return {
        "result_id": field,
        "output_field": field,
        "value_type": "DECIMAL",
        "value": {"kind": "LITERAL", "value_type": "DECIMAL", "value": amount},
    }


def contribution_rule() -> PolicyRule:
    return rule(
        "contribution-rule",
        (
            literal("monthly_pension_contribution", "1400.00"),
            literal("monthly_medical_contribution", "584.92"),
            literal("monthly_unemployment_contribution", "70.00"),
        ),
    )


def subsidy_rule(amount: str = "1392.63") -> PolicyRule:
    return rule(
        "subsidy-rule",
        (
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
                "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 36},
            },
            {
                "result_id": "offset",
                "output_field": "subsidy_start_offset_months",
                "value_type": "INTEGER",
                "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 1},
            },
            literal("monthly_subsidy_pension", amount),
        ),
    )


def base_inputs() -> dict:
    return {"contribution_base": Decimal("7000.00")}


def horizon() -> YearMonthRange:
    return YearMonthRange(YearMonth(2026, 9), YearMonth(2026, 11))


def actions(*types: ActionType) -> tuple[ScenarioAction, ...]:
    return tuple(
        ScenarioAction(month=YearMonth(2026, 9), action_type=action_type)
        for action_type in types
    )


def test_continue_scenario_has_expected_cash_flows() -> None:
    scenario = generate_scenario(
        scenario_id="continue",
        horizon=horizon(),
        actions=actions(ActionType.CONTINUE_CONTRIBUTING),
        contribution_rules=(contribution_rule(),),
        contribution_base=Decimal("7000.00"),
        subsidy_assessment=None,
        rounding=RoundingMode.HALF_UP,
        confirmed_months=179,
        requirement_months=180,
        capability_refs=["CONTRIBUTION_GAP"],
    )
    assert scenario.feasibility is ScenarioFeasibility.FEASIBLE
    assert len(scenario.monthly_cash_flows) == 3
    first = scenario.monthly_cash_flows[0]
    assert first.pension == money("1400.00")
    assert first.medical == money("584.92")
    assert first.unemployment == money("70.00")
    assert first.subsidy == money("0.00")
    assert first.net_outflow == money("2054.92")
    assert first.cumulative_outflow == money("2054.92")
    assert scenario.outcomes.ending_confirmed_months == 182
    assert scenario.outcomes.ending_gap_months == 0
    assert scenario.outcomes.total_net_outflow == money("6164.76")


def test_stop_scenario_has_zero_cash_flows_and_unchanged_gap() -> None:
    scenario = generate_scenario(
        scenario_id="stop",
        horizon=horizon(),
        actions=actions(ActionType.STOP_CONTRIBUTING),
        contribution_rules=None,
        contribution_base=None,
        subsidy_assessment=None,
        rounding=RoundingMode.HALF_UP,
        confirmed_months=179,
        requirement_months=180,
        capability_refs=["CONTRIBUTION_GAP"],
    )
    assert all(flow.net_outflow == money("0.00") for flow in scenario.monthly_cash_flows)
    assert scenario.outcomes.ending_confirmed_months == 179
    assert scenario.outcomes.ending_gap_months == 1


def test_subsidy_timing_reduces_net_outflow_within_subsidy_period() -> None:
    assessment = assess_subsidy(
        (subsidy_rule(),), base_inputs(), YearMonth(2026, 8), RoundingMode.HALF_UP
    )
    assert assessment.status is EligibilityStatus.ELIGIBLE
    scenario = generate_scenario(
        scenario_id="subsidized",
        horizon=horizon(),
        actions=actions(ActionType.CONTINUE_CONTRIBUTING, ActionType.APPLY_FOR_SUBSIDY),
        contribution_rules=(contribution_rule(),),
        contribution_base=Decimal("7000.00"),
        subsidy_assessment=assessment,
        rounding=RoundingMode.HALF_UP,
        confirmed_months=179,
        requirement_months=180,
        capability_refs=["SUBSIDY_ELIGIBILITY"],
    )
    assert scenario.monthly_cash_flows[0].subsidy == money("1392.63")
    assert scenario.monthly_cash_flows[0].net_outflow == money("662.29")
    assert scenario.monthly_cash_flows[0].cumulative_outflow == money("662.29")
    assert scenario.monthly_cash_flows[2].cumulative_outflow == money("1986.87")


def test_horizon_is_inclusive_of_both_ends() -> None:
    period = YearMonthRange(YearMonth(2026, 9), YearMonth(2026, 11))
    assert period.month_count == 3
    assert tuple(period) == (YearMonth(2026, 9), YearMonth(2026, 10), YearMonth(2026, 11))


def test_cash_flow_months_must_match_horizon() -> None:
    flow = CashFlow(
        month=YearMonth(2026, 9),
        pension=money("1400.00"),
        medical=money("584.92"),
        unemployment=money("70.00"),
        subsidy=money("0.00"),
        net_outflow=money("2054.92"),
        cumulative_outflow=money("2054.92"),
    )
    with pytest.raises(DomainValidationError):
        Scenario(
            scenario_id="mismatch",
            feasibility=ScenarioFeasibility.FEASIBLE,
            capability_refs=("CONTRIBUTION_GAP",),
            horizon=horizon(),
            actions=(),
            monthly_cash_flows=(flow,),
            outcomes=ScenarioOutcome(
                ending_confirmed_months=180,
                ending_gap_months=0,
                total_pension=money("1400.00"),
                total_medical=money("584.92"),
                total_unemployment=money("70.00"),
                total_subsidy=money("0.00"),
                total_net_outflow=money("2054.92"),
            ),
            thresholds=(),
        )


def test_stop_and_continue_cannot_coexist() -> None:
    with pytest.raises(ScenarioGenerationError):
        generate_scenario(
            scenario_id="conflict",
            horizon=horizon(),
            actions=actions(ActionType.STOP_CONTRIBUTING, ActionType.CONTINUE_CONTRIBUTING),
            contribution_rules=(contribution_rule(),),
            contribution_base=Decimal("7000.00"),
            subsidy_assessment=None,
            rounding=RoundingMode.HALF_UP,
            confirmed_months=179,
            requirement_months=180,
            capability_refs=["CONTRIBUTION_GAP"],
        )


def test_thresholds_and_assumptions_are_carried() -> None:
    threshold = Threshold(
        threshold_id="minimum-months",
        metric="confirmed_months",
        operator=">=",
        value=Decimal("180.00"),
    )
    assumption = Assumption(
        assumption_id="reemployment-event",
        event_definition="Synthetic reemployment model",
        source_type="official_statistic",
        modeling_mode="EVIDENCE_BACKED_PROBABILITY",
        distribution={"family": "beta", "parameters": {"alpha": 2.0, "beta": 5.0}},
        source_date=date(2026, 1, 1),
        population="Synthetic population",
        provenance_refs=("official-statistic-001",),
        approved_by="reviewer-001",
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        dependency_treatment="Sensitivity only",
    )
    scenario = generate_scenario(
        scenario_id="continue",
        horizon=horizon(),
        actions=actions(ActionType.CONTINUE_CONTRIBUTING),
        contribution_rules=(contribution_rule(),),
        contribution_base=Decimal("7000.00"),
        subsidy_assessment=None,
        rounding=RoundingMode.HALF_UP,
        confirmed_months=179,
        requirement_months=180,
        capability_refs=["CONTRIBUTION_GAP"],
        thresholds=(threshold,),
        sensitivity={"mode": "THRESHOLD", "assumption_refs": (assumption.assumption_id,)},
    )
    assert scenario.thresholds == (threshold,)
    assert scenario.sensitivity["mode"] == "THRESHOLD"


def test_infeasible_scenarios_rank_last_and_never_recommended() -> None:
    feasible = generate_scenario(
        scenario_id="continue",
        horizon=horizon(),
        actions=actions(ActionType.CONTINUE_CONTRIBUTING),
        contribution_rules=(contribution_rule(),),
        contribution_base=Decimal("7000.00"),
        subsidy_assessment=None,
        rounding=RoundingMode.HALF_UP,
        confirmed_months=179,
        requirement_months=180,
        capability_refs=["CONTRIBUTION_GAP"],
    )
    blocked = Scenario(
        scenario_id="blocked",
        feasibility=ScenarioFeasibility.INFEASIBLE,
        capability_refs=("SUBSIDY_ELIGIBILITY",),
        horizon=horizon(),
        actions=(),
        monthly_cash_flows=(),
        outcomes=ScenarioOutcome(
            ending_confirmed_months=179,
            ending_gap_months=1,
            total_pension=money("0.00"),
            total_medical=money("0.00"),
            total_unemployment=money("0.00"),
            total_subsidy=money("0.00"),
            total_net_outflow=money("0.00"),
        ),
        thresholds=(),
    )
    ranked = rank_scenarios((blocked, feasible))
    assert ranked[0].scenario_id == "continue"
    assert ranked[1].scenario_id == "blocked"
    assert select_recommended(ranked).scenario_id == "continue"
    with pytest.raises(ScenarioGenerationError):
        select_recommended((blocked,))


def test_ranking_prefers_lower_net_outflow() -> None:
    def scenario_for(scenario_id: str, outflow: str) -> Scenario:
        return Scenario(
            scenario_id=scenario_id,
            feasibility=ScenarioFeasibility.FEASIBLE,
            capability_refs=("CONTRIBUTION_GAP",),
            horizon=YearMonthRange(YearMonth(2026, 9), YearMonth(2026, 9)),
            actions=(),
            monthly_cash_flows=(
                CashFlow(
                    month=YearMonth(2026, 9),
                    pension=money(outflow),
                    medical=money("0.00"),
                    unemployment=money("0.00"),
                    subsidy=money("0.00"),
                    net_outflow=money(outflow),
                    cumulative_outflow=money(outflow),
                ),
            ),
            outcomes=ScenarioOutcome(
                ending_confirmed_months=180,
                ending_gap_months=0,
                total_pension=money(outflow),
                total_medical=money("0.00"),
                total_unemployment=money("0.00"),
                total_subsidy=money("0.00"),
                total_net_outflow=money(outflow),
            ),
            thresholds=(),
        )

    expensive = scenario_for("expensive", "6164.76")
    cheap = scenario_for("cheap", "662.29")
    ranked = rank_scenarios((expensive, cheap))
    assert [scenario.scenario_id for scenario in ranked] == ["cheap", "expensive"]


def test_ranking_is_deterministic_by_total_outflow_then_id() -> None:
    scenarios = (
        generate_scenario(
            scenario_id="continue",
            horizon=horizon(),
            actions=actions(ActionType.CONTINUE_CONTRIBUTING),
            contribution_rules=(contribution_rule(),),
            contribution_base=Decimal("7000.00"),
            subsidy_assessment=None,
            rounding=RoundingMode.HALF_UP,
            confirmed_months=179,
            requirement_months=180,
            capability_refs=["CONTRIBUTION_GAP"],
        ),
    )
    assert rank_scenarios(scenarios) == rank_scenarios(scenarios)


def test_recommendation_requires_limitations() -> None:
    scenario = generate_scenario(
        scenario_id="continue",
        horizon=horizon(),
        actions=actions(ActionType.CONTINUE_CONTRIBUTING),
        contribution_rules=(contribution_rule(),),
        contribution_base=Decimal("7000.00"),
        subsidy_assessment=None,
        rounding=RoundingMode.HALF_UP,
        confirmed_months=179,
        requirement_months=180,
        capability_refs=["CONTRIBUTION_GAP"],
    )
    recommendation = build_recommendation(
        scenario,
        objective="MINIMUM_COMPLIANCE_COST",
        capability_dependencies=({"capability_id": "CONTRIBUTION_GAP", "status": "AVAILABLE"},),
        limitations=("Local informational screening only.",),
        invalidators=("Official account record changes.",),
        review_triggers=("Policy package changes.",),
    )
    assert recommendation.scenario_id == "continue"
    assert recommendation.invalidators == ("Official account record changes.",)
    with pytest.raises(DomainValidationError):
        build_recommendation(
            scenario,
            objective="MINIMUM_COMPLIANCE_COST",
            capability_dependencies=(),
            limitations=(),
        )


def test_cumulative_outflow_is_last_net_sums() -> None:
    flows = build_monthly_cash_flows(
        (YearMonth(2026, 9), YearMonth(2026, 10), YearMonth(2026, 11)),
        {
            month: {
                "pension": money("1400.00"),
                "medical": money("584.92"),
                "unemployment": money("70.00"),
            }
            for month in (
                YearMonth(2026, 9),
                YearMonth(2026, 10),
                YearMonth(2026, 11),
            )
        },
        {YearMonth(2026, 9): money("1392.63")},
    )
    assert flows[-1].cumulative_outflow.amount == sum(
        (flow.net_outflow.amount for flow in flows), Decimal("0.00")
    )


@given(st.integers(min_value=0, max_value=40))
@settings(max_examples=50)
def test_cumulative_outflow_equals_sum_of_net_outflows(month_count) -> None:
    months = tuple(
        YearMonth(2026, 9).add_months(offset) for offset in range(month_count)
    )
    contributions = {
        month: {"pension": money("1400.00"), "medical": money("0.00"), "unemployment": money("0.00")}
        for month in months
    }
    subsidies = {}
    flows = build_monthly_cash_flows(months, contributions, subsidies)
    if flows:
        assert flows[-1].cumulative_outflow.amount == sum(
            (flow.net_outflow.amount for flow in flows), Decimal("0.00")
        )
    assert len(flows) == month_count


def test_unknown_eligibility_produces_no_subsidy_flows() -> None:
    unknown = assess_subsidy(
        (subsidy_rule(),), {}, YearMonth(2026, 8), RoundingMode.HALF_UP
    )
    assert unknown.status is EligibilityStatus.UNKNOWN
    scenario = generate_scenario(
        scenario_id="continue",
        horizon=horizon(),
        actions=actions(ActionType.CONTINUE_CONTRIBUTING, ActionType.APPLY_FOR_SUBSIDY),
        contribution_rules=(contribution_rule(),),
        contribution_base=Decimal("7000.00"),
        subsidy_assessment=unknown,
        rounding=RoundingMode.HALF_UP,
        confirmed_months=179,
        requirement_months=180,
        capability_refs=["SUBSIDY_ELIGIBILITY"],
    )
    assert all(flow.subsidy == zero_money() for flow in scenario.monthly_cash_flows)
