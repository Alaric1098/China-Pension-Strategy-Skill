"""Deterministic reconciliation use case over contribution evidence."""

from dataclasses import dataclass

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.reconciliation import (
    AggregatedCount,
    ConflictStatus,
    ContributionMonth,
    ReconcileResult,
    RecordConflict,
)
from china_pension_strategy.domain.values import YearMonth


@dataclass(frozen=True)
class ReconcileRequest:
    """All evidence available for one reconciliation run."""

    scheme: str
    month_entries: tuple[ContributionMonth, ...] = ()
    aggregate_counts: tuple[AggregatedCount, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scheme, str) or not self.scheme.strip():
            raise DomainValidationError("scheme must be a non-empty string")
        if not all(isinstance(entry, ContributionMonth) for entry in self.month_entries):
            raise DomainValidationError("month_entries must contain ContributionMonth values")
        if not all(isinstance(count, AggregatedCount) for count in self.aggregate_counts):
            raise DomainValidationError("aggregate_counts must contain AggregatedCount values")


def reconcile_contribution_records(
    request: ReconcileRequest,
) -> ReconcileResult:
    """Reconcile evidence into confirmed months without resolving conflicts.

    Duplicate month entries for the reconciled scheme are counted once and
    reported; aggregate counts that disagree with the detail-derived count
    or with each other become UNRESOLVED conflicts; entries for other
    schemes are excluded and reported separately.
    """
    scheme = request.scheme
    own_entries = [entry for entry in request.month_entries if entry.scheme == scheme]
    other_entries = [entry for entry in request.month_entries if entry.scheme != scheme]
    aggregates = [count for count in request.aggregate_counts if count.scheme == scheme]

    detail_count = len({entry.month for entry in own_entries})
    conflicts: list[RecordConflict] = []

    detail_assertion_refs = sorted({entry.source_id for entry in own_entries})
    for index, count in enumerate(aggregates):
        if count.reported_months != detail_count:
            conflicts.append(
                RecordConflict(
                    conflict_id=f"conflict-aggregate-detail-{index}",
                    fact_scope=f"{scheme} contribution months",
                    assertion_refs=tuple(dict.fromkeys([count.source_id, *detail_assertion_refs])),
                    status=ConflictStatus.UNRESOLVED,
                )
            )
    for left_index, left in enumerate(aggregates):
        for right in aggregates[left_index + 1 :]:
            if left.reported_months != right.reported_months:
                conflicts.append(
                    RecordConflict(
                        conflict_id=(f"conflict-aggregate-vs-aggregate-{left_index}"),
                        fact_scope=f"{scheme} contribution months",
                        assertion_refs=(left.source_id, right.source_id),
                        status=ConflictStatus.UNRESOLVED,
                    )
                )

    seen_months: set[YearMonth] = set()
    duplicates: list[ContributionMonth] = []
    for entry in own_entries:
        if entry.month in seen_months:
            duplicates.append(entry)
        else:
            seen_months.add(entry.month)

    return ReconcileResult(
        scheme=scheme,
        confirmed_months=detail_count,
        duplicates=tuple(duplicates),
        conflicts=tuple(conflicts),
        other_scheme_entries=tuple(other_entries),
    )
