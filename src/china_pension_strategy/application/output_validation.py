"""Post-schema invariants for a completed analysis output."""

from collections.abc import Mapping
from decimal import Decimal


class OutputSemanticValidationError(ValueError):
    """Raised when references in a schema-valid output contradict each other."""


def validate_output_semantics(output: Mapping[str, object]) -> None:
    """Reject contradictory capability facts and recommendation dependencies."""
    capability_items = output["capabilities"]
    seen_capability_ids = set()
    for capability in capability_items:  # type: ignore[union-attr]
        capability_id = capability["capability_id"]
        if capability_id in seen_capability_ids:
            raise OutputSemanticValidationError(
                f"duplicate capability ID: {capability_id}"
            )
        seen_capability_ids.add(capability_id)

    capabilities = {}
    for capability in capability_items:  # type: ignore[union-attr]
        capability_id = capability["capability_id"]
        required = capability["required_fact_ids"]
        satisfied = capability["satisfied_fact_ids"]
        missing = capability["missing_fact_ids"]

        for partition_name, fact_ids in (
            ("required_fact_ids", required),
            ("satisfied_fact_ids", satisfied),
            ("missing_fact_ids", missing),
        ):
            if len(fact_ids) != len(set(fact_ids)):
                raise OutputSemanticValidationError(
                    f"duplicate fact ID in {partition_name}: {capability_id}"
                )

        required_set = set(required)
        satisfied_set = set(satisfied)
        missing_set = set(missing)
        if satisfied_set & missing_set:
            raise OutputSemanticValidationError(
                f"fact partition overlap: {capability_id}"
            )
        if satisfied_set | missing_set != required_set:
            raise OutputSemanticValidationError(
                f"fact partition mismatch: {capability_id}"
            )
        if capability["status"] == "AVAILABLE" and (
            missing_set or satisfied_set != required_set
        ):
            raise OutputSemanticValidationError(
                f"AVAILABLE capability facts incomplete: {capability_id}"
            )

        capabilities[capability_id] = capability["status"]

    cash_fields = (
        "pension_contribution",
        "medical_contribution",
        "unemployment_contribution",
        "subsidy",
        "net_outflow",
    )
    outcome_fields = {field: f"total_{field}" for field in cash_fields}
    for scenario in output.get("scenarios", []):  # type: ignore[union-attr]
        totals = {field: Decimal("0.00") for field in cash_fields}
        cumulative = Decimal("0.00")
        for cash_flow in scenario["monthly_cash_flows"]:
            amounts = {
                field: Decimal(cash_flow[field]["amount"])
                for field in cash_fields
            }
            expected_net = (
                amounts["pension_contribution"]
                + amounts["medical_contribution"]
                + amounts["unemployment_contribution"]
                - amounts["subsidy"]
            )
            if amounts["net_outflow"] != expected_net:
                raise OutputSemanticValidationError(
                    f"monthly net outflow mismatch: {scenario['scenario_id']} "
                    f"{cash_flow['month']}"
                )

            cumulative += amounts["net_outflow"]
            if Decimal(cash_flow["cumulative_outflow"]["amount"]) != cumulative:
                raise OutputSemanticValidationError(
                    f"cumulative outflow mismatch: {scenario['scenario_id']} "
                    f"{cash_flow['month']}"
                )
            for field in cash_fields:
                totals[field] += amounts[field]

        for field, outcome_field in outcome_fields.items():
            outcome = Decimal(scenario["outcomes"][outcome_field]["amount"])
            if outcome != totals[field]:
                raise OutputSemanticValidationError(
                    f"scenario outcome total mismatch: {scenario['scenario_id']} "
                    f"{outcome_field}"
                )

    recommendation = output.get("recommendation")
    if recommendation is None:
        return

    for dependency in recommendation["capability_dependencies"]:  # type: ignore[index,union-attr]
        capability_id = dependency["capability_id"]
        dependency_status = dependency["status"]
        if capability_id not in capabilities:
            raise OutputSemanticValidationError(
                f"unresolved capability dependency: {capability_id}"
            )

        actual_status = capabilities[capability_id]
        if dependency_status == "BLOCKED" or actual_status == "BLOCKED":
            raise OutputSemanticValidationError(
                f"blocked capability dependency: {capability_id}"
            )
        if dependency_status != actual_status:
            raise OutputSemanticValidationError(
                f"dependency status mismatch: {capability_id} declares "
                f"{dependency_status}, capability is {actual_status}"
            )
