"""Base-limits out-of-range warnings are non-blocking and value-preserving.

The engine does not clamp or reject an out-of-range declared contribution
base; it warns in the envelope while keeping numeric output (and therefore
run ids) unchanged.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from china_pension_strategy.application.analyze import _base_limits_warnings
from china_pension_strategy.domain.policy import (
    AnalysisMode,
    PolicyPackage,
    PolicyRule,
    RuleType,
)


def _rule(
    rule_id: str,
    parameters: dict[str, object],
    topic: str = "flexible_employment_contribution",
) -> PolicyRule:
    from china_pension_strategy.domain.policy import JurisdictionRole, LegalHierarchy

    return PolicyRule(
        rule_id=rule_id,
        rule_type=RuleType.POLICY_RULE,
        scheme="enterprise_employee_basic_pension",
        topic=topic,
        jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
        population_scope="test participants",
        exceptions=(),
        effective_from=date(2025, 1, 1),
        effective_to=None,
        transaction_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        transaction_to=None,
        legal_hierarchy=LegalHierarchy.MUNICIPAL_REGULATION,
        explicit_override_refs=(),
        source_refs=("test-source",),
        inputs=(
            {"input_id": "contribution_base", "value_type": "DECIMAL", "required": True},
        ),
        conditions=(
            {"condition_id": "always", "input_ref": "contribution_base", "operator": ">=", "value_type": "DECIMAL", "value": Decimal("0.00")},
        ),
        results=(
            {
                "result_id": "out",
                "output_field": "monthly_pension_contribution",
                "value_type": "DECIMAL",
                "value": {"kind": "LITERAL", "value_type": "DECIMAL", "value": Decimal("0.00")},
            },
        ),
        parameters=parameters,
        test_vectors=(
            {
                "vector_id": "v1",
                "input": {"contribution_base": Decimal("10000.00")},
                "expected": {"monthly_pension_contribution": Decimal("0.00")},
            },
        ),
    )


def _package(rule: PolicyRule, topic: str = "flexible_employment_contribution") -> PolicyPackage:
    from china_pension_strategy.domain.policy import (
        EngineeringReview,
        PolicySource,
        ReviewStatus,
    )

    return PolicyPackage(
        schema_version="1.0.0",
        package_id="cn-pension/test/flex-employment-2026.1",
        version="1.0.0",
        scheme="enterprise_employee_basic_pension",
        jurisdiction="CN-XX",
        topic=topic,
        review_status=ReviewStatus.MVP_REVIEWED,
        execution_modes=(AnalysisMode("LOCAL_MVP"),),
        local_only=True,
        engine_compatibility=">=0.1,<1.0",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        transaction_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        transaction_to=None,
        content_digest="sha256:" + "a" * 64,
        provenance=(
            PolicySource(
                source_id="test-source",
                url="https://www.gov.cn/test",
                issuing_authority="test",
                authority_level="MUNICIPAL_HRSS",
                document_number=None,
                publication_date=date(2025, 1, 1),
                retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                locator="test",
                source_digest="sha256:" + "a" * 64,
            ),
        ),
        rules=(rule,),
        engineering_review=EngineeringReview(
            reviewer_id="test",
            reviewed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            schema_validation_passed=True,
            rule_tests_passed=True,
        ),
        production_approval=None,
    )


PENSION_LIMITS = {
    "base_floor": {"value_type": "DECIMAL", "value": Decimal("5000.00")},
    "base_ceiling": {"value_type": "DECIMAL", "value": Decimal("25000.00")},
}


def test_no_base_no_warning() -> None:
    rule = _rule("test-flex-base-limits", PENSION_LIMITS)
    package = _package(rule)
    assert _base_limits_warnings((package,), None) == ()


def test_within_limits_no_warning() -> None:
    rule = _rule("test-flex-base-limits", PENSION_LIMITS)
    package = _package(rule)
    assert _base_limits_warnings((package,), Decimal("10000.00")) == ()


def test_boundary_values_no_warning() -> None:
    rule = _rule("test-flex-base-limits", PENSION_LIMITS)
    package = _package(rule)
    assert _base_limits_warnings((package,), Decimal("5000.00")) == ()
    assert _base_limits_warnings((package,), Decimal("25000.00")) == ()


def test_below_floor_warns() -> None:
    rule = _rule("test-flex-base-limits", PENSION_LIMITS)
    package = _package(rule)
    warnings = _base_limits_warnings((package,), Decimal("4500.00"))
    assert len(warnings) == 1
    assert "CONTRIBUTION_BASE_BELOW_FLOOR" in warnings[0]
    assert "5000.00" in warnings[0]


def test_above_ceiling_warns() -> None:
    rule = _rule("test-flex-base-limits", PENSION_LIMITS)
    package = _package(rule)
    warnings = _base_limits_warnings((package,), Decimal("26000.00"))
    assert len(warnings) == 1
    assert "CONTRIBUTION_BASE_ABOVE_CEILING" in warnings[0]


def test_medical_limits_warn() -> None:
    rule = _rule(
        "test-flex-base-limits",
        {
            **PENSION_LIMITS,
            "medical_base_floor": {"value_type": "DECIMAL", "value": Decimal("6727.00")},
            "medical_base_ceiling": {"value_type": "DECIMAL", "value": Decimal("33633.00")},
        },
    )
    package = _package(rule)
    # below medical floor but within pension floor/ceiling
    warnings = _base_limits_warnings((package,), Decimal("5500.00"))
    assert any("CONTRIBUTION_BASE_BELOW_MEDICAL_FLOOR" in w for w in warnings)
    # above medical ceiling
    warnings = _base_limits_warnings((package,), Decimal("40000.00"))
    assert any("CONTRIBUTION_BASE_ABOVE_MEDICAL_CEILING" in w for w in warnings)
    assert any("CONTRIBUTION_BASE_ABOVE_CEILING" in w for w in warnings)


def test_no_parameters_no_warning() -> None:
    rule = _rule("test-flex-base-limits", {})
    package = _package(rule)
    assert _base_limits_warnings((package,), Decimal("10000.00")) == ()


def test_non_contribution_topic_ignored() -> None:
    rule = _rule("test-subsidy-amount", {}, topic="flexible_employment_subsidy")
    package = _package(rule, topic="flexible_employment_subsidy")
    assert _base_limits_warnings((package,), Decimal("100.00")) == ()
