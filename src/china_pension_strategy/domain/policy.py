"""Immutable executable policy sources, packages, and rules."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from itertools import product
from math import prod
import re
from typing import Any, Iterable, Iterator, Mapping, TypeVar

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.values import YearMonth


class AnalysisMode(str, Enum):
    LOCAL_MVP = "LOCAL_MVP"
    PRODUCTION = "PRODUCTION"


class ReviewStatus(str, Enum):
    MVP_REVIEWED = "MVP_REVIEWED"
    PRODUCTION_APPROVED = "PRODUCTION_APPROVED"


class RuleType(str, Enum):
    POLICY_RULE = "POLICY_RULE"
    DECISION_TABLE = "DECISION_TABLE"
    PARAMETER_TABLE = "PARAMETER_TABLE"


class ConditionOperator(str, Enum):
    EQUAL = "="
    NOT_EQUAL = "!="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="


class JurisdictionRole(str, Enum):
    NATIONAL_BASELINE = "NATIONAL_BASELINE"
    LOCAL_IMPLEMENTATION = "LOCAL_IMPLEMENTATION"
    LOCAL_EXCEPTION = "LOCAL_EXCEPTION"


class LegalHierarchy(str, Enum):
    NATIONAL_LAW = "NATIONAL_LAW"
    NATIONAL_REGULATION = "NATIONAL_REGULATION"
    MINISTRY_RULE = "MINISTRY_RULE"
    MUNICIPAL_REGULATION = "MUNICIPAL_REGULATION"
    MUNICIPAL_IMPLEMENTING_RULE = "MUNICIPAL_IMPLEMENTING_RULE"


T = TypeVar("T")
FrozenValue = object
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_GOV_URL = re.compile(r"^https://(?:[A-Za-z0-9-]+\.)*gov\.cn(?::[0-9]+)?(?:/|$)")
_AUTHORITY_LEVELS = {
    "NATIONAL_GOVERNMENT",
    "NATIONAL_MINISTRY",
    "PROVINCIAL_HRSS",
    "BEIJING_MUNICIPAL_GOVERNMENT",
    "BEIJING_HRSS",
    "MUNICIPAL_GOVERNMENT",
    "MUNICIPAL_HRSS",
}

VALUE_TYPES = frozenset(
    {"STRING", "INTEGER", "DECIMAL", "BOOLEAN", "DATE", "YEAR_MONTH", "NULL"}
)
_NUMERIC_TYPES = frozenset({"INTEGER", "DECIMAL"})
_ORDERED_TYPES = frozenset({"INTEGER", "DECIMAL", "DATE", "YEAR_MONTH", "STRING"})
_ORDERING_OPERATORS = frozenset({"<", "<=", ">", ">="})
_EQUALS_OPERATORS = frozenset({"=", "!="})
_EXPRESSION_OPERATORS = frozenset(
    {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "FLOOR_DIVIDE", "POWER", "MIN", "MAX"}
)
_EXCEPTION_EFFECTS = frozenset({"EXCLUDE", "OVERRIDE"})

MAX_DECISION_TABLE_COMBINATIONS = 100_000
"""Maximum Cartesian domain size a decision table may declare before validation."""


class _FrozenMapping(Mapping[str, FrozenValue]):
    def __init__(self, values: Mapping[str, object]) -> None:
        self._items = tuple((key, _freeze(value)) for key, value in values.items())

    def __getitem__(self, key: str) -> FrozenValue:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DomainValidationError(f"{field_name} must be a non-empty string")


def _require_date(value: object, field_name: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise DomainValidationError(f"{field_name} must be a date")


def _require_datetime(value: object, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise DomainValidationError(f"{field_name} must be a timezone-aware datetime")


def _require_digest(value: object, field_name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DomainValidationError(f"{field_name} must be a sha256 digest")


def _as_tuple(values: Iterable[T], field_name: str) -> tuple[T, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise DomainValidationError(f"{field_name} must be a collection")
    try:
        return tuple(values)
    except TypeError as error:
        raise DomainValidationError(f"{field_name} must be a collection") from error


def _freeze(value: Any) -> FrozenValue:
    if isinstance(value, Mapping):
        return _FrozenMapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def _freeze_records(
    values: Iterable[Mapping[str, object]], field_name: str
) -> tuple[Mapping[str, object], ...]:
    records = _as_tuple(values, field_name)
    if not all(isinstance(record, Mapping) for record in records):
        raise DomainValidationError(f"{field_name} must contain mappings")
    return tuple(_freeze(record) for record in records)  # type: ignore[return-value]


def _require_unique_text(values: tuple[str, ...], field_name: str) -> None:
    for value in values:
        _require_text(value, field_name)
    if len(values) != len(set(values)):
        raise DomainValidationError(f"{field_name} cannot contain duplicates")


def _record_ids(
    records: tuple[Mapping[str, object], ...], key: str, field_name: str
) -> set[str]:
    values = tuple(record.get(key) for record in records)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise DomainValidationError(f"{field_name} must declare non-empty {key} values")
    identifiers = tuple(values)  # type: ignore[assignment]
    if len(identifiers) != len(set(identifiers)):
        raise DomainValidationError(f"{field_name} {key} values must be unique")
    return set(identifiers)


def _validate_typed_scalar(value_type: object, value: object, field_name: str) -> None:
    if value_type == "STRING":
        matches = isinstance(value, str)
    elif value_type == "INTEGER":
        matches = isinstance(value, int) and not isinstance(value, bool)
    elif value_type == "DECIMAL":
        matches = isinstance(value, Decimal) and not isinstance(value, bool)
    elif value_type == "BOOLEAN":
        matches = isinstance(value, bool)
    elif value_type == "DATE":
        matches = isinstance(value, date) and not isinstance(value, datetime)
    elif value_type == "YEAR_MONTH":
        matches = isinstance(value, YearMonth)
    elif value_type == "NULL":
        matches = value is None
    else:
        raise DomainValidationError(f"{field_name} value_type is not supported")
    if not matches:
        raise DomainValidationError(
            f"{field_name} value does not match its declared value_type"
        )


def _validate_operator_for_type(
    operator: object, value_type: object, field_name: str
) -> None:
    if operator in _EQUALS_OPERATORS:
        return
    if operator in _ORDERING_OPERATORS:
        if value_type in _ORDERED_TYPES:
            return
        raise DomainValidationError(
            f"{field_name} ordering operators are not valid for this value_type"
        )
    raise DomainValidationError(f"{field_name} operator is not supported")


def _validate_condition(
    condition: Mapping[str, object], input_types: Mapping[str, object]
) -> None:
    operator = condition.get("operator")
    input_ref = condition.get("input_ref")
    value_type = condition.get("value_type")
    if input_ref not in input_types:
        raise DomainValidationError("condition input_ref must resolve")
    if value_type != input_types[input_ref]:
        raise DomainValidationError(
            "condition value_type must match the referenced input"
        )
    _validate_typed_scalar(value_type, condition.get("value"), "condition")
    _validate_operator_for_type(operator, value_type, "condition")


def _validate_expression(
    expression: object,
    input_types: Mapping[str, object],
    parameter_types: Mapping[str, object],
    expected_type: object,
    field_name: str,
) -> None:
    if not isinstance(expression, Mapping):
        raise DomainValidationError(f"{field_name} value must be an expression mapping")
    kind = expression.get("kind")
    value_type = expression.get("value_type")
    if value_type != expected_type:
        raise DomainValidationError(
            f"{field_name} expression type must match its declared type"
        )
    if kind == "LITERAL":
        _validate_typed_scalar(value_type, expression.get("value"), f"{field_name} literal")
    elif kind == "REFERENCE":
        reference_type = expression.get("reference_type")
        reference_id = expression.get("reference_id")
        if reference_type == "INPUT":
            declared = input_types.get(reference_id)
            if declared is None:
                raise DomainValidationError(
                    f"{field_name} expression INPUT reference must resolve"
                )
        elif reference_type == "PARAMETER":
            declared = parameter_types.get(reference_id)
            if declared is None:
                raise DomainValidationError(
                    f"{field_name} expression PARAMETER reference must resolve"
                )
        else:
            raise DomainValidationError(
                f"{field_name} expression reference_type is not supported"
            )
        if declared != value_type:
            raise DomainValidationError(
                f"{field_name} expression reference type must match its target"
            )
    elif kind == "EXPRESSION":
        operator = expression.get("operator")
        operands = expression.get("operands")
        if operator not in _EXPRESSION_OPERATORS:
            raise DomainValidationError(f"{field_name} expression operator is not supported")
        if not isinstance(operands, tuple):
            raise DomainValidationError(f"{field_name} expression operands must be a collection")
        if len(operands) < 2:
            raise DomainValidationError(
                f"{field_name} expression requires at least two operands"
            )
        if operator in {"SUBTRACT", "DIVIDE", "FLOOR_DIVIDE", "POWER"} and len(operands) != 2:
            raise DomainValidationError(
                f"{field_name} expression {operator} requires exactly two operands"
            )
        if operator == "FLOOR_DIVIDE" and value_type != "INTEGER":
            raise DomainValidationError(
                f"{field_name} expression FLOOR_DIVIDE requires INTEGER result"
            )
        if operator == "POWER" and value_type != "DECIMAL":
            raise DomainValidationError(
                f"{field_name} expression POWER requires DECIMAL result"
            )
        if operator in {"ADD", "SUBTRACT", "MULTIPLY"} and value_type not in _NUMERIC_TYPES:
            raise DomainValidationError(
                f"{field_name} expression {operator} requires a numeric value_type"
            )
        if operator == "DIVIDE" and value_type != "DECIMAL":
            raise DomainValidationError(
                f"{field_name} expression DIVIDE requires DECIMAL"
            )
        if operator in {"MIN", "MAX"} and value_type not in _ORDERED_TYPES:
            raise DomainValidationError(
                f"{field_name} expression {operator} requires an orderable value_type"
            )
        for operand in operands:
            _validate_expression(operand, input_types, parameter_types, value_type, field_name)
    else:
        raise DomainValidationError(f"{field_name} expression kind is invalid")


def _canonical_scalar(value: object) -> tuple[str, str]:
    return type(value).__name__, repr(value)


def _condition_matches(condition: Mapping[str, object], values: Mapping[str, object]) -> bool:
    actual = values[condition["input_ref"]]  # type: ignore[index]
    expected = condition.get("value")
    operator = condition.get("operator")
    try:
        if operator == "=":
            return actual == expected
        if operator == "!=":
            return actual != expected
        if operator == "<":
            return actual < expected  # type: ignore[operator]
        if operator == "<=":
            return actual <= expected  # type: ignore[operator]
        if operator == ">":
            return actual > expected  # type: ignore[operator]
        if operator == ">=":
            return actual >= expected  # type: ignore[operator]
        raise KeyError(operator)
    except (KeyError, TypeError) as error:
        raise DomainValidationError("decision row condition is not executable") from error


def _validate_override_ref(ref: str, own_rule_id: str) -> None:
    if ":" in ref:
        parts = ref.split(":")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise DomainValidationError(
                "qualified override refs must have the form package_id:rule_id"
            )
    elif ref == own_rule_id:
        raise DomainValidationError("a rule cannot override itself")


def _validate_interval(
    start: date | datetime,
    end: date | datetime | None,
    start_name: str,
    end_name: str,
) -> None:
    if end is not None and end <= start:
        raise DomainValidationError(f"{end_name} must be later than {start_name}")


def _in_half_open_interval(
    value: date | datetime,
    start: date | datetime,
    end: date | datetime | None,
) -> bool:
    return start <= value and (end is None or value < end)


@dataclass(frozen=True)
class EngineeringReview:
    reviewer_id: str
    reviewed_at: datetime
    schema_validation_passed: bool
    rule_tests_passed: bool

    def __post_init__(self) -> None:
        _require_text(self.reviewer_id, "reviewer_id")
        _require_datetime(self.reviewed_at, "reviewed_at")
        if not isinstance(self.schema_validation_passed, bool) or not isinstance(
            self.rule_tests_passed, bool
        ):
            raise DomainValidationError("review gates must be boolean values")


@dataclass(frozen=True)
class ProductionApproval:
    domain_reviewer_id: str
    approver_ids: tuple[str, ...]
    approved_at: datetime
    signature: str
    published_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.domain_reviewer_id, "domain_reviewer_id")
        approvers = _as_tuple(self.approver_ids, "approver_ids")
        _require_unique_text(approvers, "approver_ids")
        if len(approvers) < 2:
            raise DomainValidationError("production approval requires at least two approvers")
        if self.domain_reviewer_id in approvers:
            raise DomainValidationError(
                "domain reviewer and approvers must be distinct"
            )
        object.__setattr__(self, "approver_ids", approvers)
        _require_datetime(self.approved_at, "approved_at")
        _require_datetime(self.published_at, "published_at")
        if self.published_at < self.approved_at:
            raise DomainValidationError("published_at cannot precede approved_at")
        if not isinstance(self.signature, str) or not self.signature.startswith("sig:") or len(self.signature) == 4:
            raise DomainValidationError("signature must be a non-empty sig: value")


@dataclass(frozen=True)
class PolicySource:
    source_id: str
    url: str
    issuing_authority: str
    authority_level: str
    document_number: str | None
    publication_date: date
    retrieved_at: datetime
    locator: str
    source_digest: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "url",
            "issuing_authority",
            "authority_level",
            "locator",
            "source_digest",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.document_number is not None:
            _require_text(self.document_number, "document_number")
        if _GOV_URL.match(self.url) is None:
            raise DomainValidationError("url must be an official HTTPS gov.cn URL")
        if self.authority_level not in _AUTHORITY_LEVELS:
            raise DomainValidationError("authority_level is not an accepted authority")
        _require_digest(self.source_digest, "source_digest")
        _require_date(self.publication_date, "publication_date")
        _require_datetime(self.retrieved_at, "retrieved_at")


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    rule_type: RuleType
    scheme: str
    topic: str
    jurisdiction_role: JurisdictionRole
    population_scope: str
    inputs: tuple[Mapping[str, object], ...]
    conditions: tuple[Mapping[str, object], ...]
    results: tuple[Mapping[str, object], ...]
    exceptions: tuple[Mapping[str, object], ...]
    effective_from: date
    effective_to: date | None
    transaction_from: datetime
    transaction_to: datetime | None
    legal_hierarchy: LegalHierarchy
    explicit_override_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    parameters: Mapping[str, object]
    test_vectors: tuple[Mapping[str, object], ...]
    input_domains: Mapping[str, tuple[object, ...]] | None = None
    decision_rows: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("rule_id", "scheme", "topic", "population_scope"):
            _require_text(getattr(self, field_name), field_name)
        if ":" in self.rule_id:
            raise DomainValidationError("rule_id must not contain ':'")
        if not isinstance(self.rule_type, RuleType):
            raise DomainValidationError("rule_type must be a RuleType")
        if not isinstance(self.jurisdiction_role, JurisdictionRole):
            raise DomainValidationError(
                "jurisdiction_role must be a JurisdictionRole"
            )
        if not isinstance(self.legal_hierarchy, LegalHierarchy):
            raise DomainValidationError("legal_hierarchy must be a LegalHierarchy")

        for field_name in ("inputs", "conditions", "results", "exceptions", "test_vectors"):
            object.__setattr__(
                self,
                field_name,
                _freeze_records(getattr(self, field_name), field_name),
            )
        for field_name in ("inputs", "conditions", "results", "test_vectors"):
            if not getattr(self, field_name):
                raise DomainValidationError(f"{field_name} cannot be empty")

        for field_name in ("explicit_override_refs", "source_refs"):
            values = _as_tuple(getattr(self, field_name), field_name)
            _require_unique_text(values, field_name)
            object.__setattr__(self, field_name, values)
        if not self.source_refs:
            raise DomainValidationError("source_refs cannot be empty")
        for ref in self.explicit_override_refs:
            _validate_override_ref(ref, self.rule_id)
        if not isinstance(self.parameters, Mapping):
            raise DomainValidationError("parameters must be a mapping")
        parameter_types: dict[str, object] = {}
        for name, declaration in self.parameters.items():
            if (
                not isinstance(declaration, Mapping)
                or set(declaration) != {"value_type", "value"}
            ):
                raise DomainValidationError(
                    f"parameter {name} must be a typed declaration"
                )
            parameter_value_type = declaration.get("value_type")
            _validate_typed_scalar(
                parameter_value_type,
                declaration.get("value"),
                f"parameter {name}",
            )
            parameter_types[name] = parameter_value_type
        object.__setattr__(self, "parameters", _freeze(self.parameters))

        input_ids = _record_ids(self.inputs, "input_id", "inputs")
        input_types: dict[str, object] = {}
        for input_declaration in self.inputs:
            input_value_type = input_declaration.get("value_type")
            if input_value_type not in VALUE_TYPES:
                raise DomainValidationError(
                    f"input {input_declaration.get('input_id')} value_type is not supported"
                )
            if not isinstance(input_declaration.get("required"), bool):
                raise DomainValidationError(
                    f"input {input_declaration.get('input_id')} required must be boolean"
                )
            input_types[input_declaration.get("input_id")] = input_value_type  # type: ignore[index]
        condition_ids = _record_ids(self.conditions, "condition_id", "conditions")
        result_ids = _record_ids(self.results, "result_id", "results")
        output_fields = {
            result.get("output_field")
            for result in self.results
            if isinstance(result.get("output_field"), str)
        }
        if len(output_fields) != len(self.results):
            raise DomainValidationError("results must declare unique output_field values")

        for condition in self.conditions:
            _validate_condition(condition, input_types)
        for exception in self.exceptions:
            if exception.get("effect") not in _EXCEPTION_EFFECTS:
                raise DomainValidationError("exception effect is not supported")
            condition_refs = set(exception.get("condition_refs", ()))
            result_refs = set(exception.get("result_refs", ()))
            if not condition_refs <= condition_ids:
                raise DomainValidationError("exception condition_refs must resolve")
            if not result_refs <= result_ids:
                raise DomainValidationError("exception result_refs must resolve")
        result_types: dict[str, object] = {}
        for result in self.results:
            result_type = result.get("value_type")
            if result_type not in VALUE_TYPES:
                raise DomainValidationError(
                    f"result {result.get('result_id')} value_type is not supported"
                )
            result_types[result.get("output_field")] = result_type  # type: ignore[index]
            _validate_expression(
                result.get("value"), input_types, parameter_types, result_type, "result"
            )
        for vector in self.test_vectors:
            vector_input = vector.get("input")
            vector_expected = vector.get("expected")
            if not isinstance(vector_input, Mapping) or set(vector_input) != input_ids:
                raise DomainValidationError(
                    "test vector input keys must match declared inputs"
                )
            if not isinstance(vector_expected, Mapping) or set(vector_expected) != output_fields:
                raise DomainValidationError(
                    "test vector expected keys must match declared results"
                )
            for input_id, value in vector_input.items():
                _validate_typed_scalar(
                    input_types[input_id], value, "test vector input"
                )
            for output_field, value in vector_expected.items():
                _validate_typed_scalar(
                    result_types[output_field], value, "test vector expected"
                )

        if self.rule_type is RuleType.DECISION_TABLE:
            self._validate_decision_table(input_ids, input_types, result_ids, parameter_types)
        elif self.input_domains is not None or self.decision_rows:
            raise DomainValidationError(
                "input_domains and decision_rows are only valid for DECISION_TABLE"
            )

        _require_date(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _require_date(self.effective_to, "effective_to")
        _require_datetime(self.transaction_from, "transaction_from")
        if self.transaction_to is not None:
            _require_datetime(self.transaction_to, "transaction_to")
        _validate_interval(
            self.effective_from, self.effective_to, "effective_from", "effective_to"
        )
        _validate_interval(
            self.transaction_from,
            self.transaction_to,
            "transaction_from",
            "transaction_to",
        )

    def applies_at(self, effective_on: date, known_at: datetime) -> bool:
        _require_date(effective_on, "effective_on")
        _require_datetime(known_at, "known_at")
        return _in_half_open_interval(
            effective_on, self.effective_from, self.effective_to
        ) and _in_half_open_interval(
            known_at, self.transaction_from, self.transaction_to
        )

    def _validate_decision_table(
        self,
        input_ids: set[str],
        input_types: Mapping[str, object],
        result_ids: set[str],
        parameter_types: Mapping[str, object],
    ) -> None:
        if not isinstance(self.input_domains, Mapping) or set(self.input_domains) != input_ids:
            raise DomainValidationError(
                "DECISION_TABLE input_domains must match declared inputs"
            )
        domains: dict[str, tuple[object, ...]] = {}
        for input_id, raw_values in self.input_domains.items():
            values = _as_tuple(raw_values, f"input domain {input_id}")
            if not values:
                raise DomainValidationError("decision input domains cannot be empty")
            if any(isinstance(value, (Mapping, tuple, list, set)) for value in values):
                raise DomainValidationError("decision input domains must contain scalars")
            if len({_canonical_scalar(value) for value in values}) != len(values):
                raise DomainValidationError("decision input domains must be unique")
            for value in values:
                _validate_typed_scalar(
                    input_types[input_id], value, f"input domain {input_id}"
                )
            domains[input_id] = values
        combination_count = prod(len(values) for values in domains.values())
        if combination_count > MAX_DECISION_TABLE_COMBINATIONS:
            raise DomainValidationError(
                "decision table domain size "
                f"{combination_count} exceeds the maximum "
                f"{MAX_DECISION_TABLE_COMBINATIONS}"
            )
        object.__setattr__(self, "input_domains", _freeze(domains))

        rows = _as_tuple(self.decision_rows, "decision_rows")
        if not rows or not all(isinstance(row, Mapping) for row in rows):
            raise DomainValidationError("DECISION_TABLE decision_rows cannot be empty")
        frozen_rows = _freeze_records(rows, "decision_rows")
        _record_ids(frozen_rows, "row_id", "decision_rows")
        normalized_rows: list[Mapping[str, object]] = []
        for row in frozen_rows:
            conditions = row.get("conditions")
            results = row.get("results")
            if not isinstance(conditions, tuple) or not all(
                isinstance(condition, Mapping) for condition in conditions
            ):
                raise DomainValidationError("decision row conditions must be a collection")
            if not isinstance(results, tuple) or not results or not all(
                isinstance(result, Mapping) for result in results
            ):
                raise DomainValidationError("decision row results cannot be empty")
            _record_ids(conditions, "condition_id", "decision row conditions")
            row_result_ids = _record_ids(results, "result_id", "decision row results")
            if row_result_ids != result_ids:
                raise DomainValidationError(
                    "decision row results must match declared results"
                )
            for condition in conditions:
                _validate_condition(condition, input_types)
            for result in results:
                _validate_expression(
                    result.get("value"),
                    input_types,
                    parameter_types,
                    result.get("value_type"),
                    "decision row result",
                )
            normalized_rows.append(row)
        object.__setattr__(self, "decision_rows", tuple(normalized_rows))

        ordered_inputs = tuple(record["input_id"] for record in self.inputs)
        for combination in product(*(domains[input_id] for input_id in ordered_inputs)):
            values = dict(zip(ordered_inputs, combination))
            matches = [
                row
                for row in normalized_rows
                if all(
                    _condition_matches(condition, values)
                    for condition in row["conditions"]  # type: ignore[union-attr]
                )
            ]
            if not matches:
                raise DomainValidationError(
                    f"decision table gap for input combination {combination!r}"
                )
            if len(matches) > 1:
                raise DomainValidationError(
                    f"decision table overlap for input combination {combination!r}"
                )


@dataclass(frozen=True)
class PolicyPackage:
    schema_version: str
    package_id: str
    version: str
    scheme: str
    jurisdiction: str
    topic: str
    review_status: ReviewStatus
    execution_modes: tuple[AnalysisMode, ...]
    local_only: bool
    engine_compatibility: str
    effective_from: date
    effective_to: date | None
    transaction_from: datetime
    transaction_to: datetime | None
    content_digest: str
    provenance: tuple[PolicySource, ...]
    rules: tuple[PolicyRule, ...]
    engineering_review: EngineeringReview
    production_approval: ProductionApproval | None
    historical: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "schema_version",
            "package_id",
            "version",
            "scheme",
            "jurisdiction",
            "topic",
            "engine_compatibility",
            "content_digest",
        ):
            _require_text(getattr(self, field_name), field_name)
        if ":" in self.package_id:
            raise DomainValidationError("package_id must not contain ':'")
        if not isinstance(self.review_status, ReviewStatus):
            raise DomainValidationError("review_status must be a ReviewStatus")
        if not isinstance(self.historical, bool):
            raise DomainValidationError("historical must be a boolean")
        _require_digest(self.content_digest, "content_digest")
        modes = _as_tuple(self.execution_modes, "execution_modes")
        if not modes or not all(isinstance(mode, AnalysisMode) for mode in modes):
            raise DomainValidationError("execution_modes must contain AnalysisMode values")
        if len(modes) != len(set(modes)):
            raise DomainValidationError("execution_modes cannot contain duplicates")
        object.__setattr__(self, "execution_modes", modes)

        provenance = _as_tuple(self.provenance, "provenance")
        rules = _as_tuple(self.rules, "rules")
        if not provenance or not all(isinstance(item, PolicySource) for item in provenance):
            raise DomainValidationError("provenance must contain PolicySource values")
        if not rules or not all(isinstance(item, PolicyRule) for item in rules):
            raise DomainValidationError("rules must contain PolicyRule values")
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "rules", rules)
        if len({source.source_id for source in provenance}) != len(provenance):
            raise DomainValidationError("provenance source IDs must be unique")
        if len({rule.rule_id for rule in rules}) != len(rules):
            raise DomainValidationError("rule IDs must be unique within a package")

        source_ids = {source.source_id for source in provenance}
        rule_ids = {rule.rule_id for rule in rules}
        for rule in rules:
            if rule.scheme != self.scheme or rule.topic != self.topic:
                raise DomainValidationError("rule scheme and topic must match its package")
            if not set(rule.source_refs) <= source_ids:
                raise DomainValidationError("rule source_refs must resolve within provenance")
            for reference in rule.explicit_override_refs:
                if ":" in reference:
                    package_id, rule_id = reference.split(":")
                    if package_id != self.package_id:
                        continue
                    if rule_id == rule.rule_id:
                        raise DomainValidationError("a rule cannot override itself")
                    if rule_id not in rule_ids:
                        raise DomainValidationError(
                            "rule explicit override refs must resolve within the package"
                        )
                elif reference not in rule_ids:
                    raise DomainValidationError(
                        "rule explicit override refs must resolve within the package"
                    )

        if not isinstance(self.engineering_review, EngineeringReview):
            raise DomainValidationError(
                "engineering_review must be an EngineeringReview"
            )
        if self.production_approval is not None and not isinstance(
            self.production_approval, ProductionApproval
        ):
            raise DomainValidationError(
                "production_approval must be a ProductionApproval or None"
            )

        _require_date(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _require_date(self.effective_to, "effective_to")
        _require_datetime(self.transaction_from, "transaction_from")
        if self.transaction_to is not None:
            _require_datetime(self.transaction_to, "transaction_to")
        _validate_interval(
            self.effective_from, self.effective_to, "effective_from", "effective_to"
        )
        _validate_interval(
            self.transaction_from,
            self.transaction_to,
            "transaction_from",
            "transaction_to",
        )

        if self.transaction_from < max(
            source.retrieved_at for source in self.provenance
        ):
            raise DomainValidationError(
                "transaction_from cannot precede provenance source retrieval"
            )
        if self.transaction_from < self.engineering_review.reviewed_at:
            raise DomainValidationError(
                "transaction_from cannot precede engineering review"
            )
        if self.production_approval is not None and (
            self.transaction_from < self.production_approval.published_at
        ):
            raise DomainValidationError(
                "transaction_from cannot precede production publication"
            )

        review_passed = (
            self.engineering_review.schema_validation_passed
            and self.engineering_review.rule_tests_passed
        )
        if not review_passed:
            raise DomainValidationError("engineering review gates must pass")
        if self.review_status is ReviewStatus.MVP_REVIEWED:
            if modes != (AnalysisMode.LOCAL_MVP,) or not self.local_only:
                raise DomainValidationError(
                    "MVP_REVIEWED packages must be local-only LOCAL_MVP packages"
                )
            if self.production_approval is not None:
                raise DomainValidationError(
                    "MVP_REVIEWED packages cannot have production approval"
                )
        elif self.local_only or AnalysisMode.PRODUCTION not in modes:
            raise DomainValidationError(
                "PRODUCTION_APPROVED packages must permit production and not be local-only"
            )
        elif self.production_approval is None:
            raise DomainValidationError(
                "PRODUCTION_APPROVED packages require production approval"
            )

    def applies_at(self, effective_on: date, known_at: datetime) -> bool:
        _require_date(effective_on, "effective_on")
        _require_datetime(known_at, "known_at")
        return _in_half_open_interval(
            effective_on, self.effective_from, self.effective_to
        ) and _in_half_open_interval(
            known_at, self.transaction_from, self.transaction_to
        )
