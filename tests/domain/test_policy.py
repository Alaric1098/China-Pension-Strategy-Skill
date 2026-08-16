from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from china_pension_strategy.domain import policy as policy_module
from china_pension_strategy.domain.errors import DomainValidationError
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

KNOWN_AT = datetime(2026, 8, 11, tzinfo=UTC)


def make_rule(**changes: object) -> PolicyRule:
    values = {
        "rule_id": "rule-a",
        "rule_type": RuleType.POLICY_RULE,
        "scheme": "enterprise_employee_basic_pension",
        "topic": "minimum_contribution",
        "jurisdiction_role": JurisdictionRole.NATIONAL_BASELINE,
        "population_scope": "enterprise participants",
        "inputs": ({"input_id": "months", "value_type": "INTEGER", "required": True},),
        "conditions": (
            {
                "condition_id": "adult",
                "input_ref": "months",
                "operator": ">=",
                "value_type": "INTEGER",
                "value": 0,
            },
        ),
        "results": (
            {
                "result_id": "minimum",
                "output_field": "minimum_months",
                "value_type": "INTEGER",
                "value": {"kind": "LITERAL", "value_type": "INTEGER", "value": 180},
            },
        ),
        "exceptions": (),
        "effective_from": date(2025, 1, 1),
        "effective_to": None,
        "transaction_from": datetime(2025, 1, 2, tzinfo=UTC),
        "transaction_to": None,
        "legal_hierarchy": LegalHierarchy.NATIONAL_LAW,
        "explicit_override_refs": (),
        "source_refs": ("source-a",),
        "parameters": {},
        "test_vectors": (
            {"vector_id": "v1", "input": {"months": 179}, "expected": {"minimum_months": 180}},
        ),
    }
    values.update(changes)
    return PolicyRule(**values)  # type: ignore[arg-type]


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


def test_policy_objects_are_frozen_and_nested_schema_values_are_immutable() -> None:
    package = make_package()

    with pytest.raises(FrozenInstanceError):
        package.version = "2.0.0"  # type: ignore[misc]
    with pytest.raises(TypeError):
        package.rules[0].results[0]["output_field"] = "changed"  # type: ignore[index]


def test_policy_rule_matches_both_half_open_time_intervals() -> None:
    rule = make_rule(
        effective_to=date(2026, 1, 1),
        transaction_to=datetime(2026, 2, 1, tzinfo=UTC),
    )

    assert rule.applies_at(date(2025, 12, 31), datetime(2026, 1, 31, tzinfo=UTC))
    assert not rule.applies_at(date(2026, 1, 1), datetime(2026, 1, 31, tzinfo=UTC))
    assert not rule.applies_at(date(2025, 12, 31), datetime(2026, 2, 1, tzinfo=UTC))


def test_mvp_reviewed_package_is_local_only() -> None:
    with pytest.raises(DomainValidationError, match="MVP_REVIEWED"):
        make_package(execution_modes=(AnalysisMode.PRODUCTION,))


def test_policy_rejects_invalid_intervals_and_self_override() -> None:
    with pytest.raises(DomainValidationError, match="effective_to"):
        make_rule(effective_to=date(2025, 1, 1))
    with pytest.raises(DomainValidationError, match="override itself"):
        make_rule(explicit_override_refs=("rule-a",))


def test_policy_rejects_qualified_self_override() -> None:
    with pytest.raises(DomainValidationError, match="override itself"):
        make_package(rules=(make_rule(explicit_override_refs=("package-a:rule-a",)),))


def test_rule_and_package_ids_forbid_qualified_separator() -> None:
    with pytest.raises(DomainValidationError, match="rule_id must not contain ':'"):
        make_rule(rule_id="rule-a:b")
    with pytest.raises(DomainValidationError, match="package_id must not contain ':'"):
        make_package(package_id="package-a:b")


def test_engineering_review_is_strict_frozen_domain_content() -> None:
    review = EngineeringReview("engineer-a", KNOWN_AT, True, True)

    with pytest.raises(FrozenInstanceError):
        review.reviewer_id = "changed"  # type: ignore[misc]
    with pytest.raises(DomainValidationError, match="reviewed_at"):
        EngineeringReview("engineer-a", datetime(2026, 1, 1), True, True)
    with pytest.raises(DomainValidationError, match="boolean"):
        EngineeringReview("engineer-a", KNOWN_AT, 1, True)  # type: ignore[arg-type]


def test_production_approval_requires_independent_reviewers_and_ordered_times() -> None:
    approval = ProductionApproval(
        domain_reviewer_id="domain-a",
        approver_ids=("approver-a", "approver-b"),
        approved_at=KNOWN_AT,
        signature="sig:synthetic",
        published_at=KNOWN_AT,
    )

    assert approval.approver_ids == ("approver-a", "approver-b")
    with pytest.raises(DomainValidationError, match="at least two"):
        ProductionApproval("domain-a", ("approver-a",), KNOWN_AT, "sig:x", KNOWN_AT)
    with pytest.raises(DomainValidationError, match="distinct"):
        ProductionApproval("domain-a", ("domain-a", "approver-b"), KNOWN_AT, "sig:x", KNOWN_AT)
    with pytest.raises(DomainValidationError, match="published_at"):
        ProductionApproval(
            "domain-a",
            ("approver-a", "approver-b"),
            KNOWN_AT,
            "sig:x",
            datetime(2026, 8, 10, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"url": "http://www.gov.cn/synthetic"},
        {"url": "https://gov.cn.example.com/synthetic"},
        {"source_digest": "sha256:not-a-digest"},
    ],
)
def test_policy_source_rejects_untrusted_urls_and_digests(changes: dict) -> None:
    values = make_source().__dict__ | changes

    with pytest.raises(DomainValidationError):
        PolicySource(**values)


@pytest.mark.parametrize(
    "authority_level",
    ["PROVINCIAL_HRSS", "MUNICIPAL_GOVERNMENT", "MUNICIPAL_HRSS"],
)
def test_policy_source_accepts_supported_local_authorities(authority_level: str) -> None:
    values = make_source().__dict__ | {"authority_level": authority_level}

    assert PolicySource(**values).authority_level == authority_level


def test_policy_source_rejects_unofficial_authority() -> None:
    values = make_source().__dict__ | {"authority_level": "PRIVATE_BLOG"}

    with pytest.raises(DomainValidationError, match="authority_level"):
        PolicySource(**values)


def test_package_digest_is_validated_even_when_review_booleans_pass() -> None:
    with pytest.raises(DomainValidationError, match="content_digest"):
        make_package(content_digest="sha256:invalid")

    malformed_source = make_source().__dict__ | {"url": "https://example.com/policy"}
    with pytest.raises(DomainValidationError, match="url"):
        make_package(provenance=(PolicySource(**malformed_source),))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "conditions": (
                    {
                        "condition_id": "c",
                        "input_ref": "missing",
                        "operator": "=",
                        "value_type": "INTEGER",
                        "value": 1,
                    },
                )
            },
            "condition input_ref",
        ),
        (
            {
                "exceptions": (
                    {
                        "exception_id": "e",
                        "condition_refs": ("missing",),
                        "effect": "EXCLUDE",
                        "result_refs": (),
                    },
                )
            },
            "exception condition_refs",
        ),
        (
            {
                "exceptions": (
                    {
                        "exception_id": "e",
                        "condition_refs": ("adult",),
                        "effect": "OVERRIDE",
                        "result_refs": ("missing",),
                    },
                )
            },
            "exception result_refs",
        ),
        (
            {
                "results": (
                    {
                        "result_id": "minimum",
                        "output_field": "minimum_months",
                        "value_type": "INTEGER",
                        "value": {
                            "kind": "REFERENCE",
                            "reference_type": "INPUT",
                            "reference_id": "missing",
                            "value_type": "INTEGER",
                        },
                    },
                )
            },
            "expression INPUT",
        ),
        (
            {
                "results": (
                    {
                        "result_id": "minimum",
                        "output_field": "minimum_months",
                        "value_type": "INTEGER",
                        "value": {
                            "kind": "REFERENCE",
                            "reference_type": "PARAMETER",
                            "reference_id": "missing",
                            "value_type": "INTEGER",
                        },
                    },
                )
            },
            "expression PARAMETER",
        ),
        (
            {
                "test_vectors": (
                    {
                        "vector_id": "v",
                        "input": {"missing": 1},
                        "expected": {"minimum_months": 180},
                    },
                )
            },
            "test vector input",
        ),
        (
            {
                "test_vectors": (
                    {"vector_id": "v", "input": {"months": 1}, "expected": {"missing": 180}},
                )
            },
            "test vector expected",
        ),
    ],
)
def test_rule_rejects_unresolved_executable_references(changes: dict, message: str) -> None:
    with pytest.raises(DomainValidationError, match=message):
        make_rule(**changes)


def test_package_rejects_override_refs_outside_its_rule_graph() -> None:
    unresolved = make_rule(explicit_override_refs=("not-in-package",))

    with pytest.raises(DomainValidationError, match="override refs"):
        make_package(rules=(unresolved,))


def test_recursive_expression_references_are_validated() -> None:
    nested = {
        "kind": "EXPRESSION",
        "operator": "ADD",
        "value_type": "INTEGER",
        "operands": (
            {"kind": "LITERAL", "value_type": "INTEGER", "value": 1},
            {
                "kind": "REFERENCE",
                "reference_type": "INPUT",
                "reference_id": "missing",
                "value_type": "INTEGER",
            },
        ),
    }

    with pytest.raises(DomainValidationError, match="expression INPUT"):
        make_rule(
            results=(
                {
                    "result_id": "minimum",
                    "output_field": "minimum_months",
                    "value_type": "INTEGER",
                    "value": nested,
                },
            )
        )


def decision_row(row_id: str, conditions: tuple[dict, ...]) -> dict:
    return {
        "row_id": row_id,
        "conditions": conditions,
        "results": (
            {
                "result_id": "minimum",
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


def decision_condition(condition_id: str, input_ref: str, operator: str, value: object) -> dict:
    return {
        "condition_id": condition_id,
        "input_ref": input_ref,
        "operator": operator,
        "value_type": "BOOLEAN" if isinstance(value, bool) else "INTEGER",
        "value": value,
    }


def make_decision_table(rows: tuple[dict, ...]) -> PolicyRule:
    return make_rule(
        rule_type=RuleType.DECISION_TABLE,
        inputs=(
            {"input_id": "months", "value_type": "INTEGER", "required": True},
            {"input_id": "active", "value_type": "BOOLEAN", "required": True},
        ),
        input_domains={"months": (0, 1), "active": (False, True)},
        decision_rows=rows,
        test_vectors=(
            {
                "vector_id": "v1",
                "input": {"months": 0, "active": False},
                "expected": {"minimum_months": 180},
            },
        ),
    )


def test_complete_decision_table_covers_cartesian_domain_exactly_once() -> None:
    rows = tuple(
        decision_row(
            f"row-{months}-{active}",
            (
                decision_condition(f"months-{months}-{active}", "months", "=", months),
                decision_condition(f"active-{months}-{active}", "active", "=", active),
            ),
        )
        for months in (0, 1)
        for active in (False, True)
    )

    table = make_decision_table(rows)

    assert len(table.decision_rows) == 4


def test_decision_table_rejects_actual_row_overlap() -> None:
    rows = (
        decision_row(
            "nonnegative",
            (decision_condition("nonnegative", "months", ">=", 0),),
        ),
        decision_row(
            "at-most-one",
            (decision_condition("at-most-one", "months", "<=", 1),),
        ),
    )

    with pytest.raises(DomainValidationError, match="overlap"):
        make_decision_table(rows)


def test_decision_table_rejects_actual_row_gap() -> None:
    rows = (
        decision_row(
            "zero-inactive",
            (
                decision_condition("months-zero", "months", "=", 0),
                decision_condition("inactive", "active", "=", False),
            ),
        ),
    )

    with pytest.raises(DomainValidationError, match="gap"):
        make_decision_table(rows)


def test_ordinary_rule_rejects_decision_table_fields() -> None:
    with pytest.raises(DomainValidationError, match="only valid for DECISION_TABLE"):
        make_rule(input_domains={"months": (0, 1)})


@pytest.mark.parametrize("operator", ["IN", "NOT_IN"])
def test_domain_rejects_membership_condition_operators(operator: str) -> None:
    with pytest.raises(DomainValidationError, match="operator"):
        make_rule(
            conditions=(
                {
                    "condition_id": "unsupported",
                    "input_ref": "months",
                    "operator": operator,
                    "value_type": "INTEGER",
                    "value": 1,
                },
            )
        )


def test_rule_rejects_unsupported_input_value_type_and_non_boolean_required() -> None:
    with pytest.raises(DomainValidationError, match="value_type"):
        make_rule(inputs=({"input_id": "months", "value_type": "UNTYPED", "required": True},))
    with pytest.raises(DomainValidationError, match="required"):
        make_rule(inputs=({"input_id": "months", "value_type": "INTEGER", "required": 1},))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "conditions": (
                    {
                        "condition_id": "c",
                        "input_ref": "months",
                        "operator": "=",
                        "value_type": "BOOLEAN",
                        "value": True,
                    },
                )
            },
            "value_type must match",
        ),
        (
            {
                "conditions": (
                    {
                        "condition_id": "c",
                        "input_ref": "months",
                        "operator": "=",
                        "value_type": "INTEGER",
                        "value": "180",
                    },
                )
            },
            "does not match",
        ),
        (
            {
                "inputs": ({"input_id": "active", "value_type": "BOOLEAN", "required": True},),
                "conditions": (
                    {
                        "condition_id": "c",
                        "input_ref": "active",
                        "operator": ">",
                        "value_type": "BOOLEAN",
                        "value": True,
                    },
                ),
                "test_vectors": (
                    {
                        "vector_id": "v",
                        "input": {"active": True},
                        "expected": {"minimum_months": 180},
                    },
                ),
            },
            "ordering",
        ),
    ],
)
def test_rule_condition_requires_matching_typed_literals_and_valid_operators(
    changes: dict, message: str
) -> None:
    with pytest.raises(DomainValidationError, match=message):
        make_rule(**changes)


def test_rule_condition_typed_boolean_input_rejects_ordering_operator() -> None:
    with pytest.raises(DomainValidationError, match="ordering"):
        make_rule(
            inputs=({"input_id": "active", "value_type": "BOOLEAN", "required": True},),
            conditions=(
                {
                    "condition_id": "c",
                    "input_ref": "active",
                    "operator": "<=",
                    "value_type": "BOOLEAN",
                    "value": True,
                },
            ),
        )


def test_rule_rejects_untyped_scalar_parameters() -> None:
    with pytest.raises(DomainValidationError, match="typed declaration"):
        make_rule(parameters={"base": 180})
    with pytest.raises(DomainValidationError, match="typed declaration"):
        make_rule(parameters={"base": {"value": 180}})


def test_rule_parameter_type_mismatch_is_rejected() -> None:
    with pytest.raises(DomainValidationError, match="parameter base"):
        make_rule(parameters={"base": {"value_type": "INTEGER", "value": True}})


@pytest.mark.parametrize(
    ("result_type", "expression", "message"),
    [
        (
            "INTEGER",
            {"kind": "LITERAL", "value_type": "INTEGER", "value": "180"},
            "does not match",
        ),
        (
            "INTEGER",
            {"kind": "LITERAL", "value_type": "INTEGER", "value": True},
            "does not match",
        ),
        (
            "DECIMAL",
            {"kind": "LITERAL", "value_type": "DECIMAL", "value": 1},
            "does not match",
        ),
        (
            "BOOLEAN",
            {
                "kind": "REFERENCE",
                "reference_type": "INPUT",
                "reference_id": "months",
                "value_type": "BOOLEAN",
            },
            "must match its target",
        ),
        (
            "INTEGER",
            {
                "kind": "REFERENCE",
                "reference_type": "PARAMETER",
                "reference_id": "base",
                "value_type": "INTEGER",
            },
            "must match its target",
        ),
        (
            "INTEGER",
            {
                "kind": "EXPRESSION",
                "operator": "ADD",
                "value_type": "INTEGER",
                "operands": ({"kind": "LITERAL", "value_type": "INTEGER", "value": 1},),
            },
            "at least two",
        ),
        (
            "INTEGER",
            {
                "kind": "EXPRESSION",
                "operator": "SUBTRACT",
                "value_type": "INTEGER",
                "operands": (
                    {"kind": "LITERAL", "value_type": "INTEGER", "value": 3},
                    {"kind": "LITERAL", "value_type": "INTEGER", "value": 2},
                    {"kind": "LITERAL", "value_type": "INTEGER", "value": 1},
                ),
            },
            "exactly two",
        ),
        (
            "INTEGER",
            {
                "kind": "EXPRESSION",
                "operator": "ADD",
                "value_type": "INTEGER",
                "operands": (
                    {"kind": "LITERAL", "value_type": "INTEGER", "value": 1},
                    {"kind": "LITERAL", "value_type": "INTEGER", "value": True},
                ),
            },
            "does not match",
        ),
        (
            "INTEGER",
            {
                "kind": "EXPRESSION",
                "operator": "ADD",
                "value_type": "BOOLEAN",
                "operands": (
                    {"kind": "LITERAL", "value_type": "BOOLEAN", "value": True},
                    {"kind": "LITERAL", "value_type": "BOOLEAN", "value": False},
                ),
            },
            "declared type",
        ),
    ],
)
def test_rule_rejects_invalid_typed_expression_ast(
    result_type: str, expression: dict, message: str
) -> None:
    changes: dict = {
        "results": (
            {
                "result_id": "minimum",
                "output_field": "minimum_months",
                "value_type": result_type,
                "value": expression,
            },
        )
    }
    if expression.get("reference_type") == "PARAMETER":
        changes["parameters"] = {"base": {"value_type": "DECIMAL", "value": Decimal(1)}}
    with pytest.raises(DomainValidationError, match=message):
        make_rule(**changes)


def test_rule_rejects_expression_operators_on_incompatible_types() -> None:
    with pytest.raises(DomainValidationError, match="numeric"):
        make_rule(
            results=(
                {
                    "result_id": "minimum",
                    "output_field": "minimum_months",
                    "value_type": "STRING",
                    "value": {
                        "kind": "EXPRESSION",
                        "operator": "ADD",
                        "value_type": "STRING",
                        "operands": (
                            {"kind": "LITERAL", "value_type": "STRING", "value": "a"},
                            {"kind": "LITERAL", "value_type": "STRING", "value": "b"},
                        ),
                    },
                },
            )
        )
    with pytest.raises(DomainValidationError, match="DECIMAL"):
        make_rule(
            results=(
                {
                    "result_id": "minimum",
                    "output_field": "minimum_months",
                    "value_type": "INTEGER",
                    "value": {
                        "kind": "EXPRESSION",
                        "operator": "DIVIDE",
                        "value_type": "INTEGER",
                        "operands": (
                            {"kind": "LITERAL", "value_type": "INTEGER", "value": 6},
                            {"kind": "LITERAL", "value_type": "INTEGER", "value": 3},
                        ),
                    },
                },
            )
        )
    with pytest.raises(DomainValidationError, match="orderable"):
        make_rule(
            results=(
                {
                    "result_id": "minimum",
                    "output_field": "minimum_months",
                    "value_type": "BOOLEAN",
                    "value": {
                        "kind": "EXPRESSION",
                        "operator": "MIN",
                        "value_type": "BOOLEAN",
                        "operands": (
                            {"kind": "LITERAL", "value_type": "BOOLEAN", "value": True},
                            {"kind": "LITERAL", "value_type": "BOOLEAN", "value": False},
                        ),
                    },
                },
            )
        )


def test_rule_parameter_reference_must_match_declared_parameter_type() -> None:
    with pytest.raises(DomainValidationError, match="must match its target"):
        make_rule(
            parameters={"base": {"value_type": "DECIMAL", "value": Decimal(180)}},
            results=(
                {
                    "result_id": "minimum",
                    "output_field": "minimum_months",
                    "value_type": "INTEGER",
                    "value": {
                        "kind": "REFERENCE",
                        "reference_type": "PARAMETER",
                        "reference_id": "base",
                        "value_type": "INTEGER",
                    },
                },
            ),
        )


def test_rule_rejects_unsupported_exception_effects() -> None:
    with pytest.raises(DomainValidationError, match="effect"):
        make_rule(
            exceptions=(
                {
                    "exception_id": "e",
                    "condition_refs": ("adult",),
                    "effect": "REPLACE",
                    "result_refs": ("minimum",),
                },
            )
        )


def test_rule_rejects_typed_literal_conditions_on_decision_rows() -> None:
    rows = (
        decision_row(
            "row",
            (
                {
                    "condition_id": "c",
                    "input_ref": "months",
                    "operator": "=",
                    "value_type": "INTEGER",
                    "value": True,
                },
            ),
        ),
    )

    with pytest.raises(DomainValidationError, match="does not match"):
        make_decision_table(rows)


def test_decision_table_domain_values_must_match_declared_input_types() -> None:
    rows = tuple(
        decision_row(
            f"row-{months}",
            (decision_condition(f"months-{months}", "months", "=", months),),
        )
        for months in (0, 1)
    )

    with pytest.raises(DomainValidationError, match="domain months"):
        make_rule(
            rule_type=RuleType.DECISION_TABLE,
            inputs=({"input_id": "months", "value_type": "BOOLEAN", "required": True},),
            conditions=(
                {
                    "condition_id": "active",
                    "input_ref": "months",
                    "operator": "=",
                    "value_type": "BOOLEAN",
                    "value": True,
                },
            ),
            input_domains={"months": (0, 1)},
            decision_rows=rows,
            test_vectors=(
                {"vector_id": "v", "input": {"months": True}, "expected": {"minimum_months": 180}},
            ),
        )


@pytest.mark.parametrize(
    ("vector", "message"),
    [
        (
            {"vector_id": "v", "input": {"months": True}, "expected": {"minimum_months": 180}},
            "test vector input",
        ),
        (
            {"vector_id": "v", "input": {"months": 1}, "expected": {"minimum_months": "180"}},
            "test vector expected",
        ),
    ],
)
def test_rule_test_vector_values_must_match_declared_types(vector: dict, message: str) -> None:
    with pytest.raises(DomainValidationError, match=message):
        make_rule(test_vectors=(vector,))


def test_package_transaction_from_cannot_precede_source_retrieval() -> None:
    source = PolicySource(
        **{**make_source().__dict__, "retrieved_at": datetime(2025, 1, 3, tzinfo=UTC)}
    )

    with pytest.raises(DomainValidationError, match="source retrieval"):
        make_package(
            transaction_from=datetime(2025, 1, 2, tzinfo=UTC),
            provenance=(source,),
        )


def test_package_transaction_from_cannot_precede_engineering_review() -> None:
    early_source = PolicySource(
        **{**make_source().__dict__, "retrieved_at": datetime(2024, 12, 1, tzinfo=UTC)}
    )

    with pytest.raises(DomainValidationError, match="engineering review"):
        make_package(
            transaction_from=datetime(2025, 1, 2, tzinfo=UTC),
            provenance=(early_source,),
            engineering_review=EngineeringReview(
                "engineer-a",
                datetime(2025, 1, 3, tzinfo=UTC),
                True,
                True,
            ),
        )


def test_package_transaction_from_cannot_precede_production_publication() -> None:
    early_source = PolicySource(
        **{**make_source().__dict__, "retrieved_at": datetime(2024, 12, 1, tzinfo=UTC)}
    )

    with pytest.raises(DomainValidationError, match="production publication"):
        make_package(
            transaction_from=datetime(2025, 1, 2, tzinfo=UTC),
            provenance=(early_source,),
            engineering_review=EngineeringReview(
                "engineer-a",
                datetime(2024, 12, 2, tzinfo=UTC),
                True,
                True,
            ),
            review_status=ReviewStatus.PRODUCTION_APPROVED,
            execution_modes=(AnalysisMode.PRODUCTION,),
            local_only=False,
            production_approval=ProductionApproval(
                "domain-a",
                ("approver-a", "approver-b"),
                datetime(2025, 1, 1, tzinfo=UTC),
                "sig:synthetic",
                datetime(2025, 1, 3, tzinfo=UTC),
            ),
        )


def test_package_transaction_from_may_equal_latest_evidence_timestamp() -> None:
    package = make_package(
        transaction_from=KNOWN_AT,
        engineering_review=EngineeringReview("engineer-a", KNOWN_AT, True, True),
    )

    assert package.transaction_from == KNOWN_AT


def test_decision_table_cartesian_domain_at_limit_passes(monkeypatch) -> None:
    monkeypatch.setattr(policy_module, "MAX_DECISION_TABLE_COMBINATIONS", 4)
    rows = tuple(
        decision_row(
            f"row-{months}-{active}",
            (
                decision_condition(f"months-{months}-{active}", "months", "=", months),
                decision_condition(f"active-{months}-{active}", "active", "=", active),
            ),
        )
        for months in (0, 1)
        for active in (False, True)
    )

    table = make_decision_table(rows)

    assert len(table.decision_rows) == 4


def test_decision_table_cartesian_domain_over_limit_rejected(monkeypatch) -> None:
    monkeypatch.setattr(policy_module, "MAX_DECISION_TABLE_COMBINATIONS", 3)

    with pytest.raises(DomainValidationError, match="exceeds the maximum"):
        make_decision_table(())


def test_decision_table_rejects_oversized_domain_before_row_validation() -> None:
    with pytest.raises(DomainValidationError, match="exceeds the maximum"):
        make_rule(
            rule_type=RuleType.DECISION_TABLE,
            input_domains={"months": tuple(range(100_001))},
            decision_rows=(),
        )
