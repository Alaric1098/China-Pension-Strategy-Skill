import copy

import pytest


def output_with_dependency() -> dict:
    def money(amount):
        return {"currency": "CNY", "amount": amount}

    return {
        "status": "success",
        "capabilities": [
            {
                "capability_id": "CONTRIBUTION_GAP",
                "status": "AVAILABLE",
                "required_fact_ids": ["fact-account"],
                "satisfied_fact_ids": ["fact-account"],
                "missing_fact_ids": [],
            }
        ],
        "recommendation": {
            "capability_dependencies": [
                {
                    "capability_id": "CONTRIBUTION_GAP",
                    "status": "AVAILABLE",
                }
            ]
        },
        "scenarios": [
            {
                "scenario_id": "cash-flow-scenario",
                "monthly_cash_flows": [
                    {
                        "month": "2026-09",
                        "pension_contribution": money("100.00"),
                        "medical_contribution": money("20.00"),
                        "unemployment_contribution": money("10.00"),
                        "subsidy": money("30.00"),
                        "net_outflow": money("100.00"),
                        "cumulative_outflow": money("100.00"),
                    },
                    {
                        "month": "2026-10",
                        "pension_contribution": money("50.00"),
                        "medical_contribution": money("10.00"),
                        "unemployment_contribution": money("5.00"),
                        "subsidy": money("15.00"),
                        "net_outflow": money("50.00"),
                        "cumulative_outflow": money("150.00"),
                    },
                ],
                "outcomes": {
                    "total_pension_contribution": money("150.00"),
                    "total_medical_contribution": money("30.00"),
                    "total_unemployment_contribution": money("15.00"),
                    "total_subsidy": money("45.00"),
                    "total_net_outflow": money("150.00"),
                },
            }
        ],
    }


def test_output_semantics_accept_matching_recommendation_dependency():
    from china_pension_strategy.application.output_validation import validate_output_semantics

    validate_output_semantics(output_with_dependency())


@pytest.mark.parametrize(
    ("capability_id", "dependency_status", "message"),
    [
        ("UNKNOWN_CAPABILITY", "AVAILABLE", "unresolved capability dependency"),
        ("CONTRIBUTION_GAP", "PARTIAL", "dependency status mismatch"),
        ("CONTRIBUTION_GAP", "BLOCKED", "blocked capability dependency"),
    ],
)
def test_output_semantics_reject_invalid_recommendation_dependencies(
    capability_id, dependency_status, message
):
    from china_pension_strategy.application.output_validation import (
        OutputSemanticValidationError,
        validate_output_semantics,
    )

    output = copy.deepcopy(output_with_dependency())
    dependency = output["recommendation"]["capability_dependencies"][0]
    dependency.update(capability_id=capability_id, status=dependency_status)

    with pytest.raises(OutputSemanticValidationError, match=message):
        validate_output_semantics(output)


def test_output_semantics_rejects_success_with_unaccounted_required_fact():
    from china_pension_strategy.application.output_validation import (
        OutputSemanticValidationError,
        validate_output_semantics,
    )

    output = output_with_dependency()
    output["capabilities"][0]["required_fact_ids"].append("fact-neither-list")

    with pytest.raises(OutputSemanticValidationError, match="fact partition mismatch"):
        validate_output_semantics(output)


def test_output_semantics_rejects_duplicate_capability_ids_before_lookup():
    from china_pension_strategy.application.output_validation import (
        OutputSemanticValidationError,
        validate_output_semantics,
    )

    output = output_with_dependency()
    duplicate = copy.deepcopy(output["capabilities"][0])
    duplicate["status"] = "PARTIAL"
    output["capabilities"].append(duplicate)

    with pytest.raises(OutputSemanticValidationError, match="duplicate capability ID"):
        validate_output_semantics(output)


@pytest.mark.parametrize(
    ("required", "satisfied", "missing", "status", "message"),
    [
        (["fact-a", "fact-a"], ["fact-a"], [], "AVAILABLE", "duplicate fact ID"),
        (["fact-a"], ["fact-a", "fact-a"], [], "AVAILABLE", "duplicate fact ID"),
        (["fact-a"], [], ["fact-a", "fact-a"], "PARTIAL", "duplicate fact ID"),
        (["fact-a"], ["fact-a"], ["fact-a"], "PARTIAL", "fact partition overlap"),
        (["fact-a"], ["fact-a", "fact-extra"], [], "AVAILABLE", "fact partition mismatch"),
        (["fact-a"], ["fact-a"], ["fact-extra"], "PARTIAL", "fact partition mismatch"),
        (["fact-a"], [], ["fact-a"], "AVAILABLE", "AVAILABLE capability facts incomplete"),
    ],
)
def test_output_semantics_rejects_invalid_capability_fact_partitions(
    required, satisfied, missing, status, message
):
    from china_pension_strategy.application.output_validation import (
        OutputSemanticValidationError,
        validate_output_semantics,
    )

    output = output_with_dependency()
    capability = output["capabilities"][0]
    capability.update(
        status=status,
        required_fact_ids=required,
        satisfied_fact_ids=satisfied,
        missing_fact_ids=missing,
    )
    output["recommendation"]["capability_dependencies"][0]["status"] = status

    with pytest.raises(OutputSemanticValidationError, match=message):
        validate_output_semantics(output)


def test_output_semantics_rejects_incorrect_monthly_net_outflow():
    from china_pension_strategy.application.output_validation import (
        OutputSemanticValidationError,
        validate_output_semantics,
    )

    output = output_with_dependency()
    output["scenarios"][0]["monthly_cash_flows"][0]["net_outflow"]["amount"] = "99.99"

    with pytest.raises(OutputSemanticValidationError, match="monthly net outflow mismatch"):
        validate_output_semantics(output)


def test_output_semantics_rejects_incorrect_cumulative_progression():
    from china_pension_strategy.application.output_validation import (
        OutputSemanticValidationError,
        validate_output_semantics,
    )

    output = output_with_dependency()
    output["scenarios"][0]["monthly_cash_flows"][1]["cumulative_outflow"]["amount"] = "149.99"

    with pytest.raises(OutputSemanticValidationError, match="cumulative outflow mismatch"):
        validate_output_semantics(output)


@pytest.mark.parametrize(
    "field",
    [
        "total_pension_contribution",
        "total_medical_contribution",
        "total_unemployment_contribution",
        "total_subsidy",
        "total_net_outflow",
    ],
)
def test_output_semantics_rejects_outcome_total_mismatches(field):
    from china_pension_strategy.application.output_validation import (
        OutputSemanticValidationError,
        validate_output_semantics,
    )

    output = output_with_dependency()
    output["scenarios"][0]["outcomes"][field]["amount"] = "999.99"

    with pytest.raises(OutputSemanticValidationError, match="scenario outcome total mismatch"):
        validate_output_semantics(output)
