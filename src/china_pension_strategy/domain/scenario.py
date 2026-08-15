"""Monthly scenario generation and deterministic ranking artifacts."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping, TypeVar

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.values import Money, YearMonth, YearMonthRange

T = TypeVar("T")


def _tuple(values: Iterable[T], field_name: str) -> tuple[T, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise DomainValidationError(f"{field_name} must be a collection")
    try:
        return tuple(values)
    except TypeError as error:
        raise DomainValidationError(f"{field_name} must be a collection") from error


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string")


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        _require_text(value, field_name)
    if len(values) != len(set(values)):
        raise DomainValidationError(f"{field_name} cannot contain duplicates")


class ScenarioFeasibility(str, Enum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"


class ActionType(str, Enum):
    CONTINUE_CONTRIBUTING = "CONTINUE_CONTRIBUTING"
    STOP_CONTRIBUTING = "STOP_CONTRIBUTING"
    APPLY_FOR_SUBSIDY = "APPLY_FOR_SUBSIDY"


@dataclass(frozen=True)
class ScenarioAction:
    month: YearMonth
    action_type: ActionType
    assumption_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.month, YearMonth):
            raise DomainValidationError("month must be a YearMonth")
        if not isinstance(self.action_type, ActionType):
            raise DomainValidationError("action_type must be an ActionType")
        object.__setattr__(
            self, "assumption_refs", _tuple(self.assumption_refs, "assumption_refs")
        )
        _require_unique(self.assumption_refs, "assumption_refs")


@dataclass(frozen=True)
class CashFlow:
    month: YearMonth
    pension: Money
    medical: Money
    unemployment: Money
    subsidy: Money
    net_outflow: Money
    cumulative_outflow: Money

    def __post_init__(self) -> None:
        if not isinstance(self.month, YearMonth):
            raise DomainValidationError("month must be a YearMonth")
        for field_name in (
            "pension",
            "medical",
            "unemployment",
            "subsidy",
            "net_outflow",
            "cumulative_outflow",
        ):
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
class ScenarioOutcome:
    ending_confirmed_months: int
    ending_gap_months: int
    total_pension: Money
    total_medical: Money
    total_unemployment: Money
    total_subsidy: Money
    total_net_outflow: Money

    def __post_init__(self) -> None:
        for field_name in ("ending_confirmed_months", "ending_gap_months"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DomainValidationError(
                    f"{field_name} must be a non-negative integer"
                )
        for field_name in (
            "total_pension",
            "total_medical",
            "total_unemployment",
            "total_subsidy",
            "total_net_outflow",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Money) or value.amount < 0:
                raise DomainValidationError(f"{field_name} must be a non-negative Money")


@dataclass(frozen=True)
class Threshold:
    threshold_id: str
    metric: str
    operator: str
    value: Decimal

    def __post_init__(self) -> None:
        _require_text(self.threshold_id, "threshold_id")
        _require_text(self.metric, "metric")
        if self.operator not in ("<", "<=", ">", ">=", "=", "!="):
            raise DomainValidationError("threshold operator is not supported")
        if not isinstance(self.value, Decimal):
            raise DomainValidationError("threshold value must be a Decimal")


@dataclass(frozen=True)
class Assumption:
    assumption_id: str
    event_definition: str
    source_type: str
    modeling_mode: str
    source_date: date
    population: str
    provenance_refs: tuple[str, ...]
    approved_by: str
    expires_at: datetime
    dependency_treatment: str
    distribution: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "assumption_id",
            "event_definition",
            "source_type",
            "modeling_mode",
            "population",
            "approved_by",
            "dependency_treatment",
        ):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.source_date, date) or isinstance(
            self.source_date, datetime
        ):
            raise DomainValidationError("source_date must be a date")
        if not isinstance(self.expires_at, datetime) or self.expires_at.tzinfo is None:
            raise DomainValidationError("expires_at must be a timezone-aware datetime")
        object.__setattr__(
            self, "provenance_refs", _tuple(self.provenance_refs, "provenance_refs")
        )
        _require_unique(self.provenance_refs, "provenance_refs")
        if self.distribution is not None and not isinstance(
            self.distribution, Mapping
        ):
            raise DomainValidationError("distribution must be a mapping or None")


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    feasibility: ScenarioFeasibility
    capability_refs: tuple[str, ...]
    horizon: YearMonthRange
    actions: tuple[ScenarioAction, ...]
    monthly_cash_flows: tuple[CashFlow, ...]
    outcomes: ScenarioOutcome
    thresholds: tuple[Threshold, ...]
    sensitivity: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.scenario_id, "scenario_id")
        if not isinstance(self.feasibility, ScenarioFeasibility):
            raise DomainValidationError("feasibility must be a ScenarioFeasibility")
        object.__setattr__(
            self, "capability_refs", _tuple(self.capability_refs, "capability_refs")
        )
        _require_unique(self.capability_refs, "capability_refs")
        if not isinstance(self.horizon, YearMonthRange):
            raise DomainValidationError("horizon must be a YearMonthRange")
        object.__setattr__(self, "actions", _tuple(self.actions, "actions"))
        object.__setattr__(
            self,
            "monthly_cash_flows",
            _tuple(self.monthly_cash_flows, "monthly_cash_flows"),
        )
        object.__setattr__(self, "thresholds", _tuple(self.thresholds, "thresholds"))
        if not isinstance(self.sensitivity, Mapping):
            raise DomainValidationError("sensitivity must be a mapping")
        if not all(
            isinstance(flow, CashFlow) for flow in self.monthly_cash_flows
        ):
            raise DomainValidationError(
                "monthly_cash_flows must contain CashFlow values"
            )
        if not all(
            isinstance(action, ScenarioAction) for action in self.actions
        ):
            raise DomainValidationError("actions must contain ScenarioAction values")
        if not all(isinstance(threshold, Threshold) for threshold in self.thresholds):
            raise DomainValidationError("thresholds must contain Threshold values")
        if self.feasibility is ScenarioFeasibility.FEASIBLE and not self.monthly_cash_flows:
            raise DomainValidationError("FEASIBLE scenarios require cash flows")
        if self.monthly_cash_flows:
            months = tuple(flow.month for flow in self.monthly_cash_flows)
            if months != tuple(self.horizon):
                raise DomainValidationError(
                    "cash flow months must exactly match the horizon"
                )


@dataclass(frozen=True)
class Recommendation:
    scenario_id: str
    objective: str
    capability_dependencies: tuple[Mapping[str, object], ...]
    assumption_refs: tuple[str, ...]
    limitations: tuple[str, ...]
    thresholds: tuple[str, ...]
    invalidators: tuple[str, ...]
    review_triggers: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.scenario_id, "scenario_id")
        _require_text(self.objective, "objective")
        object.__setattr__(
            self,
            "capability_dependencies",
            _tuple(self.capability_dependencies, "capability_dependencies"),
        )
        for field_name in (
            "assumption_refs",
            "limitations",
            "thresholds",
            "invalidators",
            "review_triggers",
        ):
            values = _tuple(getattr(self, field_name), field_name)
            _require_unique(values, field_name)
            object.__setattr__(self, field_name, values)
        if not self.limitations:
            raise DomainValidationError("recommendations require limitations")
