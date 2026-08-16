"""Pure reconciliation of contribution evidence into confirmed months."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.values import YearMonth

ENTERPRISE_EMPLOYEE_BASIC_PENSION = "enterprise_employee_basic_pension"


def _tuple[T](values: Iterable[T], field_name: str) -> tuple[T, ...]:
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


class ConflictStatus(StrEnum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class ContributionMonth:
    """One evidence entry that a month was contributed for a scheme."""

    scheme: str
    month: YearMonth
    source_id: str

    def __post_init__(self) -> None:
        _require_text(self.scheme, "scheme")
        _require_text(self.source_id, "source_id")
        if not isinstance(self.month, YearMonth):
            raise DomainValidationError("month must be a YearMonth")


@dataclass(frozen=True)
class AggregatedCount:
    """Aggregate month count reported for a scheme by one source."""

    scheme: str
    reported_months: int
    source_id: str

    def __post_init__(self) -> None:
        _require_text(self.scheme, "scheme")
        _require_text(self.source_id, "source_id")
        if isinstance(self.reported_months, bool) or not isinstance(self.reported_months, int):
            raise DomainValidationError("reported_months must be a non-negative integer")
        if self.reported_months < 0:
            raise DomainValidationError("reported_months must be a non-negative integer")


@dataclass(frozen=True)
class RecordConflict:
    """Competing evidence that cannot be resolved automatically."""

    conflict_id: str
    fact_scope: str
    assertion_refs: tuple[str, ...]
    status: ConflictStatus
    resolution_evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.conflict_id, "conflict_id")
        _require_text(self.fact_scope, "fact_scope")
        object.__setattr__(self, "assertion_refs", _tuple(self.assertion_refs, "assertion_refs"))
        object.__setattr__(
            self,
            "resolution_evidence_refs",
            _tuple(self.resolution_evidence_refs, "resolution_evidence_refs"),
        )
        _require_unique(self.assertion_refs, "assertion_refs")
        if not self.assertion_refs:
            raise DomainValidationError("assertion_refs cannot be empty")
        _require_unique(self.resolution_evidence_refs, "resolution_evidence_refs")
        if not isinstance(self.status, ConflictStatus):
            raise DomainValidationError("status must be a ConflictStatus")


@dataclass(frozen=True)
class ReconcileResult:
    """Confirmed months plus all unresolved evidence issues."""

    scheme: str
    confirmed_months: int
    duplicates: tuple[ContributionMonth, ...]
    conflicts: tuple[RecordConflict, ...]
    other_scheme_entries: tuple[ContributionMonth, ...]

    def __post_init__(self) -> None:
        _require_text(self.scheme, "scheme")
        if isinstance(self.confirmed_months, bool) or not isinstance(self.confirmed_months, int):
            raise DomainValidationError("confirmed_months must be an integer")
        if self.confirmed_months < 0:
            raise DomainValidationError("confirmed_months cannot be negative")
        object.__setattr__(self, "duplicates", _tuple(self.duplicates, "duplicates"))
        object.__setattr__(self, "conflicts", _tuple(self.conflicts, "conflicts"))
        object.__setattr__(
            self,
            "other_scheme_entries",
            _tuple(self.other_scheme_entries, "other_scheme_entries"),
        )
        if not all(isinstance(entry, ContributionMonth) for entry in self.duplicates):
            raise DomainValidationError("duplicates must contain ContributionMonth values")
        if not all(isinstance(conflict, RecordConflict) for conflict in self.conflicts):
            raise DomainValidationError("conflicts must contain RecordConflict values")
        if not all(isinstance(entry, ContributionMonth) for entry in self.other_scheme_entries):
            raise DomainValidationError(
                "other_scheme_entries must contain ContributionMonth values"
            )
        conflict_ids = [conflict.conflict_id for conflict in self.conflicts]
        if len(conflict_ids) != len(set(conflict_ids)):
            raise DomainValidationError("conflict IDs must be unique")
        for conflict in self.conflicts:
            if conflict.status is not ConflictStatus.UNRESOLVED:
                raise DomainValidationError("reconciliation cannot produce resolved conflicts")
