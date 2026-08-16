"""JSON-backed policy package repository for the bundled official data.

Loads every package under ``policy-data/packages``, validates it against the
policy-package JSON Schema, verifies its content digest, converts it into the
domain ``PolicyPackage`` model, and serves it through the ``PolicyRepository``
port. Refuses to serve any package that fails validation, digest checks, or
domain construction so the deterministic engine never sees invalid rules.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from china_pension_strategy.adapters.data_root import data_root
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
from china_pension_strategy.domain.values import YearMonth

DEFAULT_SCHEMA_PATH = data_root() / "schemas" / "policy-package.schema.json"
DEFAULT_PACKAGES_DIR = data_root() / "policy-data" / "packages"

CODE_PACKAGE_NOT_FOUND = "POLICY_PACKAGE_NOT_FOUND"
CODE_PACKAGE_INVALID = "POLICY_PACKAGE_INVALID"
CODE_PACKAGE_DIGEST_MISMATCH = "POLICY_PACKAGE_DIGEST_MISMATCH"
CODE_PACKAGE_NOT_DIRECTORY = "POLICY_PACKAGE_NOT_DIRECTORY"


class PolicyPackageError(Exception):
    """Base class for safe policy repository failures."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class PackageNotFoundError(PolicyPackageError):
    def __init__(self, path: str) -> None:
        super().__init__(CODE_PACKAGE_NOT_FOUND, f"no policy package found at: {path}")


class PackageInvalidError(PolicyPackageError):
    def __init__(self, detail: str) -> None:
        super().__init__(CODE_PACKAGE_INVALID, f"policy package is invalid: {detail}")


class PackageDigestMismatchError(PolicyPackageError):
    def __init__(self) -> None:
        super().__init__(
            CODE_PACKAGE_DIGEST_MISMATCH, "policy package content digest does not match"
        )


class PackageDirectoryError(PolicyPackageError):
    def __init__(self, path: str) -> None:
        super().__init__(
            CODE_PACKAGE_NOT_DIRECTORY, f"policy packages path is not a directory: {path}"
        )


def _scalar(value_type: object, value: object) -> object:
    if value_type == "DECIMAL":
        return Decimal(str(value))
    if value_type == "YEAR_MONTH":
        year, month = str(value).split("-")
        return YearMonth(int(year), int(month))
    if value_type == "DATE":
        return date.fromisoformat(str(value))
    if value_type == "INTEGER":
        if isinstance(value, bool) or not isinstance(value, int):
            raise PackageInvalidError(f"INTEGER scalar is not an integer: {value!r}")
        return value
    if value_type == "BOOLEAN":
        if not isinstance(value, bool):
            raise PackageInvalidError(f"BOOLEAN scalar is not a boolean: {value!r}")
        return value
    if value_type == "STRING":
        if not isinstance(value, str):
            raise PackageInvalidError(f"STRING scalar is not a string: {value!r}")
        return value
    if value_type == "NULL":
        if value is not None:
            raise PackageInvalidError(f"NULL scalar is not null: {value!r}")
        return None
    raise PackageInvalidError(f"unsupported scalar value_type {value_type!r}")


def _expression(expression: Mapping[str, object]) -> dict[str, object]:
    expression = cast(dict[str, Any], expression)
    kind = expression.get("kind")
    if kind == "LITERAL":
        return {
            **expression,
            "value": _scalar(expression["value_type"], expression["value"]),
        }
    if kind == "EXPRESSION":
        return {
            **expression,
            "operands": [_expression(operand) for operand in expression["operands"]],
        }
    if kind == "REFERENCE":
        return dict(expression)
    raise PackageInvalidError(f"unsupported expression kind {kind!r}")


def _condition(condition: Mapping[str, object]) -> dict[str, object]:
    return {
        **condition,
        "value": _scalar(condition["value_type"], condition["value"]),
    }


def _source(record: Mapping[str, object]) -> PolicySource:
    record = cast(dict[str, Any], record)
    return PolicySource(
        source_id=record["source_id"],
        url=record["url"],
        issuing_authority=record["issuing_authority"],
        authority_level=record["authority_level"],
        document_number=record["document_number"],
        publication_date=date.fromisoformat(str(record["publication_date"])),
        retrieved_at=datetime.fromisoformat(str(record["retrieved_at"])),
        locator=record["locator"],
        source_digest=record["source_digest"],
    )


def _rule(record: Mapping[str, object]) -> PolicyRule:
    record = cast(dict[str, Any], record)
    rule_type = RuleType(record["rule_type"])
    input_types = {
        declaration["input_id"]: declaration["value_type"] for declaration in record["inputs"]
    }
    result_types = {result["output_field"]: result["value_type"] for result in record["results"]}
    parameters = {
        name: {**declaration, "value": _scalar(declaration["value_type"], declaration["value"])}
        for name, declaration in record["parameters"].items()
    }
    conditions = tuple(_condition(condition) for condition in record["conditions"])
    results = tuple(
        {**result, "value": _expression(result["value"])} for result in record["results"]
    )
    test_vectors = tuple(
        {
            "vector_id": vector["vector_id"],
            "input": {
                key: _scalar(input_types[key], value) for key, value in vector["input"].items()
            },
            "expected": {
                key: _scalar(result_types[key], value) for key, value in vector["expected"].items()
            },
        }
        for vector in record["test_vectors"]
    )
    input_domains: dict[str, tuple[object, ...]] | None = None
    decision_rows: tuple[dict[str, Any], ...] = ()
    if rule_type is RuleType.DECISION_TABLE:
        input_domains = {
            input_id: tuple(
                _scalar(input_types[input_id], value) for value in record["input_domains"][input_id]
            )
            for input_id in record["input_domains"]
        }
        decision_rows = tuple(
            {
                "row_id": row["row_id"],
                "conditions": tuple(_condition(condition) for condition in row["conditions"]),
                "results": tuple(
                    {**result, "value": _expression(result["value"])} for result in row["results"]
                ),
            }
            for row in record["decision_rows"]
        )
    return PolicyRule(
        rule_id=record["rule_id"],
        rule_type=rule_type,
        scheme=record["scheme"],
        topic=record["topic"],
        jurisdiction_role=JurisdictionRole(record["jurisdiction_role"]),
        population_scope=record["population_scope"],
        inputs=tuple(record["inputs"]),
        conditions=conditions,
        results=results,
        exceptions=tuple(record["exceptions"]),
        effective_from=date.fromisoformat(str(record["effective_from"])),
        effective_to=(
            date.fromisoformat(str(record["effective_to"])) if record["effective_to"] else None
        ),
        transaction_from=datetime.fromisoformat(str(record["transaction_from"])),
        transaction_to=(
            datetime.fromisoformat(str(record["transaction_to"]))
            if record["transaction_to"]
            else None
        ),
        legal_hierarchy=LegalHierarchy(record["legal_hierarchy"]),
        explicit_override_refs=tuple(record["explicit_override_refs"]),
        source_refs=tuple(record["source_refs"]),
        parameters=parameters,
        test_vectors=test_vectors,
        input_domains=input_domains,
        decision_rows=decision_rows,
    )


def _engineering_review(record: Mapping[str, object]) -> EngineeringReview:
    record = cast(dict[str, Any], record)
    return EngineeringReview(
        reviewer_id=record["reviewer_id"],
        reviewed_at=datetime.fromisoformat(str(record["reviewed_at"])),
        schema_validation_passed=record["schema_validation_passed"],
        rule_tests_passed=record["rule_tests_passed"],
    )


def _production_approval(record: object) -> ProductionApproval | None:
    if record is None:
        return None
    approval = cast(dict[str, Any], record)
    return ProductionApproval(
        domain_reviewer_id=approval["domain_reviewer_id"],
        approver_ids=tuple(approval["approver_ids"]),
        approved_at=datetime.fromisoformat(str(approval["approved_at"])),
        signature=approval["signature"],
        published_at=datetime.fromisoformat(str(approval["published_at"])),
    )


def build_package(record: Mapping[str, object]) -> PolicyPackage:
    """Convert one validated package JSON record into a domain package."""
    record = cast(dict[str, Any], record)
    return PolicyPackage(
        schema_version=record["schema_version"],
        package_id=record["package_id"],
        version=record["version"],
        scheme=record["scheme"],
        jurisdiction=record["jurisdiction"],
        topic=record["topic"],
        review_status=ReviewStatus(record["review_status"]),
        execution_modes=tuple(AnalysisMode(mode) for mode in record["execution_modes"]),
        local_only=record["local_only"],
        engine_compatibility=record["engine_compatibility"],
        effective_from=date.fromisoformat(str(record["effective_from"])),
        effective_to=(
            date.fromisoformat(str(record["effective_to"])) if record["effective_to"] else None
        ),
        transaction_from=datetime.fromisoformat(str(record["transaction_from"])),
        transaction_to=(
            datetime.fromisoformat(str(record["transaction_to"]))
            if record["transaction_to"]
            else None
        ),
        content_digest=record["content_digest"],
        provenance=tuple(_source(source) for source in record["provenance"]),
        rules=tuple(_rule(rule) for rule in record["rules"]),
        engineering_review=_engineering_review(record["engineering_review"]),
        production_approval=_production_approval(record.get("production_approval")),
        historical=bool(record.get("historical", False)),
    )


def canonical_content_digest(package: Mapping[str, object]) -> str:
    """Recompute the content digest the way the package generator does."""
    without = {key: value for key, value in package.items() if key != "content_digest"}
    canonical = json.dumps(without, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class JsonPolicyRepository:
    """Loads official policy packages from the bundled JSON files."""

    def __init__(
        self,
        packages_dir: str | Path | None = None,
        schema_path: str | Path | None = None,
    ) -> None:
        self._packages_dir = (
            Path(packages_dir) if packages_dir is not None else DEFAULT_PACKAGES_DIR
        )
        schema_file = Path(schema_path) if schema_path is not None else DEFAULT_SCHEMA_PATH
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        self._validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def list_packages(self) -> Iterable[PolicyPackage]:
        if not self._packages_dir.is_dir() or not any(self._packages_dir.glob("*.json")):
            raise PackageDirectoryError(str(self._packages_dir))
        packages = []
        for path in sorted(self._packages_dir.glob("*.json")):
            packages.append(self.load_package(path))
        return tuple(packages)

    def load_package(self, path: str | Path) -> PolicyPackage:
        package_path = Path(path)
        if not package_path.is_file():
            raise PackageNotFoundError(str(package_path))
        try:
            record = json.loads(package_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise PackageInvalidError(f"not valid JSON: {error}") from error
        if not isinstance(record, Mapping):
            raise PackageInvalidError("<root> is not an object")
        errors = sorted(self._validator.iter_errors(record), key=lambda error: list(error.path))
        if errors:
            details = "; ".join(
                "/".join(str(part) for part in error.path) or "<root>" for error in errors[:3]
            )
            raise PackageInvalidError(details)
        if record.get("content_digest") != canonical_content_digest(record):
            raise PackageDigestMismatchError()
        try:
            return build_package(record)
        except (KeyError, TypeError, ValueError) as error:
            raise PackageInvalidError(str(error)) from error
