"""Post-schema consistency checks for run manifest compatibility fields."""

from collections.abc import Mapping
from typing import Any, cast


class ManifestSemanticValidationError(ValueError):
    """Raised when duplicated manifest compatibility fields disagree."""


def validate_manifest_semantics(manifest: Mapping[str, object]) -> None:
    """Reject disagreement between v1-compatible and grouped v2 fields."""
    record = cast(dict[str, Any], manifest)
    component_versions = record["component_versions"]
    if record["engine_version"] != component_versions["engine"]:
        raise ManifestSemanticValidationError("engine version mismatch")
    if record["schema_version"] != component_versions["manifest_schema"]:
        raise ManifestSemanticValidationError("schema version mismatch")
    if record["rounding_profile"] != component_versions["rounding_profile"]:
        raise ManifestSemanticValidationError("rounding profile mismatch")

    digests = record["digests"]
    if record["input_snapshot_digest"] != digests["input"]:
        raise ManifestSemanticValidationError("input digest mismatch")
    if record["assumption_set_digest"] != digests["assumptions"]:
        raise ManifestSemanticValidationError("assumption digest mismatch")
    if record["objective_digest"] != digests["objective"]:
        raise ManifestSemanticValidationError("objective digest mismatch")
    if record["output_digest"] != digests["output"]:
        raise ManifestSemanticValidationError("output digest mismatch")

    rule_digests = [ruleset["digest"] for ruleset in record["policy_rulesets"]]
    if rule_digests != digests["rules"]:
        raise ManifestSemanticValidationError("rule digest mismatch")
    if record["artifact_digests"] != digests["artifacts"]:
        raise ManifestSemanticValidationError("artifact digest mismatch")

    validation = record["validation"]
    if record["validation_status"] == "passed" and not all(validation.values()):
        raise ManifestSemanticValidationError("passed validation has failed fields")
