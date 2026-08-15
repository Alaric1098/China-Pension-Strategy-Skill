from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from china_pension_strategy.application.resolve_policy import (
    AmbiguousPolicyRuleError,
    PolicyQuery,
    PolicyVersionNotFoundError,
    RulesetIncompatibleError,
    resolve_policy,
)
from china_pension_strategy.domain.policy import (
    AnalysisMode,
    EngineeringReview,
    JurisdictionRole,
    LegalHierarchy,
    PolicyPackage,
    PolicyRule,
    PolicySource,
    ProductionApproval,
    ReviewStatus,
    RuleType,
)


KNOWN_AT = datetime(2026, 8, 11, tzinfo=timezone.utc)


def make_source(**changes: object) -> PolicySource:
    values = {
        "source_id": "source-a",
        "url": "https://www.gov.cn/synthetic",
        "issuing_authority": "Synthetic authority",
        "authority_level": "NATIONAL_GOVERNMENT",
        "document_number": "Synthetic-1",
        "publication_date": date(2025, 1, 1),
        "retrieved_at": KNOWN_AT,
        "locator": "Article 1",
        "source_digest": "sha256:" + "a" * 64,
    }
    values.update(changes)
    return PolicySource(**values)  # type: ignore[arg-type]


def make_rule(**changes: object) -> PolicyRule:
    values = {
        "rule_id": "rule-a",
        "rule_type": RuleType.POLICY_RULE,
        "scheme": "enterprise_employee_basic_pension",
        "topic": "minimum_contribution",
        "jurisdiction_role": JurisdictionRole.NATIONAL_BASELINE,
        "population_scope": "enterprise participants",
        "inputs": ({"input_id": "months", "value_type": "INTEGER", "required": True},),
        "conditions": ({"condition_id": "adult", "input_ref": "months", "operator": ">=", "value_type": "INTEGER", "value": 0},),
        "results": ({"result_id": "minimum", "output_field": "minimum_months", "value_type": "INTEGER", "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 180}},),
        "exceptions": (),
        "effective_from": date(2025, 1, 1),
        "effective_to": None,
        "transaction_from": datetime(2025, 1, 2, tzinfo=timezone.utc),
        "transaction_to": None,
        "legal_hierarchy": LegalHierarchy.NATIONAL_LAW,
        "explicit_override_refs": (),
        "source_refs": ("source-a",),
        "parameters": {},
        "test_vectors": ({"vector_id": "v1", "input": {"months": 179}, "expected": {"minimum_months": 180}},),
    }
    values.update(changes)
    return PolicyRule(**values)  # type: ignore[arg-type]


def make_package(**changes: object) -> PolicyPackage:
    values = {
        "schema_version": "1.0.0",
        "package_id": "package-a",
        "version": "1.0.0",
        "scheme": "enterprise_employee_basic_pension",
        "jurisdiction": "CN-11",
        "topic": "minimum_contribution",
        "review_status": ReviewStatus.MVP_REVIEWED,
        "execution_modes": (AnalysisMode.LOCAL_MVP,),
        "local_only": True,
        "engine_compatibility": ">=0.1,<1.0",
        "effective_from": date(2025, 1, 1),
        "effective_to": None,
        "transaction_from": KNOWN_AT,
        "transaction_to": None,
        "content_digest": "sha256:" + "b" * 64,
        "provenance": (make_source(),),
        "rules": (make_rule(),),
        "engineering_review": EngineeringReview(
            reviewer_id="engineer-a",
            reviewed_at=KNOWN_AT,
            schema_validation_passed=True,
            rule_tests_passed=True,
        ),
        "production_approval": None,
    }
    values.update(changes)
    return PolicyPackage(**values)  # type: ignore[arg-type]


class MemoryPolicyRepository:
    def __init__(self, *packages):
        self._packages = packages

    def list_packages(self):
        return self._packages


def query(**changes: object) -> PolicyQuery:
    values = {
        "scheme": "enterprise_employee_basic_pension",
        "topic": "minimum_contribution",
        "jurisdiction": "CN-11",
        "jurisdiction_role": JurisdictionRole.NATIONAL_BASELINE,
        "population_scope": "enterprise participants",
        "as_of_effective_date": date(2026, 1, 1),
        "as_known_at": KNOWN_AT,
        "engine_version": "0.1.0",
        "analysis_mode": AnalysisMode.LOCAL_MVP,
    }
    values.update(changes)
    return PolicyQuery(**values)  # type: ignore[arg-type]


def with_rules(*rules, **changes):
    return make_package(rules=rules, **changes)


def test_resolver_filters_scope_without_implicit_specificity() -> None:
    matching = make_rule(rule_id="matching")
    wrong_population = replace(matching, rule_id="specific", population_scope="more specific")
    wrong_role = replace(
        matching,
        rule_id="local",
        jurisdiction_role=JurisdictionRole.LOCAL_IMPLEMENTATION,
    )

    resolved = resolve_policy(
        MemoryPolicyRepository(with_rules(matching, wrong_population, wrong_role)), query()
    )

    assert [rule.rule_id for rule in resolved.rules] == ["matching"]


def test_higher_legal_hierarchy_wins_without_using_recency_or_specificity() -> None:
    lower = make_rule(
        rule_id="municipal",
        legal_hierarchy=LegalHierarchy.MUNICIPAL_IMPLEMENTING_RULE,
        transaction_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    higher = make_rule(rule_id="national", legal_hierarchy=LegalHierarchy.NATIONAL_LAW)

    resolved = resolve_policy(MemoryPolicyRepository(with_rules(lower, higher)), query())

    assert [rule.rule_id for rule in resolved.rules] == ["national"]


def test_explicit_override_can_replace_a_higher_hierarchy_rule() -> None:
    baseline = make_rule(rule_id="baseline", legal_hierarchy=LegalHierarchy.NATIONAL_LAW)
    exception = make_rule(
        rule_id="exception",
        legal_hierarchy=LegalHierarchy.MUNICIPAL_IMPLEMENTING_RULE,
        explicit_override_refs=("baseline",),
    )

    resolved = resolve_policy(
        MemoryPolicyRepository(with_rules(baseline, exception)), query()
    )

    assert [rule.rule_id for rule in resolved.rules] == ["exception"]


def test_incompatible_survivors_return_deterministic_ambiguity() -> None:
    first = make_rule(rule_id="z-rule")
    second = make_rule(
        rule_id="a-rule",
        results=({"result_id": "minimum", "output_field": "minimum_months", "value_type": "INTEGER", "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 240}},),
    )

    with pytest.raises(AmbiguousPolicyRuleError) as raised:
        resolve_policy(MemoryPolicyRepository(with_rules(first, second)), query())

    assert raised.value.competing_rule_ids == ("package-a:a-rule", "package-a:z-rule")
    assert raised.value.conflict_dimensions == (
        "LEGAL_HIERARCHY",
        "RULE_OVERRIDE",
    )


def test_complete_tables_with_different_row_outputs_are_ambiguous() -> None:
    def table(rule_id: str, second_output: int) -> PolicyRule:
        rows = tuple(
            {
                "row_id": f"row-{months}",
                "conditions": (
                    {
                        "condition_id": f"months-{months}",
                        "input_ref": "months",
                        "operator": "=",
                        "value_type": "INTEGER",
                        "value": months,
                    },
                ),
                "results": (
                    {
                        "result_id": "minimum",
                        "output_field": "minimum_months",
                        "value_type": "INTEGER",
                        "value": {
                            "kind": "LITERAL",
                            "value_type": "INTEGER",
                            "value": 180 if months == 0 else second_output,
                        },
                    },
                ),
            }
            for months in (0, 1)
        )
        return make_rule(
            rule_id=rule_id,
            rule_type=RuleType.DECISION_TABLE,
            input_domains={"months": (0, 1)},
            decision_rows=rows,
        )

    first = table("table-a", 180)
    second = table("table-b", 181)

    with pytest.raises(AmbiguousPolicyRuleError) as raised:
        resolve_policy(MemoryPolicyRepository(with_rules(first, second)), query())

    assert raised.value.competing_rule_ids == ("package-a:table-a", "package-a:table-b")


def test_behaviorally_identical_rules_ignore_ids_and_resolve_exception_edges() -> None:
    def rule(
        rule_id: str, condition_id: str, result_id: str, exception_id: str
    ) -> PolicyRule:
        return make_rule(
            rule_id=rule_id,
            conditions=(
                {
                    "condition_id": condition_id,
                    "input_ref": "months",
                    "operator": ">=",
                    "value_type": "INTEGER",
                    "value": 0,
                },
            ),
            results=(
                {
                    "result_id": result_id,
                    "output_field": "minimum_months",
                    "value_type": "INTEGER",
                    "value": {
                        "kind": "LITERAL",
                        "value_type": "INTEGER",
                        "value": 180,
                    },
                },
            ),
            exceptions=(
                {
                    "exception_id": exception_id,
                    "condition_refs": (condition_id,),
                    "effect": "OVERRIDE",
                    "result_refs": (result_id,),
                },
            ),
        )

    first = rule("rule-a", "condition-a", "result-a", "exception-a")
    second = rule("rule-b", "condition-b", "result-b", "exception-b")

    resolved = resolve_policy(
        MemoryPolicyRepository(with_rules(first, second)), query()
    )

    assert [rule.rule_id for rule in resolved.rules] == ["rule-a", "rule-b"]


def test_behaviorally_identical_tables_ignore_top_level_and_row_ids() -> None:
    def table(rule_id: str, suffix: str) -> PolicyRule:
        result_id = f"result-{suffix}"
        rows = tuple(
            {
                "row_id": f"row-{suffix}-{months}",
                "conditions": (
                    {
                        "condition_id": f"row-condition-{suffix}-{months}",
                        "input_ref": "months",
                        "operator": "=",
                        "value_type": "INTEGER",
                        "value": months,
                    },
                ),
                "results": (
                    {
                        "result_id": result_id,
                        "output_field": "minimum_months",
                        "value_type": "INTEGER",
                        "value": {
                            "kind": "LITERAL",
                            "value_type": "INTEGER",
                            "value": 180,
                        },
                    },
                ),
            }
            for months in (0, 1)
        )
        return make_rule(
            rule_id=rule_id,
            rule_type=RuleType.DECISION_TABLE,
            conditions=(
                {
                    "condition_id": f"top-condition-{suffix}",
                    "input_ref": "months",
                    "operator": ">=",
                    "value_type": "INTEGER",
                    "value": 0,
                },
            ),
            results=(
                {
                    "result_id": result_id,
                    "output_field": "minimum_months",
                    "value_type": "INTEGER",
                    "value": {
                        "kind": "LITERAL",
                        "value_type": "INTEGER",
                        "value": 180,
                    },
                },
            ),
            input_domains={"months": (0, 1)},
            decision_rows=rows,
        )

    first = table("table-a", "a")
    second = table("table-b", "b")

    resolved = resolve_policy(
        MemoryPolicyRepository(with_rules(first, second)), query()
    )

    assert [rule.rule_id for rule in resolved.rules] == ["table-a", "table-b"]


def test_engine_compatibility_is_enforced() -> None:
    package = make_package(engine_compatibility=">=1.0,<2.0")

    with pytest.raises(RulesetIncompatibleError):
        resolve_policy(MemoryPolicyRepository(package), query(engine_version="0.9.0"))


def test_incompatible_higher_precedence_rule_blocks_compatible_lower_rule() -> None:
    higher = make_package(
        package_id="higher",
        engine_compatibility=">=1.0,<2.0",
        rules=(make_rule(rule_id="higher"),),
    )
    lower = make_package(
        package_id="lower",
        rules=(
            make_rule(
                rule_id="lower",
                legal_hierarchy=LegalHierarchy.MUNICIPAL_IMPLEMENTING_RULE,
            ),
        ),
    )

    with pytest.raises(RulesetIncompatibleError):
        resolve_policy(
            MemoryPolicyRepository(lower, higher), query(engine_version="0.9.0")
        )


def test_non_executable_higher_precedence_rule_does_not_fall_through() -> None:
    higher = make_package(package_id="higher", rules=(make_rule(rule_id="higher"),))
    lower = make_package(
        package_id="lower",
        review_status=ReviewStatus.PRODUCTION_APPROVED,
        execution_modes=(AnalysisMode.PRODUCTION,),
        local_only=False,
        rules=(
            make_rule(
                rule_id="lower",
                legal_hierarchy=LegalHierarchy.MUNICIPAL_IMPLEMENTING_RULE,
            ),
        ),
        production_approval=ProductionApproval(
            "domain-a",
            ("approver-a", "approver-b"),
            KNOWN_AT,
            "sig:synthetic",
            KNOWN_AT,
        ),
    )

    with pytest.raises(PolicyVersionNotFoundError):
        resolve_policy(
            MemoryPolicyRepository(lower, higher),
            query(analysis_mode=AnalysisMode.PRODUCTION),
        )


def test_mvp_reviewed_is_rejected_outside_local_mvp() -> None:
    with pytest.raises(PolicyVersionNotFoundError):
        resolve_policy(
            MemoryPolicyRepository(make_package()),
            query(analysis_mode=AnalysisMode.PRODUCTION),
        )


@pytest.mark.parametrize(
    ("as_of", "known_at", "expected_rule"),
    [
        pytest.param(
            date(2025, 6, 1),
            datetime(2025, 6, 1, tzinfo=timezone.utc),
            "original",
            id="replay-before-correction-is-recorded",
        ),
        pytest.param(
            date(2025, 6, 1),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            "retrospective-correction",
            id="replay-after-retrospective-correction",
        ),
        pytest.param(
            date(2026, 1, 1),
            datetime(2026, 2, 1, tzinfo=timezone.utc),
            "current",
            id="replay-new-effective-period",
        ),
    ],
)
def test_bitemporal_historical_replay(as_of, known_at, expected_rule) -> None:
    original = make_rule(
        rule_id="original",
        effective_to=date(2026, 1, 1),
        transaction_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        transaction_to=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    correction = make_rule(
        rule_id="retrospective-correction",
        effective_to=date(2026, 1, 1),
        transaction_from=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    current = make_rule(
        rule_id="current",
        effective_from=date(2026, 1, 1),
        transaction_from=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    first = make_package(
        package_id="package-v1",
        transaction_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        provenance=(
            make_source(retrieved_at=datetime(2024, 12, 20, tzinfo=timezone.utc)),
        ),
        engineering_review=EngineeringReview(
            "engineer-a",
            datetime(2024, 12, 28, tzinfo=timezone.utc),
            True,
            True,
        ),
        rules=(original,),
    )
    second = make_package(
        package_id="package-v2",
        transaction_from=datetime(2026, 1, 15, tzinfo=timezone.utc),
        provenance=(
            make_source(retrieved_at=datetime(2026, 1, 10, tzinfo=timezone.utc)),
        ),
        engineering_review=EngineeringReview(
            "engineer-a",
            datetime(2026, 1, 12, tzinfo=timezone.utc),
            True,
            True,
        ),
        rules=(correction, current),
    )

    resolved = resolve_policy(
        MemoryPolicyRepository(first, second),
        query(as_of_effective_date=as_of, as_known_at=known_at),
    )

    assert [rule.rule_id for rule in resolved.rules] == [expected_rule]


@pytest.mark.parametrize(
    ("rules", "error"),
    [
        pytest.param(
            (
                make_rule(rule_id="row-a"),
                make_rule(
                    rule_id="row-b",
                    results=({"result_id": "minimum", "output_field": "minimum_months", "value_type": "INTEGER", "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 181}},),
                ),
            ),
            AmbiguousPolicyRuleError,
            id="decision-table-overlap",
        ),
        pytest.param(
            (make_rule(rule_id="other-population", population_scope="other"),),
            PolicyVersionNotFoundError,
            id="decision-table-gap",
        ),
    ],
)
def test_rule_overlap_and_scope_gap_fail_closed(rules, error) -> None:
    with pytest.raises(error):
        resolve_policy(MemoryPolicyRepository(with_rules(*rules)), query())


def test_compatible_survivors_have_stable_rule_order() -> None:
    resolved = resolve_policy(
        MemoryPolicyRepository(with_rules(make_rule(rule_id="z"), make_rule(rule_id="a"))),
        query(),
    )

    assert [rule.rule_id for rule in resolved.rules] == ["a", "z"]


def test_production_approved_package_can_run_in_declared_production_mode() -> None:
    package = make_package(
        review_status=ReviewStatus.PRODUCTION_APPROVED,
        execution_modes=(AnalysisMode.PRODUCTION,),
        local_only=False,
        production_approval=ProductionApproval(
            domain_reviewer_id="domain-a",
            approver_ids=("approver-a", "approver-b"),
            approved_at=KNOWN_AT,
            signature="sig:synthetic",
            published_at=KNOWN_AT,
        ),
    )

    resolved = resolve_policy(
        MemoryPolicyRepository(package), query(analysis_mode=AnalysisMode.PRODUCTION)
    )

    assert resolved.packages == (package,)


def test_bare_override_ref_is_scoped_to_its_own_package() -> None:
    baseline_a = make_rule(rule_id="baseline")
    baseline_b = make_rule(rule_id="baseline")
    exception_b = make_rule(
        rule_id="exception",
        explicit_override_refs=("baseline",),
    )
    package_a = make_package(package_id="package-a", rules=(baseline_a,))
    package_b = make_package(package_id="package-b", rules=(baseline_b, exception_b))

    resolved = resolve_policy(MemoryPolicyRepository(package_a, package_b), query())

    assert [rule.rule_id for rule in resolved.rules] == ["baseline", "exception"]


def test_qualified_override_can_target_a_rule_in_another_package() -> None:
    baseline_a = make_rule(rule_id="baseline")
    exception_b = make_rule(
        rule_id="exception",
        explicit_override_refs=("package-a:baseline",),
    )

    resolved = resolve_policy(
        MemoryPolicyRepository(
            make_package(package_id="package-a", rules=(baseline_a,)),
            make_package(package_id="package-b", rules=(exception_b,)),
        ),
        query(),
    )

    assert [rule.rule_id for rule in resolved.rules] == ["exception"]


def test_same_bare_rule_id_across_packages_reports_qualified_ambiguity() -> None:
    first = make_rule(rule_id="shared")
    second = make_rule(
        rule_id="shared",
        results=({"result_id": "minimum", "output_field": "minimum_months", "value_type": "INTEGER", "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 240}},),
    )

    with pytest.raises(AmbiguousPolicyRuleError) as raised:
        resolve_policy(
            MemoryPolicyRepository(
                make_package(package_id="package-a", rules=(first,)),
                make_package(package_id="package-b", rules=(second,)),
            ),
            query(),
        )

    assert raised.value.competing_rule_ids == ("package-a:shared", "package-b:shared")


def test_equal_python_scalars_with_different_types_do_not_collapse_signatures() -> None:
    integer_parameter = make_rule(
        rule_id="integer-parameter",
        parameters={"cap": {"value_type": "INTEGER", "value": 1}},
    )
    boolean_parameter = make_rule(
        rule_id="boolean-parameter",
        parameters={"cap": {"value_type": "BOOLEAN", "value": True}},
    )

    with pytest.raises(AmbiguousPolicyRuleError) as raised:
        resolve_policy(
            MemoryPolicyRepository(with_rules(integer_parameter, boolean_parameter)),
            query(),
        )

    assert raised.value.competing_rule_ids == (
        "package-a:boolean-parameter",
        "package-a:integer-parameter",
    )


def test_condition_scalar_type_tags_are_canonically_distinct() -> None:
    def rule(rule_id: str, value: object, value_type: str) -> PolicyRule:
        return make_rule(
            rule_id=rule_id,
            inputs=({"input_id": "months", "value_type": value_type, "required": True},),
            conditions=({"condition_id": "c", "input_ref": "months", "operator": "=", "value_type": value_type, "value": value},),
            test_vectors=({"vector_id": "v", "input": {"months": value}, "expected": {"minimum_months": 180}},),
        )

    integer_rule = rule("int-rule", 1, "INTEGER")
    string_rule = rule("string-rule", "1", "STRING")

    with pytest.raises(AmbiguousPolicyRuleError) as raised:
        resolve_policy(MemoryPolicyRepository(with_rules(integer_rule, string_rule)), query())

    assert raised.value.competing_rule_ids == (
        "package-a:int-rule",
        "package-a:string-rule",
    )


def test_equal_decimal_values_with_different_precision_share_a_signature() -> None:
    plain = make_rule(
        rule_id="decimal-plain",
        parameters={"cap": {"value_type": "DECIMAL", "value": Decimal("1")}},
    )
    padded = make_rule(
        rule_id="decimal-padded",
        parameters={"cap": {"value_type": "DECIMAL", "value": Decimal("1.0")}},
    )

    resolved = resolve_policy(
        MemoryPolicyRepository(with_rules(plain, padded)), query()
    )

    assert {rule.rule_id for rule in resolved.rules} == {
        "decimal-padded",
        "decimal-plain",
    }
