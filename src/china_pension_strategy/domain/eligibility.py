"""Capability and eligibility assessments with mechanical state derivation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, TypeVar

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.facts import FactReference


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class ConditionStatus(str, Enum):
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


T = TypeVar("T")


def _tuple(values: Iterable[T], field_name: str) -> tuple[T, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise DomainValidationError(f"{field_name} must be a collection")
    try:
        return tuple(values)
    except TypeError as error:
        raise DomainValidationError(f"{field_name} must be a collection") from error


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string")


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        _require_text(value, field_name)
    if len(values) != len(set(values)):
        raise DomainValidationError(f"{field_name} cannot contain duplicate IDs")


@dataclass(frozen=True)
class CapabilityAssessment:
    capability_id: str
    status: CapabilityStatus
    required_fact_ids: tuple[str, ...]
    satisfied_fact_ids: tuple[str, ...]
    missing_fact_ids: tuple[str, ...]
    blocker_codes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.capability_id, "capability_id")
        if not isinstance(self.status, CapabilityStatus):
            raise DomainValidationError("status must be a CapabilityStatus")

        for field_name in (
            "required_fact_ids",
            "satisfied_fact_ids",
            "missing_fact_ids",
            "blocker_codes",
            "limitations",
        ):
            object.__setattr__(
                self, field_name, _tuple(getattr(self, field_name), field_name)
            )

        for field_name in (
            "required_fact_ids",
            "satisfied_fact_ids",
            "missing_fact_ids",
            "blocker_codes",
        ):
            _require_unique(getattr(self, field_name), field_name)
        for limitation in self.limitations:
            _require_text(limitation, "limitations")

        required = set(self.required_fact_ids)
        satisfied = set(self.satisfied_fact_ids)
        missing = set(self.missing_fact_ids)
        if satisfied & missing or required != satisfied | missing:
            raise DomainValidationError(
                "satisfied and missing fact IDs must exactly partition required fact IDs"
            )

        if self.status is CapabilityStatus.AVAILABLE:
            if missing or self.blocker_codes:
                raise DomainValidationError(
                    "AVAILABLE requires every fact and cannot have blockers"
                )
        elif self.status is CapabilityStatus.PARTIAL:
            if not self.limitations:
                raise DomainValidationError(
                    "PARTIAL requires at least one limitation"
                )
        elif not self.blocker_codes:
            raise DomainValidationError("BLOCKED requires at least one blocker code")


@dataclass(frozen=True)
class ConditionAssessment:
    condition_id: str
    status: ConditionStatus
    fact_refs: tuple[FactReference, ...]
    rule_refs: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        _require_text(self.condition_id, "condition_id")
        _require_text(self.explanation, "explanation")
        if not isinstance(self.status, ConditionStatus):
            raise DomainValidationError("status must be a ConditionStatus")
        object.__setattr__(self, "fact_refs", _tuple(self.fact_refs, "fact_refs"))
        object.__setattr__(self, "rule_refs", _tuple(self.rule_refs, "rule_refs"))
        if not all(isinstance(reference, FactReference) for reference in self.fact_refs):
            raise DomainValidationError("fact_refs must contain FactReference values")
        _require_unique(self.rule_refs, "rule_refs")


@dataclass(frozen=True)
class EligibilityAssessment:
    assessment_id: str
    capability_id: str
    subject_scope: str
    rule_ids: tuple[str, ...]
    conditions: tuple[ConditionAssessment, ...]
    status: EligibilityStatus = field(init=False)

    def __post_init__(self) -> None:
        _require_text(self.assessment_id, "assessment_id")
        _require_text(self.capability_id, "capability_id")
        _require_text(self.subject_scope, "subject_scope")
        object.__setattr__(self, "rule_ids", _tuple(self.rule_ids, "rule_ids"))
        object.__setattr__(
            self, "conditions", _tuple(self.conditions, "conditions")
        )
        _require_unique(self.rule_ids, "rule_ids")
        if not self.conditions:
            raise DomainValidationError("eligibility requires at least one condition")
        if not all(
            isinstance(condition, ConditionAssessment) for condition in self.conditions
        ):
            raise DomainValidationError(
                "conditions must contain ConditionAssessment values"
            )

        statuses = {condition.status for condition in self.conditions}
        if ConditionStatus.FAILED in statuses:
            status = EligibilityStatus.INELIGIBLE
        elif ConditionStatus.UNVERIFIED in statuses:
            status = EligibilityStatus.UNKNOWN
        else:
            status = EligibilityStatus.ELIGIBLE
        object.__setattr__(self, "status", status)
