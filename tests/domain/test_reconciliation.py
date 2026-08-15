from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from china_pension_strategy.application.reconcile_records import (
    ReconcileRequest,
    reconcile_contribution_records,
)
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.reconciliation import (
    ENTERPRISE_EMPLOYEE_BASIC_PENSION,
    AggregatedCount,
    ConflictStatus,
    ContributionMonth,
    ReconcileResult,
    RecordConflict,
)
from china_pension_strategy.domain.values import YearMonth

SCHEME = ENTERPRISE_EMPLOYEE_BASIC_PENSION


def month(year: int, month_number: int, source_id: str = "detail") -> ContributionMonth:
    return ContributionMonth(scheme=SCHEME, month=YearMonth(year, month_number), source_id=source_id)


def aggregate(reported: int, source_id: str = "account-summary") -> AggregatedCount:
    return AggregatedCount(scheme=SCHEME, reported_months=reported, source_id=source_id)


def months_span(start: int, end: int, source_id: str = "detail") -> tuple[ContributionMonth, ...]:
    year, month_number = divmod(start - 1, 12)
    current = YearMonth(year + 2000, month_number + 1)
    entries = []
    for offset in range(end - start + 1):
        entries.append(ContributionMonth(SCHEME, current, source_id))
        current = current.add_months(1)
    return tuple(entries)


def test_duplicate_month_is_counted_once_and_reported() -> None:
    entries = (
        month(2026, 1, "detail-a"),
        month(2026, 1, "detail-b"),
        month(2026, 2, "detail-a"),
    )
    result = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=entries)
    )
    assert result.confirmed_months == 2
    assert len(result.duplicates) == 1
    assert result.duplicates[0].month == YearMonth(2026, 1)
    assert result.duplicates[0].source_id == "detail-b"


def test_179_month_history_confirms_179() -> None:
    entries = months_span(1, 179)
    result = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=entries)
    )
    assert result.confirmed_months == 179
    assert not result.conflicts
    assert not result.duplicates


def test_180_month_history_confirms_180() -> None:
    entries = months_span(1, 180)
    result = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=entries)
    )
    assert result.confirmed_months == 180


def test_181_month_history_confirms_181() -> None:
    entries = months_span(1, 181)
    result = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=entries)
    )
    assert result.confirmed_months == 181


def test_aggregate_matching_detail_produces_no_conflict() -> None:
    entries = months_span(1, 179)
    result = reconcile_contribution_records(
        ReconcileRequest(
            scheme=SCHEME,
            month_entries=entries,
            aggregate_counts=(aggregate(179),),
        )
    )
    assert result.confirmed_months == 179
    assert not result.conflicts


def test_aggregate_200_versus_17y1m_detail_205_preserves_unresolved_conflict() -> None:
    entries = months_span(1, 205)
    result = reconcile_contribution_records(
        ReconcileRequest(
            scheme=SCHEME,
            month_entries=entries,
            aggregate_counts=(aggregate(200, "account-summary"),),
        )
    )
    assert result.confirmed_months == 205
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.status is ConflictStatus.UNRESOLVED
    assert conflict.fact_scope == f"{SCHEME} contribution months"
    assert conflict.assertion_refs[0] == "account-summary"
    assert conflict.assertion_refs[-1] == "detail"
    assert conflict.resolution_evidence_refs == ()


def test_competing_aggregates_both_conflict() -> None:
    result = reconcile_contribution_records(
        ReconcileRequest(
            scheme=SCHEME,
            month_entries=months_span(1, 200),
            aggregate_counts=(aggregate(200, "summary-a"), aggregate(205, "summary-b")),
        )
    )
    assert len(result.conflicts) == 2
    scopes = {conflict.fact_scope for conflict in result.conflicts}
    assert scopes == {f"{SCHEME} contribution months"}
    aggregate_conflict = next(
        conflict
        for conflict in result.conflicts
        if conflict.assertion_refs == ("summary-a", "summary-b")
    )
    assert aggregate_conflict.status is ConflictStatus.UNRESOLVED
    detail_conflict = next(
        conflict
        for conflict in result.conflicts
        if conflict.assertion_refs[0] == "summary-b"
    )
    assert "detail" in detail_conflict.assertion_refs


def test_matching_aggregates_do_not_conflict_with_each_other() -> None:
    result = reconcile_contribution_records(
        ReconcileRequest(
            scheme=SCHEME,
            month_entries=months_span(1, 200),
            aggregate_counts=(aggregate(200, "summary-a"), aggregate(200, "summary-b")),
        )
    )
    assert not result.conflicts
    assert result.confirmed_months == 200


def test_other_scheme_entries_are_excluded_and_tracked() -> None:
    resident = ContributionMonth(
        scheme="urban_rural_resident_basic_pension",
        month=YearMonth(2026, 1),
        source_id="resident-detail",
    )
    result = reconcile_contribution_records(
        ReconcileRequest(
            scheme=SCHEME,
            month_entries=(month(2026, 1, "detail"), resident),
        )
    )
    assert result.confirmed_months == 1
    assert result.other_scheme_entries == (resident,)


def test_other_scheme_aggregate_is_ignored() -> None:
    result = reconcile_contribution_records(
        ReconcileRequest(
            scheme=SCHEME,
            month_entries=(month(2026, 1),),
            aggregate_counts=(
                AggregatedCount(
                    scheme="urban_rural_resident_basic_pension",
                    reported_months=60,
                    source_id="resident-summary",
                ),
            ),
        )
    )
    assert result.confirmed_months == 1
    assert not result.conflicts


def test_empty_evidence_confirms_zero_without_conflicts() -> None:
    result = reconcile_contribution_records(ReconcileRequest(scheme=SCHEME))
    assert result.confirmed_months == 0
    assert not result.conflicts
    assert not result.duplicates


def test_result_requires_nonnegative_confirmed_months() -> None:
    with pytest.raises(DomainValidationError):
        ReconcileResult(
            scheme=SCHEME,
            confirmed_months=-1,
            duplicates=(),
            conflicts=(),
            other_scheme_entries=(),
        )


def test_conflict_requires_unique_nonempty_assertion_refs() -> None:
    with pytest.raises(DomainValidationError):
        RecordConflict(
            conflict_id="conflict-x",
            fact_scope="pension months",
            assertion_refs=(),
            status=ConflictStatus.UNRESOLVED,
        )
    with pytest.raises(DomainValidationError):
        RecordConflict(
            conflict_id="conflict-x",
            fact_scope="pension months",
            assertion_refs=("a", "a"),
            status=ConflictStatus.UNRESOLVED,
        )


def test_contribution_month_requires_YearMonth() -> None:
    with pytest.raises(DomainValidationError):
        ContributionMonth(scheme=SCHEME, month=date(2026, 1, 1), source_id="x")
    with pytest.raises(DomainValidationError):
        AggregatedCount(scheme=SCHEME, reported_months=-1, source_id="x")
    with pytest.raises(DomainValidationError):
        AggregatedCount(scheme=SCHEME, reported_months=1.5, source_id="x")


def test_request_rejects_wrong_entry_types() -> None:
    with pytest.raises(DomainValidationError):
        ReconcileRequest(scheme=SCHEME, month_entries=("not-a-month",))
    with pytest.raises(DomainValidationError):
        ReconcileRequest(scheme=SCHEME, aggregate_counts=(1, 2))


def _year_month() -> st.SearchStrategy[YearMonth]:
    return st.builds(
        YearMonth,
        year=st.integers(min_value=2000, max_value=2030),
        month=st.integers(min_value=1, max_value=12),
    )


@given(
    existing=st.lists(_year_month(), max_size=60),
    extra=st.lists(_year_month(), max_size=30),
)
@settings(max_examples=100)
def test_adding_unique_valid_month_never_reduces_confirmed_months(existing, extra) -> None:
    entries = [
        ContributionMonth(SCHEME, ym, f"source-{index}")
        for index, ym in enumerate(existing)
    ]
    before = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=entries)
    ).confirmed_months
    extra_entries = [
        ContributionMonth(SCHEME, ym, f"extra-{index}")
        for index, ym in enumerate(extra)
    ]
    after = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=(*entries, *extra_entries))
    ).confirmed_months
    assert after >= before


def test_duplicate_reconciliation_is_deterministic() -> None:
    entries = months_span(1, 179) + months_span(1, 60)
    first = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=entries)
    )
    second = reconcile_contribution_records(
        ReconcileRequest(scheme=SCHEME, month_entries=entries)
    )
    assert first == second
    assert first.confirmed_months == 179
