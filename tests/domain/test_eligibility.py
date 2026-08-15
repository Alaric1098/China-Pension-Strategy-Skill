from dataclasses import FrozenInstanceError

import pytest
from hypothesis import given
from hypothesis import strategies as st

from china_pension_strategy.domain.eligibility import (
    CapabilityAssessment,
    CapabilityStatus,
    ConditionAssessment,
    ConditionStatus,
    EligibilityAssessment,
    EligibilityStatus,
)
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.facts import FactReference


def test_fact_reference_is_immutable() -> None:
    reference = FactReference("fact-age")

    with pytest.raises(FrozenInstanceError):
        reference.fact_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "status, missing, blockers, limitations",
    [
        (CapabilityStatus.AVAILABLE, (), (), ()),
        (CapabilityStatus.PARTIAL, ("fact-detail",), (), ("Estimate only",)),
        (CapabilityStatus.BLOCKED, ("fact-age",), ("MISSING_AGE",), ()),
    ],
)
def test_capability_assessment_accepts_exact_requirement_partition(
    status: CapabilityStatus,
    missing: tuple[str, ...],
    blockers: tuple[str, ...],
    limitations: tuple[str, ...],
) -> None:
    assessment = CapabilityAssessment(
        capability_id="SUBSIDY_ELIGIBILITY",
        status=status,
        required_fact_ids=("fact-age", "fact-detail"),
        satisfied_fact_ids=tuple(
            fact_id
            for fact_id in ("fact-age", "fact-detail")
            if fact_id not in missing
        ),
        missing_fact_ids=missing,
        blocker_codes=blockers,
        limitations=limitations,
    )

    assert set(assessment.required_fact_ids) == set(
        assessment.satisfied_fact_ids + assessment.missing_fact_ids
    )


def test_partial_capability_allows_policy_uncertainty_without_missing_facts() -> None:
    assessment = CapabilityAssessment(
        capability_id="SUBSIDY_ELIGIBILITY",
        status=CapabilityStatus.PARTIAL,
        required_fact_ids=("fact-age",),
        satisfied_fact_ids=("fact-age",),
        missing_fact_ids=(),
        limitations=("Applicable policy is unresolved",),
    )

    assert assessment.status is CapabilityStatus.PARTIAL


@pytest.mark.parametrize(
    "satisfied, missing",
    [
        (("fact-age",), ("fact-age",)),
        (("fact-other",), ("fact-age",)),
        (("fact-age", "fact-age"), ()),
    ],
)
def test_capability_assessment_rejects_non_exact_partitions(
    satisfied: tuple[str, ...], missing: tuple[str, ...]
) -> None:
    with pytest.raises(DomainValidationError, match="partition|duplicate"):
        CapabilityAssessment(
            capability_id="CONTRIBUTION_GAP",
            status=CapabilityStatus.PARTIAL,
            required_fact_ids=("fact-age",),
            satisfied_fact_ids=satisfied,
            missing_fact_ids=missing,
            limitations=("Estimate only",),
        )


@pytest.mark.parametrize(
    "status, missing, blockers, limitations",
    [
        (CapabilityStatus.AVAILABLE, ("fact-age",), (), ()),
        (CapabilityStatus.AVAILABLE, (), ("CONFLICT",), ()),
        (CapabilityStatus.PARTIAL, ("fact-age",), (), ()),
        (CapabilityStatus.BLOCKED, ("fact-age",), (), ()),
    ],
)
def test_capability_state_invariants_are_enforced(
    status: CapabilityStatus,
    missing: tuple[str, ...],
    blockers: tuple[str, ...],
    limitations: tuple[str, ...],
) -> None:
    with pytest.raises(DomainValidationError):
        CapabilityAssessment(
            capability_id="CONTRIBUTION_GAP",
            status=status,
            required_fact_ids=("fact-age",),
            satisfied_fact_ids=() if missing else ("fact-age",),
            missing_fact_ids=missing,
            blocker_codes=blockers,
            limitations=limitations,
        )


def condition(status: ConditionStatus) -> ConditionAssessment:
    return ConditionAssessment(
        condition_id=f"condition-{status.value.lower()}",
        status=status,
        fact_refs=(FactReference("fact-age"),),
        rule_refs=("rule-age",),
        explanation="Safe explanation",
    )


@pytest.mark.parametrize("malformed", ["fact-age", b"fact-age", 42])
def test_capability_rejects_scalar_id_collections(malformed: object) -> None:
    with pytest.raises(DomainValidationError, match="collection"):
        CapabilityAssessment(
            capability_id="CONTRIBUTION_GAP",
            status=CapabilityStatus.AVAILABLE,
            required_fact_ids=malformed,  # type: ignore[arg-type]
            satisfied_fact_ids=(),
            missing_fact_ids=(),
        )


@pytest.mark.parametrize(
    "field_name, malformed",
    [
        ("fact_refs", "fact-age"),
        ("fact_refs", b"fact-age"),
        ("fact_refs", FactReference("fact-age")),
        ("rule_refs", "rule-age"),
        ("rule_refs", b"rule-age"),
        ("rule_refs", 42),
    ],
)
def test_condition_rejects_scalar_reference_collections(
    field_name: str, malformed: object
) -> None:
    arguments = {
        "condition_id": "condition-age",
        "status": ConditionStatus.SATISFIED,
        "fact_refs": (FactReference("fact-age"),),
        "rule_refs": ("rule-age",),
        "explanation": "Safe explanation",
    }
    arguments[field_name] = malformed

    with pytest.raises(DomainValidationError, match="collection"):
        ConditionAssessment(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name, malformed",
    [
        ("rule_ids", "rule-age"),
        ("rule_ids", b"rule-age"),
        ("rule_ids", 42),
        ("conditions", "condition-age"),
        ("conditions", b"condition-age"),
        ("conditions", condition(ConditionStatus.SATISFIED)),
    ],
)
def test_eligibility_rejects_scalar_collections(
    field_name: str, malformed: object
) -> None:
    arguments = {
        "assessment_id": "assessment-1",
        "capability_id": "SUBSIDY_ELIGIBILITY",
        "subject_scope": "person-1",
        "rule_ids": ("rule-age",),
        "conditions": (condition(ConditionStatus.SATISFIED),),
    }
    arguments[field_name] = malformed

    with pytest.raises(DomainValidationError, match="collection"):
        EligibilityAssessment(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "statuses, expected",
    [
        ((ConditionStatus.SATISFIED,), EligibilityStatus.ELIGIBLE),
        (
            (ConditionStatus.SATISFIED, ConditionStatus.UNVERIFIED),
            EligibilityStatus.UNKNOWN,
        ),
        (
            (ConditionStatus.FAILED, ConditionStatus.UNVERIFIED),
            EligibilityStatus.INELIGIBLE,
        ),
    ],
)
def test_eligibility_status_is_mechanically_derived(
    statuses: tuple[ConditionStatus, ...], expected: EligibilityStatus
) -> None:
    assessment = EligibilityAssessment(
        assessment_id="assessment-1",
        capability_id="SUBSIDY_ELIGIBILITY",
        subject_scope="person-1",
        rule_ids=("rule-age",),
        conditions=tuple(condition(status) for status in statuses),
    )

    assert assessment.status is expected


@given(
    statuses=st.lists(
        st.sampled_from(tuple(ConditionStatus)), min_size=1, max_size=20
    )
)
def test_eligibility_derivation_property(statuses: list[ConditionStatus]) -> None:
    assessment = EligibilityAssessment(
        assessment_id="assessment-property",
        capability_id="SUBSIDY_ELIGIBILITY",
        subject_scope="person-1",
        rule_ids=("rule-age",),
        conditions=tuple(condition(status) for status in statuses),
    )

    if ConditionStatus.FAILED in statuses:
        expected = EligibilityStatus.INELIGIBLE
    elif ConditionStatus.UNVERIFIED in statuses:
        expected = EligibilityStatus.UNKNOWN
    else:
        expected = EligibilityStatus.ELIGIBLE

    assert assessment.status is expected


def test_eligibility_requires_at_least_one_condition() -> None:
    with pytest.raises(DomainValidationError, match="condition"):
        EligibilityAssessment(
            assessment_id="assessment-1",
            capability_id="SUBSIDY_ELIGIBILITY",
            subject_scope="person-1",
            rule_ids=("rule-age",),
            conditions=(),
        )
