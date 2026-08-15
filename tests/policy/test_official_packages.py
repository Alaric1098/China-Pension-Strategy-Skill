"""Official policy packages and source records must stay schema-valid, domain-constructible, digest-consistent, and traceable to reference sections."""

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from china_pension_strategy.domain.policy import (
    AnalysisMode,
    EngineeringReview,
    JurisdictionRole,
    LegalHierarchy,
    PolicyPackage,
    PolicyRule,
    PolicySource,
    ReviewStatus,
    RuleType,
)
from china_pension_strategy.domain.values import YearMonth


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = ROOT / "policy-data" / "packages"
SOURCES_DIR = ROOT / "policy-data" / "sources"
REFERENCE_FILES = (ROOT / "references" / "national-rules.md",) + tuple(
    sorted((ROOT / "references" / "regions").glob("*.md"))
)
SCHEMA = "schemas/policy-package.schema.json"
AS_OF_EFFECTIVE = date(2026, 8, 11)
AS_KNOWN_AT = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
PACKAGE_PATHS = sorted(PACKAGES_DIR.glob("*.json"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_validator() -> Draft202012Validator:
    schema = load_json(ROOT / SCHEMA)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def canonical_source_digest(body: str) -> str:
    canonical = "\n".join(line.rstrip() for line in body.splitlines()).rstrip() + "\n"
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_content_digest(package: dict) -> str:
    without = {key: value for key, value in package.items() if key != "content_digest"}
    canonical = json.dumps(without, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reference_sections() -> dict[str, str]:
    sections: dict[str, str] = {}
    for path in REFERENCE_FILES:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        current: str | None = None
        body: list[str] = []
        for line in lines:
            match = re.match(r"^## 来源：(\S+)\s*$", line)
            if match:
                if current is not None:
                    sections[current] = "".join(body)
                current = match.group(1)
                body = []
            elif current is not None:
                body.append(line)
        if current is not None:
            sections[current] = "".join(body)
    return sections


def convert_scalar(value_type: object, value: object) -> object:
    if value_type == "DECIMAL":
        return Decimal(value)  # type: ignore[arg-type]
    if value_type == "YEAR_MONTH":
        year, month = str(value).split("-")
        return YearMonth(int(year), int(month))
    if value_type == "DATE":
        return date.fromisoformat(str(value))
    return value


def convert_expression(expression: dict) -> dict:
    kind = expression.get("kind")
    if kind == "LITERAL":
        return {**expression, "value": convert_scalar(expression["value_type"], expression["value"])}
    if kind == "EXPRESSION":
        return {
            **expression,
            "operands": [convert_expression(operand) for operand in expression["operands"]],
        }
    return expression


def convert_condition(condition: dict) -> dict:
    return {**condition, "value": convert_scalar(condition["value_type"], condition["value"])}


def build_source(record: dict) -> PolicySource:
    return PolicySource(
        source_id=record["source_id"],
        url=record["url"],
        issuing_authority=record["issuing_authority"],
        authority_level=record["authority_level"],
        document_number=record["document_number"],
        publication_date=date.fromisoformat(record["publication_date"]),
        retrieved_at=datetime.fromisoformat(record["retrieved_at"]),
        locator=record["locator"],
        source_digest=record["source_digest"],
    )


def build_rule(record: dict) -> PolicyRule:
    rule_type = RuleType(record["rule_type"])
    input_types = {decl["input_id"]: decl["value_type"] for decl in record["inputs"]}
    result_types = {result["output_field"]: result["value_type"] for result in record["results"]}
    parameters = {
        name: {**decl, "value": convert_scalar(decl["value_type"], decl["value"])}
        for name, decl in record["parameters"].items()
    }
    conditions = tuple(convert_condition(condition) for condition in record["conditions"])
    results = tuple(
        {**result, "value": convert_expression(result["value"])} for result in record["results"]
    )
    test_vectors = tuple(
        {
            "vector_id": vector["vector_id"],
            "input": {
                key: convert_scalar(input_types[key], value) for key, value in vector["input"].items()
            },
            "expected": {
                key: convert_scalar(result_types[key], value)
                for key, value in vector["expected"].items()
            },
        }
        for vector in record["test_vectors"]
    )
    decision_rows = ()
    input_domains = None
    if rule_type is RuleType.DECISION_TABLE:
        input_domains = {
            input_id: tuple(
                convert_scalar(input_types[input_id], value)
                for value in record["input_domains"][input_id]
            )
            for input_id in record["input_domains"]
        }
        decision_rows = tuple(
            {
                "row_id": row["row_id"],
                "conditions": tuple(convert_condition(condition) for condition in row["conditions"]),
                "results": tuple(
                    {**result, "value": convert_expression(result["value"])}
                    for result in row["results"]
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
        effective_from=date.fromisoformat(record["effective_from"]),
        effective_to=date.fromisoformat(record["effective_to"]) if record["effective_to"] else None,
        transaction_from=datetime.fromisoformat(record["transaction_from"]),
        transaction_to=datetime.fromisoformat(record["transaction_to"]) if record["transaction_to"] else None,
        legal_hierarchy=LegalHierarchy(record["legal_hierarchy"]),
        explicit_override_refs=tuple(record["explicit_override_refs"]),
        source_refs=tuple(record["source_refs"]),
        parameters=parameters,
        test_vectors=test_vectors,
        input_domains=input_domains,
        decision_rows=decision_rows,
    )


def build_package(record: dict) -> PolicyPackage:
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
        effective_from=date.fromisoformat(record["effective_from"]),
        effective_to=date.fromisoformat(record["effective_to"]) if record["effective_to"] else None,
        transaction_from=datetime.fromisoformat(record["transaction_from"]),
        transaction_to=datetime.fromisoformat(record["transaction_to"]) if record["transaction_to"] else None,
        content_digest=record["content_digest"],
        provenance=tuple(build_source(source) for source in record["provenance"]),
        rules=tuple(build_rule(rule) for rule in record["rules"]),
        engineering_review=EngineeringReview(
            reviewer_id=record["engineering_review"]["reviewer_id"],
            reviewed_at=datetime.fromisoformat(record["engineering_review"]["reviewed_at"]),
            schema_validation_passed=record["engineering_review"]["schema_validation_passed"],
            rule_tests_passed=record["engineering_review"]["rule_tests_passed"],
        ),
        production_approval=None,
        historical=bool(record.get("historical", False)),
    )


@pytest.mark.parametrize("package_path", PACKAGE_PATHS, ids=lambda path: path.stem)
def test_official_package_validates_against_policy_package_schema(package_path):
    package = load_json(package_path)
    errors = sorted(
        schema_validator().iter_errors(package), key=lambda error: list(error.path)
    )
    assert not errors, "\n".join(error.message for error in errors)


@pytest.mark.parametrize("package_path", PACKAGE_PATHS, ids=lambda path: path.stem)
def test_official_package_constructs_as_domain_package_and_applies_now(package_path):
    package = build_package(load_json(package_path))
    assert package.review_status is ReviewStatus.MVP_REVIEWED
    assert package.execution_modes == (AnalysisMode.LOCAL_MVP,)
    assert package.local_only is True
    assert package.production_approval is None
    # Historical packages intentionally cover a past window only; they are
    # selected by as-of date, not expected to apply to the current date.
    if package.historical:
        # Historical package: effective in the past, known now.
        assert package.applies_at(date(2024, 6, 1), AS_KNOWN_AT)
        assert not package.applies_at(AS_OF_EFFECTIVE, AS_KNOWN_AT)
        for rule in package.rules:
            assert rule.applies_at(date(2024, 6, 1), AS_KNOWN_AT)
    else:
        assert package.applies_at(AS_OF_EFFECTIVE, AS_KNOWN_AT)
        for rule in package.rules:
            assert rule.applies_at(AS_OF_EFFECTIVE, AS_KNOWN_AT)
    assert package.engineering_review.schema_validation_passed
    assert package.engineering_review.rule_tests_passed


@pytest.mark.parametrize("package_path", PACKAGE_PATHS, ids=lambda path: path.stem)
def test_official_package_content_digest_covers_every_field_but_itself(package_path):
    package = load_json(package_path)
    assert package["content_digest"] == canonical_content_digest(package)


@pytest.mark.parametrize("package_path", PACKAGE_PATHS, ids=lambda path: path.stem)
def test_official_package_provenance_matches_source_records(package_path):
    package = load_json(package_path)
    for source in package["provenance"]:
        record_path = SOURCES_DIR / f"{source['source_id']}.json"
        assert record_path.exists(), f"missing source record for {source['source_id']}"
        assert load_json(record_path) == source


def test_every_source_record_is_used_by_at_least_one_package():
    used_ids = {
        source["source_id"]
        for package_path in PACKAGE_PATHS
        for source in load_json(package_path)["provenance"]
    }
    assert {path.stem for path in SOURCES_DIR.glob("*.json")} == used_ids


@pytest.mark.parametrize("package_path", PACKAGE_PATHS, ids=lambda path: path.stem)
def test_official_package_source_digests_match_reference_sections(package_path):
    package = load_json(package_path)
    sections = reference_sections()
    for source in package["provenance"]:
        assert source["source_id"] in sections, f"missing reference section for {source['source_id']}"
        assert source["source_digest"] == canonical_source_digest(sections[source["source_id"]])


def test_reference_sections_cover_all_source_digests_in_registry():
    registry = load_json(ROOT / "policy-data" / "source-digests.json")
    sections = reference_sections()
    assert set(registry) == set(sections)
    for source_id, expected in registry.items():
        assert expected == canonical_source_digest(sections[source_id])


@pytest.mark.parametrize("package_path", PACKAGE_PATHS, ids=lambda path: path.stem)
def test_official_package_rules_are_source_supported_and_vector_tested(package_path):
    package = load_json(package_path)
    source_ids = {source["source_id"] for source in package["provenance"]}
    for rule in package["rules"]:
        assert rule["source_refs"], f"rule {rule['rule_id']} has no source refs"
        assert set(rule["source_refs"]) <= source_ids
        assert rule["test_vectors"], f"rule {rule['rule_id']} has no test vectors"
        input_ids = {input_decl["input_id"] for input_decl in rule["inputs"]}
        output_fields = {result["output_field"] for result in rule["results"]}
        for vector in rule["test_vectors"]:
            assert set(vector["input"]) == input_ids
            assert set(vector["expected"]) == output_fields
