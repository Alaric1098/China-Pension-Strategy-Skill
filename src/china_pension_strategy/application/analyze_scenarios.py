"""Deterministic monthly scenario generation and ranking."""

from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from china_pension_strategy.domain.calculation import SubsidyAssessment
from china_pension_strategy.domain.eligibility import EligibilityStatus
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import PolicyRule
from china_pension_strategy.domain.scenario import (
    ActionType,
    Assumption,
    CashFlow,
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
from china_pension_strategy.application.calculate_months import (
    assess_subsidy,
    monthly_contributions,
)

CNY = "CNY"
CENT = Decimal("0.01")


class ScenarioGenerationError(Exception):
    """Base class for safe scenario generation failures."""


def zero_money() -> Money:
    return Money(Decimal("0.00"), CNY)


def build_monthly_cash_flows(
    months: Sequence[YearMonth],
    contributions: Mapping[YearMonth, Mapping[str, Money]],
    subsidies: Mapping[YearMonth, Money],
) -> tuple[CashFlow, ...]:
    """Combine contribution and subsidy money per month into cash flows."""
    flows: list[CashFlow] = []
    cumulative = Decimal("0.00")
    for month in months:
        entry = contributions.get(month, {})
        pension = entry.get("pension", zero_money())
        medical = entry.get("medical", zero_money())
        unemployment = entry.get("unemployment", zero_money())
        subsidy = subsidies.get(month, zero_money())
        net = Money(
            pension.amount + medical.amount + unemployment.amount - subsidy.amount,
            CNY,
        )
        cumulative += net.amount
        flows.append(
            CashFlow(
                month=month,
                pension=pension,
                medical=medical,
                unemployment=unemployment,
                subsidy=subsidy,
                net_outflow=net,
                cumulative_outflow=Money(cumulative, CNY),
            )
        )
    return tuple(flows)


def generate_scenario(
    scenario_id: str,
    horizon: YearMonthRange,
    actions: Sequence[ScenarioAction],
    contribution_rules: Sequence[PolicyRule] | None,
    contribution_base: Decimal | None,
    subsidy_assessment: SubsidyAssessment | None,
    rounding: RoundingMode,
    confirmed_months: int,
    requirement_months: int,
    capability_refs: Sequence[str],
    thresholds: Sequence[Threshold] = (),
    sensitivity: Mapping[str, object] | None = None,
) -> Scenario:
    """Generate the monthly cash-flow scenario for one action sequence."""
    stopping = any(
        action.action_type is ActionType.STOP_CONTRIBUTING for action in actions
    )
    continuing = any(
        action.action_type is ActionType.CONTINUE_CONTRIBUTING for action in actions
    )
    if continuing and stopping:
        raise ScenarioGenerationError("a scenario cannot both stop and continue")

    months = tuple(horizon)
    contributions: dict[YearMonth, dict[str, Money]] = {}
    subsidies: dict[YearMonth, Money] = {}
    ending_confirmed = confirmed_months
    if continuing:
        if not contribution_rules or contribution_base is None:
            raise ScenarioGenerationError(
                "CONTINUE_CONTRIBUTING requires contribution rules and base"
            )
        schedule = monthly_contributions(
            contribution_rules, contribution_base, months, rounding
        )
        for entry in schedule:
            contributions[entry.month] = {
                "pension": entry.pension,
                "medical": entry.medical,
                "unemployment": entry.unemployment,
            }
        ending_confirmed = confirmed_months + len(months)
    if (
        subsidy_assessment is not None
        and subsidy_assessment.status is EligibilityStatus.ELIGIBLE
        and any(
            action.action_type is ActionType.APPLY_FOR_SUBSIDY
            for action in actions
        )
    ):
        for month in months:
            if (
                subsidy_assessment.start_month is not None
                and subsidy_assessment.end_month is not None
                and subsidy_assessment.monthly_subsidy is not None
                and subsidy_assessment.start_month
                <= month
                <= subsidy_assessment.end_month
            ):
                subsidies[month] = subsidy_assessment.monthly_subsidy

    flows = build_monthly_cash_flows(months, contributions, subsidies)
    totals = {
        name: sum(
            (getattr(flow, name).amount for flow in flows), Decimal("0.00")
        )
        for name in (
            "pension",
            "medical",
            "unemployment",
            "subsidy",
            "net_outflow",
        )
    }
    outcomes = ScenarioOutcome(
        ending_confirmed_months=ending_confirmed,
        ending_gap_months=max(requirement_months - ending_confirmed, 0),
        total_pension=Money(totals["pension"], CNY),
        total_medical=Money(totals["medical"], CNY),
        total_unemployment=Money(totals["unemployment"], CNY),
        total_subsidy=Money(totals["subsidy"], CNY),
        total_net_outflow=Money(totals["net_outflow"], CNY),
    )
    return Scenario(
        scenario_id=scenario_id,
        feasibility=ScenarioFeasibility.FEASIBLE,
        capability_refs=tuple(capability_refs),
        horizon=horizon,
        actions=tuple(actions),
        monthly_cash_flows=flows,
        outcomes=outcomes,
        thresholds=tuple(thresholds),
        sensitivity=dict(sensitivity or {}),
    )


def rank_scenarios(
    scenarios: Iterable[Scenario],
    objective: str = "MINIMUM_COMPLIANCE_COST",
) -> tuple[Scenario, ...]:
    """Deterministically rank scenarios for the objective.

    Feasible scenarios are preferred over infeasible ones; among equally
    feasible scenarios the ranking prefers closing the contribution gap
    (lower remaining gap) and then lower total net outflow. The scenario_id
    breaks ties so the ranking is total and stable.
    """
    ranked = sorted(
        scenarios,
        key=lambda scenario: (
            scenario.feasibility is ScenarioFeasibility.INFEASIBLE,
            scenario.outcomes.ending_gap_months,
            scenario.outcomes.total_net_outflow.amount,
            scenario.scenario_id,
        ),
    )
    if objective not in ("MINIMUM_COMPLIANCE_COST",):
        raise DomainValidationError(f"unsupported objective {objective!r}")
    return tuple(ranked)


def select_recommended(
    ranked: Sequence[Scenario],
) -> Scenario:
    """Return the top feasible scenario; raise when none is feasible."""
    feasible = [
        scenario
        for scenario in ranked
        if scenario.feasibility is ScenarioFeasibility.FEASIBLE
    ]
    if not feasible:
        raise ScenarioGenerationError("no feasible scenario to recommend")
    return feasible[0]
