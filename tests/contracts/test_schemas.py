import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64


def validator(relative_path: str) -> Draft202012Validator:
    schema = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def assert_valid(relative_path: str, instance: dict) -> None:
    errors = sorted(validator(relative_path).iter_errors(instance), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def assert_invalid(relative_path: str, instance: dict) -> None:
    assert list(validator(relative_path).iter_errors(instance))


@pytest.fixture
def person_input() -> dict:
    return {
        "schema_version": "1.0.0",
        "case_id": "synthetic-case-001",
        "analysis_mode": "LOCAL_MVP",
        "classification": "S2-CONFIDENTIAL",
        "purpose": "pension_strategy_analysis",
        "consent_id": "consent-synthetic-001",
        "created_at": "2026-08-11T10:00:00+08:00",
        "expires_at": "2026-09-10T10:00:00+08:00",
        "deletion_status": "ACTIVE",
        "requested_capabilities": [
            "CONTRIBUTION_RECONCILIATION",
            "CONTRIBUTION_GAP",
            "FLEXIBLE_EMPLOYMENT_CONTRIBUTION",
            "SUBSIDY_ELIGIBILITY",
            "SCENARIO_COMPARISON",
            "RECOMMENDATION",
        ],
        "facts": [
            {
                "fact_id": "fact-pension-months",
                "fact_type": "CONFIRMED_CONTRIBUTION_MONTHS",
                "value": 179,
                "as_of_date": "2026-08-11",
                "source_ref": "synthetic-account-summary",
                "required_for": ["CONTRIBUTION_GAP", "SCENARIO_COMPARISON"],
            }
        ],
    }


def test_person_input_requires_governance_and_requested_capabilities(person_input):
    path = "schemas/person-input.schema.json"
    assert_valid(path, person_input)

    for field in ("consent_id", "classification", "expires_at", "requested_capabilities"):
        invalid = copy.deepcopy(person_input)
        del invalid[field]
        assert_invalid(path, invalid)

    invalid = copy.deepcopy(person_input)
    invalid["classification"] = "PUBLIC"
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(person_input)
    invalid["unexpected"] = True
    assert_invalid(path, invalid)


@pytest.fixture
def mvp_policy_package() -> dict:
    return {
        "schema_version": "1.0.0",
        "package_id": "cn-pension/beijing-flex/2026.1",
        "version": "2026.1.0",
        "scheme": "enterprise_employee_basic_pension",
        "jurisdiction": "CN-11",
        "topic": "flexible_employment_contribution",
        "review_status": "MVP_REVIEWED",
        "execution_modes": ["LOCAL_MVP"],
        "local_only": True,
        "engine_compatibility": ">=0.1,<1.0",
        "effective_from": "2026-01-01",
        "effective_to": None,
        "transaction_from": "2026-08-11T09:00:00+08:00",
        "transaction_to": None,
        "content_digest": DIGEST,
        "provenance": [
            {
                "source_id": "beijing-official-001",
                "url": "https://www.beijing.gov.cn/example",
                "issuing_authority": "Beijing Municipal Government",
                "authority_level": "BEIJING_MUNICIPAL_GOVERNMENT",
                "document_number": "Synthetic-001",
                "publication_date": "2026-01-01",
                "retrieved_at": "2026-08-11T08:00:00+08:00",
                "locator": "Article 3, paragraph 2",
                "source_digest": OTHER_DIGEST,
            }
        ],
        "rules": [
            {
                "rule_id": "beijing-flex-pension-rate-2026",
                "rule_type": "PARAMETER_TABLE",
                "topic": "flexible_employment_contribution",
                "scheme": "enterprise_employee_basic_pension",
                "jurisdiction_role": "LOCAL_IMPLEMENTATION",
                "population_scope": "Beijing flexible-employment participants",
                "inputs": [
                    {"input_id": "contribution_base", "value_type": "DECIMAL", "required": True}
                ],
                "conditions": [
                    {
                        "condition_id": "positive-base",
                        "input_ref": "contribution_base",
                        "operator": ">",
                        "value_type": "DECIMAL",
                        "value": "0.00",
                    }
                ],
                "results": [
                    {
                        "result_id": "pension-contribution",
                        "output_field": "pension_contribution",
                        "value_type": "DECIMAL",
                        "value": {
                            "kind": "EXPRESSION",
                            "operator": "MULTIPLY",
                            "value_type": "DECIMAL",
                            "operands": [
                                {
                                    "kind": "REFERENCE",
                                    "reference_type": "INPUT",
                                    "reference_id": "contribution_base",
                                    "value_type": "DECIMAL",
                                },
                                {
                                    "kind": "REFERENCE",
                                    "reference_type": "PARAMETER",
                                    "reference_id": "pension_rate",
                                    "value_type": "DECIMAL",
                                },
                            ],
                        },
                    }
                ],
                "exceptions": [
                    {
                        "exception_id": "no-positive-base",
                        "condition_refs": ["positive-base"],
                        "effect": "EXCLUDE",
                        "result_refs": [],
                    }
                ],
                "legal_hierarchy": "MUNICIPAL_IMPLEMENTING_RULE",
                "explicit_override_refs": [],
                "source_refs": ["beijing-official-001"],
                "effective_from": "2026-01-01",
                "effective_to": None,
                "transaction_from": "2026-08-11T09:00:00+08:00",
                "transaction_to": None,
                "parameters": {"pension_rate": {"value_type": "DECIMAL", "value": "0.20"}},
                "test_vectors": [
                    {
                        "vector_id": "vector-rate-001",
                        "input": {"contribution_base": "7000.00"},
                        "expected": {"pension_contribution": "1400.00"},
                    }
                ],
            }
        ],
        "engineering_review": {
            "reviewer_id": "engineer-reviewer-01",
            "reviewed_at": "2026-08-11T08:30:00+08:00",
            "schema_validation_passed": True,
            "rule_tests_passed": True,
        },
        "production_approval": None,
    }


def test_policy_package_supports_local_mvp_review_with_provenance_and_vectors(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    assert_valid(path, mvp_policy_package)

    for mutation in (
        lambda value: value.update(execution_modes=["PRODUCTION"]),
        lambda value: value.update(local_only=False),
        lambda value: value["provenance"][0].pop("source_digest"),
        lambda value: value["rules"][0].update(test_vectors=[]),
    ):
        invalid = copy.deepcopy(mvp_policy_package)
        mutation(invalid)
        assert_invalid(path, invalid)


def test_policy_rules_require_complete_typed_scope_time_and_traceability(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    required_fields = (
        "scheme",
        "topic",
        "jurisdiction_role",
        "population_scope",
        "inputs",
        "conditions",
        "results",
        "exceptions",
        "effective_from",
        "effective_to",
        "transaction_from",
        "transaction_to",
        "legal_hierarchy",
        "explicit_override_refs",
        "source_refs",
        "test_vectors",
    )
    for field in required_fields:
        invalid = copy.deepcopy(mvp_policy_package)
        del invalid["rules"][0][field]
        assert_invalid(path, invalid)

    invalid = copy.deepcopy(mvp_policy_package)
    invalid["rules"][0]["conditions"][0]["unexpected"] = True
    assert_invalid(path, invalid)


def test_decision_table_schema_requires_strict_domains_and_rows(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    table = copy.deepcopy(mvp_policy_package)
    rule = table["rules"][0]
    rule["rule_type"] = "DECISION_TABLE"
    rule["input_domains"] = {"contribution_base": ["0.00", "7000.00"]}
    rule["decision_rows"] = [
        {
            "row_id": "positive",
            "conditions": [copy.deepcopy(rule["conditions"][0])],
            "results": [copy.deepcopy(rule["results"][0])],
        }
    ]
    assert_valid(path, table)

    for field in ("input_domains", "decision_rows"):
        invalid = copy.deepcopy(table)
        del invalid["rules"][0][field]
        assert_invalid(path, invalid)

    invalid = copy.deepcopy(table)
    invalid["rules"][0]["input_domains"]["contribution_base"] = []
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(table)
    invalid["rules"][0]["decision_rows"][0]["unexpected"] = True
    assert_invalid(path, invalid)


@pytest.mark.parametrize(
    ("value_type", "valid_value", "invalid_value"),
    [
        ("DECIMAL", "12.50", 12.5),
        ("INTEGER", 12, "12"),
        ("BOOLEAN", True, "true"),
        ("STRING", "synthetic", 12),
        ("DATE", "2026-08-11", "2026-13-40"),
        ("YEAR_MONTH", "2026-08", "2026-13"),
        ("NULL", None, "null"),
    ],
)
def test_policy_condition_typed_values_match_declared_type(
    mvp_policy_package, value_type, valid_value, invalid_value
):
    path = "schemas/policy-package.schema.json"
    valid = copy.deepcopy(mvp_policy_package)
    valid["rules"][0]["conditions"][0].update(value_type=value_type, value=valid_value)
    assert_valid(path, valid)

    invalid = copy.deepcopy(valid)
    invalid["rules"][0]["conditions"][0]["value"] = invalid_value
    assert_invalid(path, invalid)


@pytest.mark.parametrize("operator", ["IN", "NOT_IN"])
def test_policy_schema_rejects_membership_condition_operators(
    mvp_policy_package, operator
):
    invalid = copy.deepcopy(mvp_policy_package)
    invalid["rules"][0]["conditions"][0]["operator"] = operator

    assert_invalid("schemas/policy-package.schema.json", invalid)


def test_policy_result_accepts_strict_literal_reference_and_recursive_expressions(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    expressions = [
        {"kind": "LITERAL", "value_type": "DECIMAL", "value": "1400.00"},
        {
            "kind": "REFERENCE",
            "reference_type": "INPUT",
            "reference_id": "contribution_base",
            "value_type": "DECIMAL",
        },
        {
            "kind": "REFERENCE",
            "reference_type": "PARAMETER",
            "reference_id": "pension_rate",
            "value_type": "DECIMAL",
        },
        {
            "kind": "EXPRESSION",
            "operator": "MAX",
            "value_type": "DECIMAL",
            "operands": [
                {"kind": "LITERAL", "value_type": "DECIMAL", "value": "0.00"},
                {
                    "kind": "EXPRESSION",
                    "operator": "ADD",
                    "value_type": "DECIMAL",
                    "operands": [
                        {"kind": "LITERAL", "value_type": "DECIMAL", "value": "1.00"},
                        {"kind": "LITERAL", "value_type": "DECIMAL", "value": "2.00"},
                    ],
                },
            ],
        },
    ]
    for expression in expressions:
        valid = copy.deepcopy(mvp_policy_package)
        valid["rules"][0]["results"][0]["value"] = expression
        assert_valid(path, valid)


def test_policy_result_rejects_unstructured_or_invalid_expression_ast(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    invalid_expressions = [
        "input:contribution_base*parameter:pension_rate",
        {
            "kind": "EXPRESSION",
            "operator": "MODULO",
            "value_type": "DECIMAL",
            "operands": [
                {"kind": "LITERAL", "value_type": "DECIMAL", "value": "2.00"},
                {"kind": "LITERAL", "value_type": "DECIMAL", "value": "3.00"},
            ],
        },
        {
            "kind": "EXPRESSION",
            "operator": "ADD",
            "value_type": "DECIMAL",
            "operands": [{"kind": "LITERAL", "value": "1.00"}],
        },
        {
            "kind": "EXPRESSION",
            "operator": "ADD",
            "value_type": "DECIMAL",
            "operands": [{"kind": "LITERAL", "value_type": "DECIMAL", "value": "1.00"}],
        },
        {
            "kind": "EXPRESSION",
            "operator": "DIVIDE",
            "value_type": "DECIMAL",
            "operands": [
                {"kind": "LITERAL", "value_type": "DECIMAL", "value": "6.00"},
                {"kind": "LITERAL", "value_type": "DECIMAL", "value": "3.00"},
                {"kind": "LITERAL", "value_type": "DECIMAL", "value": "2.00"},
            ],
        },
        {
            "kind": "REFERENCE",
            "reference_type": "REMOTE_LOOKUP",
            "reference_id": "unsafe",
            "value_type": "DECIMAL",
        },
        {"kind": "LITERAL", "value_type": "DECIMAL", "value": "1.00", "extra": True},
        {"kind": "LITERAL", "value_type": "INTEGER", "value": 1},
    ]
    for expression in invalid_expressions:
        invalid = copy.deepcopy(mvp_policy_package)
        invalid["rules"][0]["results"][0]["value"] = expression
        assert_invalid(path, invalid)


def test_policy_parameters_are_typed_declarations(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    for parameters in (
        {"pension_rate": "0.20"},
        {"pension_rate": {"value": "0.20"}},
        {"pension_rate": {"value_type": "DECIMAL", "value": 0.20}},
    ):
        invalid = copy.deepcopy(mvp_policy_package)
        invalid["rules"][0]["parameters"] = parameters
        assert_invalid(path, invalid)


def test_policy_override_refs_accept_bare_and_qualified_forms(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    for refs in (["beijing-flex-pension-rate-2026"], ["other-package:beijing-flex-pension-rate-2026"]):
        valid = copy.deepcopy(mvp_policy_package)
        valid["rules"][0]["explicit_override_refs"] = refs
        assert_valid(path, valid)

    for refs in ([":"], ["package:"], [":rule"], ["a:b:c"]):
        invalid = copy.deepcopy(mvp_policy_package)
        invalid["rules"][0]["explicit_override_refs"] = refs
        assert_invalid(path, invalid)


def test_decision_table_schema_cardinality_limits(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    table = copy.deepcopy(mvp_policy_package)
    rule = table["rules"][0]
    rule["rule_type"] = "DECISION_TABLE"
    rule["input_domains"] = {"contribution_base": ["0.00", "7000.00"]}
    rule["decision_rows"] = [
        {
            "row_id": "positive",
            "conditions": [copy.deepcopy(rule["conditions"][0])],
            "results": [copy.deepcopy(rule["results"][0])],
        }
    ]

    oversized_domains = copy.deepcopy(table)
    oversized_domains["rules"][0]["input_domains"] = {
        f"input-{index}": ["0.00"] for index in range(13)
    }
    assert_invalid(path, oversized_domains)

    oversized_values = copy.deepcopy(table)
    oversized_values["rules"][0]["input_domains"]["contribution_base"] = [
        f"{index}.00" for index in range(257)
    ]
    assert_invalid(path, oversized_values)

    schema = validator(path)
    decision_rows_limit = schema.schema["$defs"]["rule"]["properties"]["decision_rows"]["maxItems"]
    assert decision_rows_limit == 100000


def test_policy_ids_forbid_qualified_separator(mvp_policy_package):
    path = "schemas/policy-package.schema.json"
    for mutation in (
        lambda value: value.update(package_id="cn-pension:beijing"),
        lambda value: value["rules"][0].update(rule_id="beijing:flex-rate"),
    ):
        invalid = copy.deepcopy(mvp_policy_package)
        mutation(invalid)
        assert_invalid(path, invalid)


def test_mvp_policy_provenance_requires_official_gov_cn_authority(mvp_policy_package):
    path = "schemas/policy-package.schema.json"

    for url in (
        "https://example.com/policy",
        "https://private-blog.example/policy",
        "https://gov.cn.example.com/policy",
    ):
        invalid = copy.deepcopy(mvp_policy_package)
        invalid["provenance"][0]["url"] = url
        assert_invalid(path, invalid)

    invalid = copy.deepcopy(mvp_policy_package)
    del invalid["provenance"][0]["authority_level"]
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(mvp_policy_package)
    invalid["provenance"][0]["authority_level"] = "PRIVATE_BLOG"
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(mvp_policy_package)
    invalid["rules"][0]["results"][0]["value_type"] = "UNTYPED"
    assert_invalid(path, invalid)


@pytest.mark.parametrize(
    "authority_level",
    ["PROVINCIAL_HRSS", "MUNICIPAL_GOVERNMENT", "MUNICIPAL_HRSS"],
)
def test_policy_schema_accepts_supported_local_authorities(
    mvp_policy_package, authority_level
):
    valid = copy.deepcopy(mvp_policy_package)
    valid["provenance"][0]["authority_level"] = authority_level

    assert_valid("schemas/policy-package.schema.json", valid)


def test_policy_package_supports_production_approved_only_with_dual_approval_and_signature(
    mvp_policy_package,
):
    path = "schemas/policy-package.schema.json"
    package = copy.deepcopy(mvp_policy_package)
    package.update(
        review_status="PRODUCTION_APPROVED",
        execution_modes=["PRODUCTION"],
        local_only=False,
        transaction_from="2026-08-11T13:00:00+08:00",
        production_approval={
            "domain_reviewer_id": "domain-reviewer-01",
            "approver_ids": ["approver-01", "approver-02"],
            "approved_at": "2026-08-11T11:00:00+08:00",
            "signature": "sig:synthetic-package-signature",
            "published_at": "2026-08-11T12:00:00+08:00",
        },
    )
    assert_valid(path, package)

    invalid = copy.deepcopy(package)
    invalid["production_approval"]["approver_ids"] = ["approver-01"]
    assert_invalid(path, invalid)

    for gate in ("schema_validation_passed", "rule_tests_passed"):
        invalid = copy.deepcopy(package)
        invalid["engineering_review"][gate] = False
        assert_invalid(path, invalid)


@pytest.fixture
def tool_envelope() -> dict:
    return {
        "schema_version": "1.0.0",
        "tool_name": "analyze",
        "tool_version": "0.1.0",
        "run_id": "run-synthetic-001",
        "request_id": "request-synthetic-001",
        "status": "partial",
        "data": {"run_id": "run-synthetic-001", "result_ref": "runs/run-synthetic-001/result.json"},
        "warnings": [
            {"code": "CAPABILITY_PARTIAL", "message": "Synthetic limitation", "related_refs": ["cap-gap"]}
        ],
        "errors": [],
        "provenance": [DIGEST],
        "metrics": {"duration_ms": 12, "cache_hit": False},
    }


def test_tool_envelope_enforces_status_payload_contract(tool_envelope):
    path = "schemas/tool-envelope.schema.json"
    assert_valid(path, tool_envelope)

    invalid = copy.deepcopy(tool_envelope)
    invalid["warnings"] = []
    assert_invalid(path, invalid)

    success = copy.deepcopy(tool_envelope)
    success.update(status="success", data={}, provenance=["official-source-001", DIGEST])
    success["warnings"] = []
    assert_valid(path, success)

    invalid = copy.deepcopy(tool_envelope)
    invalid.update(status="error", data=None)
    invalid["warnings"] = []
    invalid["errors"] = []
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(success)
    invalid["provenance"] = [""]
    assert_invalid(path, invalid)


@pytest.fixture
def run_manifest() -> dict:
    return {
        "schema_version": "2.0.0",
        "manifest_version": "2.0.0",
        "run_id": "run-synthetic-001",
        "parent_run_id": None,
        "created_at": "2026-08-11T10:00:00+08:00",
        "analysis_mode": "LOCAL_MVP",
        "review_statuses": ["MVP_REVIEWED"],
        "component_versions": {
            "engine": "0.1.0",
            "input_schema": "1.0.0",
            "output_schema": "2.0.0",
            "manifest_schema": "2.0.0",
            "rounding_profile": "CNY-half-up-v1",
        },
        "policy_rulesets": [
            {
                "package_id": "cn-pension/beijing-flex/2026.1",
                "ruleset_id": "cn-pension/beijing-flex/2026.1",
                "version": "2026.1.0",
                "digest": OTHER_DIGEST,
            }
        ],
        "input_snapshot_digest": DIGEST,
        "assumption_set_digest": DIGEST,
        "objective_digest": OTHER_DIGEST,
        "engine_version": "0.1.0",
        "rounding_profile": "CNY-half-up-v1",
        "output_digest": DIGEST,
        "artifact_digests": [OTHER_DIGEST],
        "adapter_versions": {"policy_repository": "0.1.0", "report_renderer": "0.1.0"},
        "digests": {
            "input": DIGEST,
            "rules": [OTHER_DIGEST],
            "assumptions": DIGEST,
            "objective": OTHER_DIGEST,
            "output": DIGEST,
            "artifacts": [OTHER_DIGEST],
        },
        "validation": {
            "input_schema_valid": True,
            "policy_schema_valid": True,
            "output_schema_valid": True,
            "invariants_valid": True,
        },
        "validation_suite": "architecture-and-domain-v1",
        "validation_status": "passed",
        "warnings_count": 0,
        "unresolved_conflicts_count": 0,
        "duration_ms": 512,
        "publication_status": "LOCAL_ONLY",
    }


def test_run_manifest_requires_reproduction_digests_and_blocks_mvp_publication(run_manifest):
    path = "schemas/run-manifest.schema.json"
    assert_valid(path, run_manifest)

    invalid = copy.deepcopy(run_manifest)
    del invalid["digests"]["objective"]
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(run_manifest)
    invalid["publication_status"] = "PUBLISHED"
    assert_invalid(path, invalid)


def test_run_manifest_explicitly_validates_v2_migration_of_documented_v1_shape(run_manifest):
    path = "schemas/run-manifest.schema.json"
    documented_fields = (
        "manifest_version",
        "parent_run_id",
        "policy_rulesets",
        "input_snapshot_digest",
        "assumption_set_digest",
        "objective_digest",
        "engine_version",
        "rounding_profile",
        "output_digest",
        "artifact_digests",
        "adapter_versions",
        "validation_suite",
        "validation_status",
        "warnings_count",
        "unresolved_conflicts_count",
        "duration_ms",
    )
    for field in documented_fields:
        invalid = copy.deepcopy(run_manifest)
        del invalid[field]
        assert_invalid(path, invalid)

    legacy_version = copy.deepcopy(run_manifest)
    legacy_version["schema_version"] = "1.0.0"
    legacy_version["manifest_version"] = "1.0.0"
    assert_invalid(path, legacy_version)

    invalid = copy.deepcopy(run_manifest)
    del invalid["policy_rulesets"][0]["version"]
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(run_manifest)
    del invalid["policy_rulesets"][0]["ruleset_id"]
    assert_invalid(path, invalid)


@pytest.fixture
def analysis_output() -> dict:
    money = lambda amount: {"currency": "CNY", "amount": amount}
    return {
        "schema_version": "2.0.0",
        "run_id": "run-synthetic-001",
        "status": "success",
        "snapshot": {
            "input_digest": DIGEST,
            "ruleset_digests": [OTHER_DIGEST],
            "assumption_digest": DIGEST,
            "as_of_effective_date": "2026-08-11",
            "as_known_at": "2026-08-11T10:00:00+08:00",
            "engine_version": "0.1.0",
            "schema_version": "2.0.0",
            "rounding_profile": "CNY-half-up-v1",
        },
        "capabilities": [
            {
                "capability_id": "CONTRIBUTION_GAP",
                "status": "AVAILABLE",
                "required_fact_ids": ["fact-account"],
                "satisfied_fact_ids": ["fact-account"],
                "missing_fact_ids": [],
                "blocker_codes": [],
                "limitations": [],
            }
        ],
        "contribution_facts": [
            {
                "fact_id": "fact-account",
                "scheme": "enterprise_employee_basic_pension",
                "fact_type": "ACCOUNT_SUMMARY",
                "period_from": "2011-09",
                "period_to": "2026-07",
                "reported_months": 179,
                "recognized_month_basis": "DEDUPLICATED_MONTH_DETAIL",
                "source_refs": ["synthetic-account-summary"],
            }
        ],
        "gap_results": [
            {
                "result_id": "gap-primary",
                "scheme": "enterprise_employee_basic_pension",
                "requirement_months": 180,
                "confirmed_months": 179,
                "remaining_months": 1,
                "basis_fact_refs": ["fact-account"],
                "rule_refs": ["minimum-years-rule"],
                "is_primary": True,
            }
        ],
        "policy_evidence": [
            {
                "package_id": "cn-pension/beijing-flex/2026.1",
                "package_digest": OTHER_DIGEST,
                "review_status": "MVP_REVIEWED",
                "rule_ids": ["minimum-years-rule"],
                "source_refs": [
                    {
                        "source_id": "national-official-001",
                        "url": "https://www.gov.cn/example",
                        "locator": "Article 16",
                        "source_digest": DIGEST,
                    }
                ],
                "effective_on": "2026-08-11",
                "known_at": "2026-08-11T10:00:00+08:00",
            }
        ],
        "review_notice": {
            "analysis_mode": "LOCAL_MVP",
            "package_review_statuses": ["MVP_REVIEWED"],
            "notice": "NOT_PRODUCTION_APPROVED",
            "official_eligibility_claim": False,
        },
        "eligibility_assessments": [],
        "record_conflicts": [],
        "policy_ambiguities": [],
        "assumptions": [],
        "scenarios": [
            {
                "scenario_id": "continue-one-month",
                "feasibility": "FEASIBLE",
                "capability_refs": ["CONTRIBUTION_GAP"],
                "horizon": {"start_month": "2026-09", "end_month": "2026-09", "inclusive_months": 1},
                "actions": [
                    {"month": "2026-09", "action_type": "CONTINUE_CONTRIBUTING", "assumption_refs": []}
                ],
                "monthly_cash_flows": [
                    {
                        "month": "2026-09",
                        "pension_contribution": money("1400.00"),
                        "medical_contribution": money("420.00"),
                        "unemployment_contribution": money("70.00"),
                        "subsidy": money("0.00"),
                        "net_outflow": money("1890.00"),
                        "cumulative_outflow": money("1890.00"),
                    }
                ],
                "outcomes": {
                    "ending_confirmed_months": 180,
                    "ending_gap_months": 0,
                    "total_pension_contribution": money("1400.00"),
                    "total_medical_contribution": money("420.00"),
                    "total_unemployment_contribution": money("70.00"),
                    "total_subsidy": money("0.00"),
                    "total_net_outflow": money("1890.00"),
                },
                "thresholds": [
                    {"threshold_id": "minimum-months", "metric": "confirmed_months", "operator": ">=", "value": "180"}
                ],
                "sensitivity": {"mode": "THRESHOLD", "assumption_refs": [], "summary": "One month closes the gap."},
            }
        ],
        "recommendation": {
            "scenario_id": "continue-one-month",
            "objective": "MINIMUM_COMPLIANCE_COST",
            "capability_dependencies": [
                {"capability_id": "CONTRIBUTION_GAP", "status": "AVAILABLE"}
            ],
            "assumption_refs": [],
            "limitations": ["Local informational screening only."],
            "thresholds": ["Recommendation changes if confirmed months are already 180 or more."],
            "invalidators": ["Official account record changes."],
            "review_triggers": ["Policy package or contribution record changes."],
        },
        "warnings": [],
        "errors": [],
    }


def test_analysis_output_covers_facts_gaps_policy_cash_flow_scenarios_and_recommendation(analysis_output):
    path = "docs/schemas/analysis-output.schema.json"
    assert_valid(path, analysis_output)

    invalid = copy.deepcopy(analysis_output)
    invalid["scenarios"][0]["monthly_cash_flows"][0]["pension_contribution"] = "1400.00"
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(analysis_output)
    del invalid["scenarios"][0]["outcomes"]
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(analysis_output)
    del invalid["recommendation"]["limitations"]
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(analysis_output)
    invalid["review_notice"]["notice"] = "APPROVED"
    assert_invalid(path, invalid)

    for field in (
        "pension_contribution",
        "medical_contribution",
        "unemployment_contribution",
        "subsidy",
        "net_outflow",
        "cumulative_outflow",
    ):
        invalid = copy.deepcopy(analysis_output)
        invalid["scenarios"][0]["monthly_cash_flows"][0][field]["amount"] = "-0.01"
        assert_invalid(path, invalid)


def test_conflict_and_policy_ambiguity_refs_are_nonempty_unique_sets(analysis_output):
    path = "docs/schemas/analysis-output.schema.json"
    conflict = {
        "conflict_id": "conflict-001",
        "fact_scope": "pension months",
        "assertion_refs": ["assertion-a", "assertion-b"],
        "status": "UNRESOLVED",
        "resolution_evidence_refs": [],
    }
    ambiguity = {
        "ambiguity_id": "ambiguity-001",
        "capability_id": "CONTRIBUTION_GAP",
        "competing_rule_ids": ["rule-a", "rule-b"],
        "conflict_dimensions": ["EFFECTIVE_TIME"],
        "effect": "BLOCKS_CAPABILITY",
    }

    invalid = copy.deepcopy(analysis_output)
    invalid["record_conflicts"] = [conflict | {"assertion_refs": ["assertion-a", "assertion-a"]}]
    assert_invalid(path, invalid)

    for rule_ids, dimensions in (
        (["rule-a", "rule-a"], ["EFFECTIVE_TIME"]),
        (["rule-a", "rule-b"], []),
        (["rule-a", "rule-b"], ["EFFECTIVE_TIME", "EFFECTIVE_TIME"]),
    ):
        invalid = copy.deepcopy(analysis_output)
        invalid["policy_ambiguities"] = [
            ambiguity | {"competing_rule_ids": rule_ids, "conflict_dimensions": dimensions}
        ]
        assert_invalid(path, invalid)


def test_capability_statuses_require_consistent_fact_and_non_fact_blockers(analysis_output):
    path = "docs/schemas/analysis-output.schema.json"

    invalid = copy.deepcopy(analysis_output)
    invalid["capabilities"][0]["missing_fact_ids"] = ["missing-fact"]
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(analysis_output)
    invalid["capabilities"][0]["blocker_codes"] = ["POLICY_AMBIGUITY"]
    assert_invalid(path, invalid)

    partial = copy.deepcopy(analysis_output)
    partial["status"] = "partial"
    partial["warnings"] = [
        {"code": "CAPABILITY_LIMITED", "message": "Synthetic limitation", "related_refs": []}
    ]
    partial["capabilities"][0].update(
        status="PARTIAL", missing_fact_ids=[], blocker_codes=[], limitations=["Bounded estimate only."]
    )
    assert_valid(path, partial)

    invalid = copy.deepcopy(partial)
    invalid["capabilities"][0]["limitations"] = []
    assert_invalid(path, invalid)

    blocked = copy.deepcopy(partial)
    blocked["capabilities"][0].update(
        capability_id="SUBSIDY_ELIGIBILITY",
        status="BLOCKED",
        missing_fact_ids=[],
        blocker_codes=["AMBIGUOUS_POLICY_RULE"],
    )
    assert_invalid(path, blocked)

    blocked["capabilities"].insert(
        0,
        {
            "capability_id": "CONTRIBUTION_GAP",
            "status": "AVAILABLE",
            "required_fact_ids": ["fact-account"],
            "satisfied_fact_ids": ["fact-account"],
            "missing_fact_ids": [],
            "blocker_codes": [],
            "limitations": [],
        },
    )
    assert_valid(path, blocked)

    invalid = copy.deepcopy(blocked)
    invalid["capabilities"][1]["blocker_codes"] = []
    assert_invalid(path, invalid)


def test_partial_output_requires_progress_and_rejects_all_blocked(analysis_output):
    path = "docs/schemas/analysis-output.schema.json"
    partial = copy.deepcopy(analysis_output)
    partial["status"] = "partial"
    partial["warnings"] = [
        {"code": "CAPABILITY_BLOCKED", "message": "Synthetic limitation", "related_refs": []}
    ]
    partial["capabilities"].append(
        {
            "capability_id": "SUBSIDY_ELIGIBILITY",
            "status": "BLOCKED",
            "required_fact_ids": ["employment-status"],
            "satisfied_fact_ids": [],
            "missing_fact_ids": ["employment-status"],
            "blocker_codes": ["MISSING_REQUIRED_FACT"],
            "limitations": ["Employment status is missing."],
        }
    )
    assert_valid(path, partial)

    all_blocked = copy.deepcopy(partial)
    all_blocked["capabilities"] = [all_blocked["capabilities"][1]]
    assert_invalid(path, all_blocked)


def test_recommendation_dependencies_reject_blocked_capabilities(analysis_output):
    path = "docs/schemas/analysis-output.schema.json"
    invalid = copy.deepcopy(analysis_output)
    invalid["recommendation"]["capability_dependencies"][0]["status"] = "BLOCKED"
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(analysis_output)
    invalid["recommendation"]["capability_dependencies"][0]["unexpected"] = True
    assert_invalid(path, invalid)


def test_distribution_parameters_are_named_strict_scalars(analysis_output):
    path = "docs/schemas/analysis-output.schema.json"
    with_distribution = copy.deepcopy(analysis_output)
    with_distribution["assumptions"] = [
        {
            "event_id": "reemployment-event",
            "event_definition": "Synthetic reemployment model",
            "source_type": "official_statistic",
            "modeling_mode": "EVIDENCE_BACKED_PROBABILITY",
            "distribution": {
                "family": "beta",
                "parameters": {"alpha": 2.0, "beta": 5.0},
            },
            "source_date": "2026-01-01",
            "population": "Synthetic population",
            "provenance_refs": ["official-statistic-001"],
            "approved_by": "reviewer-001",
            "expires_at": "2027-01-01T00:00:00+08:00",
            "dependency_treatment": "Sensitivity only",
        }
    ]
    assert_valid(path, with_distribution)

    invalid = copy.deepcopy(with_distribution)
    invalid["assumptions"][0]["distribution"]["parameters"]["alpha"] = {"nested": 2.0}
    assert_invalid(path, invalid)

    invalid = copy.deepcopy(with_distribution)
    invalid["assumptions"][0]["distribution"]["parameters"]["bad-name!"] = 2.0
    assert_invalid(path, invalid)
