import copy

import pytest


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def valid_manifest() -> dict:
    return {
        "schema_version": "2.0.0",
        "engine_version": "1.0.0",
        "rounding_profile": "CNY-half-up-v1",
        "component_versions": {
            "engine": "1.0.0",
            "manifest_schema": "2.0.0",
            "rounding_profile": "CNY-half-up-v1",
        },
        "input_snapshot_digest": DIGEST_A,
        "assumption_set_digest": DIGEST_A,
        "objective_digest": DIGEST_B,
        "output_digest": DIGEST_B,
        "artifact_digests": [DIGEST_A],
        "policy_rulesets": [{"digest": DIGEST_B}],
        "digests": {
            "input": DIGEST_A,
            "assumptions": DIGEST_A,
            "objective": DIGEST_B,
            "output": DIGEST_B,
            "rules": [DIGEST_B],
            "artifacts": [DIGEST_A],
        },
        "validation_status": "passed",
        "validation": {
            "input_schema_valid": True,
            "policy_schema_valid": True,
            "output_schema_valid": True,
            "invariants_valid": True,
        },
    }


def test_manifest_semantics_accept_matching_compatibility_fields():
    from china_pension_strategy.application.manifest_validation import validate_manifest_semantics

    validate_manifest_semantics(valid_manifest())


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("component_versions", "engine", "1.1.0", "engine version mismatch"),
        ("component_versions", "manifest_schema", "2.1.0", "schema version mismatch"),
        ("component_versions", "rounding_profile", "other", "rounding profile mismatch"),
        ("digests", "input", DIGEST_B, "input digest mismatch"),
        ("digests", "assumptions", DIGEST_B, "assumption digest mismatch"),
        ("digests", "objective", DIGEST_A, "objective digest mismatch"),
        ("digests", "output", DIGEST_A, "output digest mismatch"),
        ("digests", "rules", [DIGEST_A], "rule digest mismatch"),
        ("digests", "artifacts", [DIGEST_B], "artifact digest mismatch"),
        ("validation", "invariants_valid", False, "passed validation has failed fields"),
    ],
)
def test_manifest_semantics_reject_mismatched_duplicate_fields(section, field, value, message):
    from china_pension_strategy.application.manifest_validation import (
        ManifestSemanticValidationError,
        validate_manifest_semantics,
    )

    manifest = copy.deepcopy(valid_manifest())
    manifest[section][field] = value

    with pytest.raises(ManifestSemanticValidationError, match=message):
        validate_manifest_semantics(manifest)
