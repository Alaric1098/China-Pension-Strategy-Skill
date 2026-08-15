"""Tests for the JSON policy package repository adapter."""

import json
from pathlib import Path

import pytest

from china_pension_strategy.adapters.policies.json_policy_repository import (
    JsonPolicyRepository,
    PackageDigestMismatchError,
    PackageDirectoryError,
    PackageInvalidError,
    PackageNotFoundError,
    build_package,
    canonical_content_digest,
)
from china_pension_strategy.domain.policy import (
    AnalysisMode,
    ReviewStatus,
    RuleType,
)

ROOT = Path(__file__).resolve().parents[2]
REAL_PACKAGES_DIR = ROOT / "policy-data" / "packages"
REAL_SCHEMA_PATH = ROOT / "schemas" / "policy-package.schema.json"


def test_repository_loads_all_official_packages() -> None:
    repository = JsonPolicyRepository(
        packages_dir=REAL_PACKAGES_DIR, schema_path=REAL_SCHEMA_PATH
    )
    packages = tuple(repository.list_packages())
    names = {package.package_id for package in packages}
    assert "cn-pension/beijing/flex-employment-2026.1" in names
    assert "cn-pension/beijing/flex-subsidy-2026.1" in names
    assert "cn-pension/national/enterprise-minimum-2026.1" in names
    assert all(package.review_status is ReviewStatus.MVP_REVIEWED for package in packages)
    assert all(
        package.execution_modes == (AnalysisMode.LOCAL_MVP,) for package in packages
    )


def test_repository_converts_rules_with_typed_scalars() -> None:
    repository = JsonPolicyRepository(
        packages_dir=REAL_PACKAGES_DIR, schema_path=REAL_SCHEMA_PATH
    )
    package = repository.load_package(
        REAL_PACKAGES_DIR / "beijing-flex-employment.json"
    )
    contribution = next(
        rule
        for rule in package.rules
        if rule.rule_id == "beijing-flex-pension-contribution"
    )
    assert contribution.rule_type is RuleType.POLICY_RULE
    assert contribution.conditions[0]["value"].as_tuple().exponent == -2


def test_repository_rejects_missing_file() -> None:
    repository = JsonPolicyRepository(
        packages_dir=REAL_PACKAGES_DIR, schema_path=REAL_SCHEMA_PATH
    )
    with pytest.raises(PackageNotFoundError) as excinfo:
        repository.load_package(ROOT / "policy-data" / "packages" / "missing.json")
    assert excinfo.value.code == "POLICY_PACKAGE_NOT_FOUND"


def test_repository_rejects_non_directory(tmp_path) -> None:
    repository = JsonPolicyRepository(packages_dir=tmp_path)
    with pytest.raises(PackageDirectoryError) as excinfo:
        repository.list_packages()
    assert excinfo.value.code == "POLICY_PACKAGE_NOT_DIRECTORY"


def test_repository_rejects_invalid_json(tmp_path) -> None:
    package = tmp_path / "broken.json"
    package.write_text("{not json", encoding="utf-8")
    repository = JsonPolicyRepository(packages_dir=tmp_path, schema_path=REAL_SCHEMA_PATH)
    with pytest.raises(PackageInvalidError) as excinfo:
        repository.load_package(package)
    assert excinfo.value.code == "POLICY_PACKAGE_INVALID"


def test_repository_rejects_schema_invalid_package(tmp_path) -> None:
    package = tmp_path / "bad.json"
    package.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "package_id": "bad",
                "version": "1.0.0",
                "scheme": "enterprise_employee_basic_pension",
                "jurisdiction": "CN-11",
                "topic": "minimum_contribution",
                "review_status": "MVP_REVIEWED",
                "execution_modes": ["LOCAL_MVP"],
                "local_only": True,
                "engine_compatibility": ">=0.1,<1.0",
                "effective_from": "2025-01-01",
                "effective_to": None,
                "transaction_from": "2026-08-11T12:00:00Z",
                "transaction_to": None,
                "content_digest": "sha256:" + "0" * 64,
                "provenance": [],
                "rules": [],
                "engineering_review": {
                    "reviewer_id": "engineer-a",
                    "reviewed_at": "2026-08-11T12:00:00Z",
                    "schema_validation_passed": True,
                    "rule_tests_passed": True,
                },
            }
        ),
        encoding="utf-8",
    )
    repository = JsonPolicyRepository(packages_dir=tmp_path, schema_path=REAL_SCHEMA_PATH)
    with pytest.raises(PackageInvalidError) as excinfo:
        repository.load_package(package)
    assert excinfo.value.code == "POLICY_PACKAGE_INVALID"


def test_repository_rejects_digest_mismatch(tmp_path) -> None:
    original = json.loads(
        (REAL_PACKAGES_DIR / "national-enterprise-pension.json").read_text(
            encoding="utf-8"
        )
    )
    tampered = dict(original)
    tampered["content_digest"] = "sha256:" + "f" * 64
    package = tmp_path / "tampered.json"
    package.write_text(json.dumps(tampered), encoding="utf-8")
    repository = JsonPolicyRepository(packages_dir=tmp_path, schema_path=REAL_SCHEMA_PATH)
    with pytest.raises(PackageDigestMismatchError) as excinfo:
        repository.load_package(package)
    assert excinfo.value.code == "POLICY_PACKAGE_DIGEST_MISMATCH"


def test_repository_detects_rule_level_tampering(tmp_path) -> None:
    original = json.loads(
        (REAL_PACKAGES_DIR / "national-enterprise-pension.json").read_text(
            encoding="utf-8"
        )
    )
    tampered = dict(original)
    tampered["rules"] = [
        {
            **rule,
            "results": [
                {
                    **result,
                    "value": {
                        **result["value"],
                        "value": (
                            not result["value"]["value"]
                            if isinstance(result["value"].get("value"), bool)
                            else result["value"]["value"]
                        ),
                    },
                }
                for result in rule["results"]
            ],
        }
        for rule in tampered["rules"]
    ]
    package = tmp_path / "tampered-rule.json"
    package.write_text(json.dumps(tampered), encoding="utf-8")
    repository = JsonPolicyRepository(packages_dir=tmp_path, schema_path=REAL_SCHEMA_PATH)
    with pytest.raises(PackageDigestMismatchError):
        repository.load_package(package)


def test_canonical_content_digest_is_stable_and_order_independent() -> None:
    record = json.loads(
        (REAL_PACKAGES_DIR / "beijing-flex-subsidy.json").read_text(encoding="utf-8")
    )
    first = canonical_content_digest(record)
    shuffled = dict(sorted(record.items()))
    assert canonical_content_digest(shuffled) == first
    assert record["content_digest"] == first


def test_build_package_rejects_missing_required_fields(tmp_path) -> None:
    record = json.loads(
        (REAL_PACKAGES_DIR / "beijing-flex-subsidy.json").read_text(encoding="utf-8")
    )
    del record["rules"]
    with pytest.raises(KeyError):
        build_package(record)
