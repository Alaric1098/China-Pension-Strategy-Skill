"""Tests for the composition use case in application.analyze."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from china_pension_strategy.application.analyze import (
    AnalysisRequest,
    AnalysisRequestError,
    analyze,
    content_digest,
)
from china_pension_strategy.application.resolve_policy import (
    PolicyQuery,
    PolicyVersionNotFoundError,
)
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import (
    AnalysisMode,
    EngineeringReview,
    JurisdictionRole,
    LegalHierarchy,
    PolicyPackage,
    PolicyRule,
    PolicySource,
    ReviewStatus,
    RuleType,
)
from china_pension_strategy.domain.reconciliation import (
    AggregatedCount,
    ContributionMonth,
)
from china_pension_strategy.domain.values import YearMonth

KNOWN_AT = datetime(2026, 8, 11, tzinfo=timezone.utc)
AS_OF = date(2026, 8, 11)
ENGINE = "0.1.0"


def make_source() -> PolicySource:
    return PolicySource(
        source_id="source-a",
        url="https://www.gov.cn/synthetic",
        issuing_authority="Synthetic authority",
        authority_level="NATIONAL_GOVERNMENT",
        document_number="Synthetic-1",
        publication_date=date(2025, 1, 1),
        retrieved_at=KNOWN_AT,
        locator="Article 1",
        source_digest="sha256:" + "a" * 64,
    )


def contribution_rule(rule_id: str, field: str) -> PolicyRule:
    return PolicyRule(
        rule_id=rule_id,
        rule_type=RuleType.POLICY_RULE,
        scheme="enterprise_employee_basic_pension",
        topic="flexible_employment_contribution",
        jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
        population_scope="beijing flexible employment participants",
        inputs=(
            {"input_id": "contribution_base", "value_type": "DECIMAL", "required": True},
        ),
        conditions=(
            {
                "condition_id": "positive",
                "input_ref": "contribution_base",
                "operator": ">",
                "value_type": "DECIMAL",
                "value": Decimal("0.00"),
            },
        ),
        results=(
            {
                "result_id": "amount",
                "output_field": f"monthly_{field}_contribution",
                "value_type": "DECIMAL",
                "value": {"kind": "LITERAL", "value_type": "DECIMAL", "value": Decimal("100.00")},
            },
        ),
        exceptions=(),
        effective_from=date(2026, 1, 1),
        effective_to=None,
        transaction_from=KNOWN_AT,
        transaction_to=None,
        legal_hierarchy=LegalHierarchy.MUNICIPAL_REGULATION,
        explicit_override_refs=(),
        source_refs=("source-a",),
        parameters={},
        test_vectors=(
            {
                "vector_id": "v1",
                "input": {"contribution_base": Decimal("7000.00")},
                "expected": {f"monthly_{field}_contribution": Decimal("100.00")},
            },
        ),
    )


def minimum_rule() -> PolicyRule:
    return PolicyRule(
        rule_id="national-minimum-180-months",
        rule_type=RuleType.POLICY_RULE,
        scheme="enterprise_employee_basic_pension",
        topic="minimum_contribution",
        jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
        population_scope="enterprise participants",
        inputs=({"input_id": "confirmed_months", "value_type": "INTEGER", "required": True},),
        conditions=(
            {
                "condition_id": "nonnegative",
                "input_ref": "confirmed_months",
                "operator": ">=",
                "value_type": "INTEGER",
                "value": 0,
            },
        ),
        results=(
            {
                "result_id": "minimum",
                "output_field": "minimum_months",
                "value_type": "INTEGER",
                "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 180},
            },
        ),
        exceptions=(),
        effective_from=date(2025, 1, 1),
        effective_to=None,
        transaction_from=KNOWN_AT,
        transaction_to=None,
        legal_hierarchy=LegalHierarchy.NATIONAL_LAW,
        explicit_override_refs=(),
        source_refs=("source-a",),
        parameters={},
        test_vectors=(
            {
                "vector_id": "v1",
                "input": {"confirmed_months": 179},
                "expected": {"minimum_months": 180},
            },
        ),
    )


def subsidy_rule() -> PolicyRule:
    return PolicyRule(
        rule_id="beijing-subsidy-eligibility",
        rule_type=RuleType.POLICY_RULE,
        scheme="enterprise_employee_basic_pension",
        topic="flexible_employment_subsidy",
        jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
        population_scope="beijing employment-difficulty flexible employment participants",
        inputs=(
            {"input_id": "employment_difficulty_recognized", "value_type": "BOOLEAN", "required": True},
        ),
        conditions=(
            {
                "condition_id": "recognized",
                "input_ref": "employment_difficulty_recognized",
                "operator": "=",
                "value_type": "BOOLEAN",
                "value": True,
            },
        ),
        results=(
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
                "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 0},
            },
            {
                "result_id": "amount",
                "output_field": "monthly_subsidy_pension",
                "value_type": "DECIMAL",
                "value": {"kind": "LITERAL", "value_type": "DECIMAL", "value": Decimal("50.00")},
            },
        ),
        exceptions=(),
        effective_from=date(2026, 1, 1),
        effective_to=None,
        transaction_from=KNOWN_AT,
        transaction_to=None,
        legal_hierarchy=LegalHierarchy.MUNICIPAL_REGULATION,
        explicit_override_refs=(),
        source_refs=("source-a",),
        parameters={},
        test_vectors=(
            {
                "vector_id": "v1",
                "input": {"employment_difficulty_recognized": True},
                "expected": {
                    "subsidy_eligible": True,
                    "subsidy_duration_months": 36,
                    "subsidy_start_offset_months": 0,
                    "monthly_subsidy_pension": Decimal("50.00"),
                },
            },
        ),
    )


def make_package(rule: PolicyRule, topic: str, jurisdiction: str = "CN-11") -> PolicyPackage:
    return PolicyPackage(
        schema_version="1.0.0",
        package_id=f"package-{rule.rule_id}",
        version="1.0.0",
        scheme="enterprise_employee_basic_pension",
        jurisdiction=jurisdiction,
        topic=topic,
        review_status=ReviewStatus.MVP_REVIEWED,
        execution_modes=(AnalysisMode.LOCAL_MVP,),
        local_only=True,
        engine_compatibility=">=0.1,<1.0",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        transaction_from=KNOWN_AT,
        transaction_to=None,
        content_digest="sha256:" + "c" * 64,
        provenance=(make_source(),),
        rules=(rule,),
        engineering_review=EngineeringReview(
            reviewer_id="engineer-a",
            reviewed_at=KNOWN_AT,
            schema_validation_passed=True,
            rule_tests_passed=True,
        ),
        production_approval=None,
    )


class MemoryPolicyRepository:
    def __init__(self, *packages: PolicyPackage) -> None:
        self._packages = packages

    def list_packages(self):
        return self._packages


class MemoryRunRepository:
    def __init__(self) -> None:
        self.saved: list = []

    def save(self, run) -> None:
        self.saved.append(run)

    def load(self, run_id: str):
        for run in self.saved:
            if run.run_id == run_id:
                return run
        raise LookupError(run_id)

    def exists(self, run_id: str) -> bool:
        return any(run.run_id == run_id for run in self.saved)


class FixedClock:
    def __init__(self, instant: datetime = KNOWN_AT) -> None:
        self.instant = instant

    def now_utc(self) -> datetime:
        return self.instant


def policy_repository() -> MemoryPolicyRepository:
    return MemoryPolicyRepository(
        make_package(minimum_rule(), "minimum_contribution", jurisdiction="CN"),
        make_package(contribution_rule("pension-rule", "pension"), "flexible_employment_contribution"),
        make_package(contribution_rule("medical-rule", "medical"), "flexible_employment_contribution"),
        make_package(contribution_rule("unemployment-rule", "unemployment"), "flexible_employment_contribution"),
        make_package(subsidy_rule(), "flexible_employment_subsidy"),
    )


def base_request(**overrides) -> AnalysisRequest:
    values = dict(
        case_id="case-001",
        scheme="enterprise_employee_basic_pension",
        jurisdiction="CN-11",
        population_scope="enterprise participants",
        as_of_effective_date=AS_OF,
        as_known_at=KNOWN_AT,
        engine_version=ENGINE,
        analysis_mode=AnalysisMode.LOCAL_MVP,
        policy_queries=(
            PolicyQuery(
                scheme="enterprise_employee_basic_pension",
                topic="minimum_contribution",
                jurisdiction="CN",
                jurisdiction_role=JurisdictionRole.NATIONAL_BASELINE,
                population_scope="enterprise participants",
                as_of_effective_date=AS_OF,
                as_known_at=KNOWN_AT,
                engine_version=ENGINE,
                analysis_mode=AnalysisMode.LOCAL_MVP,
            ),
            PolicyQuery(
                scheme="enterprise_employee_basic_pension",
                topic="flexible_employment_contribution",
                jurisdiction="CN-11",
                jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
                population_scope="beijing flexible employment participants",
                as_of_effective_date=AS_OF,
                as_known_at=KNOWN_AT,
                engine_version=ENGINE,
                analysis_mode=AnalysisMode.LOCAL_MVP,
            ),
            PolicyQuery(
                scheme="enterprise_employee_basic_pension",
                topic="flexible_employment_subsidy",
                jurisdiction="CN-11",
                jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
                population_scope="beijing employment-difficulty flexible employment participants",
                as_of_effective_date=AS_OF,
                as_known_at=KNOWN_AT,
                engine_version=ENGINE,
                analysis_mode=AnalysisMode.LOCAL_MVP,
            ),
        ),
        month_entries=(
            ContributionMonth(
                scheme="enterprise_employee_basic_pension",
                month=YearMonth(2026, 7),
                source_id="social-security-statement",
            ),
            ContributionMonth(
                scheme="enterprise_employee_basic_pension",
                month=YearMonth(2026, 6),
                source_id="social-security-statement",
            ),
        ),
        aggregate_counts=(
            AggregatedCount(
                scheme="enterprise_employee_basic_pension",
                reported_months=2,
                source_id="social-security-statement",
            ),
        ),
        contribution_base=Decimal("7000.00"),
        subsidy_inputs={"employment_difficulty_recognized": True},
        requested_capabilities=(
            "CONTRIBUTION_RECONCILIATION",
            "CONTRIBUTION_GAP",
            "FLEXIBLE_EMPLOYMENT_CONTRIBUTION",
            "SUBSIDY_ELIGIBILITY",
            "SUBSIDY_TIMING",
            "SCENARIO_COMPARISON",
            "RECOMMENDATION",
        ),
    )
    return AnalysisRequest(**values)


def test_analyze_produces_succeeded_run_with_stable_id() -> None:
    result = analyze(
        base_request(),
        policy_repository(),
        MemoryRunRepository(),
        FixedClock(),
    )
    assert result.run.status.value == "SUCCEEDED"
    assert result.run.run_id.startswith("run-")
    assert len(result.run.run_id) == 4 + 64


def test_analyze_run_id_is_idempotent() -> None:
    first = analyze(base_request(), policy_repository(), MemoryRunRepository(), FixedClock())
    later = analyze(
        base_request(),
        policy_repository(),
        MemoryRunRepository(),
        FixedClock(datetime(2026, 8, 12, tzinfo=timezone.utc)),
    )
    assert first.run.run_id == later.run.run_id
    assert first.run.created_at != later.run.created_at


def test_analyze_persists_run_through_repository() -> None:
    repository = MemoryRunRepository()
    result = analyze(base_request(), policy_repository(), repository, FixedClock())
    assert repository.exists(result.run.run_id)
    assert repository.load(result.run.run_id) == result.run


def test_analyze_reconciles_confirmed_months() -> None:
    result = analyze(base_request(), policy_repository(), MemoryRunRepository(), FixedClock())
    assert result.output["reconciliation"]["confirmed_months"] == 2


def test_analyze_generates_three_scenarios_and_recommendation() -> None:
    result = analyze(base_request(), policy_repository(), MemoryRunRepository(), FixedClock())
    assert [scenario.scenario_id for scenario in result.scenarios] == [
        "subsidized",
        "continue",
        "stop",
    ]
    assert result.recommendation is not None
    assert result.recommendation.scenario_id == "subsidized"


def test_analyze_scenario_cash_flows_are_consistent() -> None:
    result = analyze(base_request(), policy_repository(), MemoryRunRepository(), FixedClock())
    continue_scenario = next(
        scenario for scenario in result.scenarios if scenario.scenario_id == "continue"
    )
    assert continue_scenario.monthly_cash_flows[0].pension.amount == Decimal("100.00")
    assert continue_scenario.monthly_cash_flows[0].net_outflow.amount == Decimal("300.00")


def test_analyze_without_contribution_base_omits_continue_scenarios() -> None:
    request = base_request()
    request = AnalysisRequest(
        **{
            **{
                key: value
                for key, value in request.__dict__.items()
                if key != "contribution_base"
            },
            "contribution_base": None,
        }
    )
    result = analyze(request, policy_repository(), MemoryRunRepository(), FixedClock())
    assert [scenario.scenario_id for scenario in result.scenarios] == ["stop"]


def test_analyze_without_recommendation_capability_has_no_recommendation() -> None:
    request = base_request()
    request = AnalysisRequest(
        **{
            **request.__dict__,
            "requested_capabilities": tuple(
                capability
                for capability in request.requested_capabilities
                if capability != "RECOMMENDATION"
            ),
        }
    )
    result = analyze(request, policy_repository(), MemoryRunRepository(), FixedClock())
    assert result.recommendation is None


def test_analyze_rejects_missing_policy_query() -> None:
    with pytest.raises(AnalysisRequestError):
        AnalysisRequest(
            case_id="case-001",
            scheme="enterprise_employee_basic_pension",
            jurisdiction="CN-11",
            population_scope="enterprise participants",
            as_of_effective_date=AS_OF,
            as_known_at=KNOWN_AT,
            engine_version=ENGINE,
            analysis_mode=AnalysisMode.LOCAL_MVP,
            policy_queries=(),
        )


def test_analyze_rejects_missing_policy_rules() -> None:
    repository = MemoryPolicyRepository()  # no packages
    with pytest.raises(PolicyVersionNotFoundError):
        analyze(base_request(), repository, MemoryRunRepository(), FixedClock())


def test_analyze_output_digest_matches_content() -> None:
    result = analyze(base_request(), policy_repository(), MemoryRunRepository(), FixedClock())
    assert result.run.output_digest == content_digest(result.output)
