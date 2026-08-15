"""Post-schema consistency checks for run manifest compatibility fields."""

from collections.abc import Mapping


class ManifestSemanticValidationError(ValueError):
    """Raised when duplicated manifest compatibility fields disagree."""


def validate_manifest_semantics(manifest: Mapping[str, object]) -> None:
    """Reject disagreement between v1-compatible and grouped v2 fields."""
    component_versions = manifest["component_versions"]  # type: ignore[assignment]
    if manifest["engine_version"] != component_versions["engine"]:
        raise ManifestSemanticValidationError("engine version mismatch")
    if manifest["schema_version"] != component_versions["manifest_schema"]:
        raise ManifestSemanticValidationError("schema version mismatch")
    if manifest["rounding_profile"] != component_versions["rounding_profile"]:
        raise ManifestSemanticValidationError("rounding profile mismatch")

    digests = manifest["digests"]  # type: ignore[assignment]
    if manifest["input_snapshot_digest"] != digests["input"]:
        raise ManifestSemanticValidationError("input digest mismatch")
    if manifest["assumption_set_digest"] != digests["assumptions"]:
        raise ManifestSemanticValidationError("assumption digest mismatch")
    if manifest["objective_digest"] != digests["objective"]:
        raise ManifestSemanticValidationError("objective digest mismatch")
    if manifest["output_digest"] != digests["output"]:
        raise ManifestSemanticValidationError("output digest mismatch")

    rule_digests = [ruleset["digest"] for ruleset in manifest["policy_rulesets"]]  # type: ignore[union-attr]
    if rule_digests != digests["rules"]:
        raise ManifestSemanticValidationError("rule digest mismatch")
    if manifest["artifact_digests"] != digests["artifacts"]:
        raise ManifestSemanticValidationError("artifact digest mismatch")

    validation = manifest["validation"]  # type: ignore[assignment]
    if manifest["validation_status"] == "passed" and not all(validation.values()):
        raise ManifestSemanticValidationError("passed validation has failed fields")
