"""Deterministic bitemporal policy resolution."""

from dataclasses import dataclass
from datetime import date, datetime, date as date_type, datetime as datetime_type
from decimal import Decimal
from enum import Enum
import re
from typing import Iterable, Mapping

from china_pension_strategy.domain.policy import (
    AnalysisMode,
    JurisdictionRole,
    LegalHierarchy,
    PolicyPackage,
    PolicyRule,
    ReviewStatus,
)
from china_pension_strategy.ports.outbound.policy_repository import PolicyRepository


class PolicyResolutionError(Exception):
    """Base class for safe policy resolution failures."""


class PolicyVersionNotFoundError(PolicyResolutionError):
    code = "POLICY_VERSION_NOT_FOUND"


class RulesetIncompatibleError(PolicyResolutionError):
    code = "RULESET_INCOMPATIBLE"


class ConflictDimension(str, Enum):
    SCHEME = "SCHEME"
    JURISDICTION_ROLE = "JURISDICTION_ROLE"
    EFFECTIVE_TIME = "EFFECTIVE_TIME"
    KNOWN_AT_TIME = "KNOWN_AT_TIME"
    LEGAL_HIERARCHY = "LEGAL_HIERARCHY"
    RULE_OVERRIDE = "RULE_OVERRIDE"
    COMPATIBILITY = "COMPATIBILITY"
    PUBLICATION_STATUS = "PUBLICATION_STATUS"


class AmbiguousPolicyRuleError(PolicyResolutionError):
    code = "AMBIGUOUS_POLICY_RULE"

    def __init__(
        self,
        competing_rule_ids: Iterable[str],
        conflict_dimensions: Iterable[ConflictDimension],
    ) -> None:
        self.competing_rule_ids = tuple(sorted(competing_rule_ids))
        self.conflict_dimensions = tuple(conflict_dimensions)
        if not self.conflict_dimensions or len(self.conflict_dimensions) != len(
            set(self.conflict_dimensions)
        ):
            raise ValueError("conflict_dimensions must be a non-empty unique set")
        if not all(
            isinstance(dimension, ConflictDimension)
            for dimension in self.conflict_dimensions
        ):
            raise TypeError("conflict_dimensions must contain ConflictDimension values")
        super().__init__(
            "incompatible policy rules survive resolution: "
            + ", ".join(self.competing_rule_ids)
        )


@dataclass(frozen=True)
class PolicyQuery:
    scheme: str
    topic: str
    jurisdiction: str
    jurisdiction_role: JurisdictionRole
    population_scope: str
    as_of_effective_date: date
    as_known_at: datetime
    engine_version: str
    analysis_mode: AnalysisMode


@dataclass(frozen=True)
class ResolvedPolicy:
    packages: tuple[PolicyPackage, ...]
    rules: tuple[PolicyRule, ...]


_HIERARCHY_RANK = {
    LegalHierarchy.NATIONAL_LAW: 5,
    LegalHierarchy.NATIONAL_REGULATION: 4,
    LegalHierarchy.MINISTRY_RULE: 3,
    LegalHierarchy.MUNICIPAL_REGULATION: 2,
    LegalHierarchy.MUNICIPAL_IMPLEMENTING_RULE: 1,
}
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_CONSTRAINT = re.compile(
    r"^(>=|<=|==|>|<)((?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){0,2})$"
)


def _version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise RulesetIncompatibleError(f"invalid engine version: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _is_compatible(engine_version: str, compatibility: str) -> bool:
    current = _version(engine_version)
    constraints = compatibility.split(",")
    if not constraints:
        return False
    for raw_constraint in constraints:
        match = _CONSTRAINT.fullmatch(raw_constraint.strip())
        if match is None:
            raise RulesetIncompatibleError(
                f"invalid engine compatibility range: {compatibility}"
            )
        operator, version_text = match.groups()
        expected_parts = tuple(int(part) for part in version_text.split("."))
        expected = expected_parts + (0,) * (3 - len(expected_parts))
        accepted = {
            ">=": current >= expected,
            "<=": current <= expected,
            "==": current == expected,
            ">": current > expected,
            "<": current < expected,
        }[operator]
        if not accepted:
            return False
    return True


def _qualified_rule_id(package: PolicyPackage, rule: PolicyRule) -> str:
    return f"{package.package_id}:{rule.rule_id}"


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        return tuple(sorted((key, _canonical(item)) for key, item in value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(_canonical(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(_canonical(item) for item in value))
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, Decimal):
        try:
            normalized = value.normalize()
        except ArithmeticError:
            normalized = value
        return ("decimal", str(normalized))
    if isinstance(value, str):
        return ("str", value)
    if value is None:
        return ("none", None)
    if isinstance(value, datetime_type):
        return ("datetime", value.isoformat())
    if isinstance(value, date_type):
        return ("date", value.isoformat())
    return (type(value).__name__, repr(value))


def _canonical_unordered(values: Iterable[object]) -> tuple[object, ...]:
    return tuple(sorted((_canonical(value) for value in values), key=repr))


def _canonical_without_ids(
    record: Mapping[str, object], excluded_ids: set[str]
) -> object:
    return tuple(
        sorted(
            (key, _canonical(value))
            for key, value in record.items()
            if key not in excluded_ids
        )
    )


def _condition_semantics(condition: Mapping[str, object]) -> object:
    return _canonical_without_ids(condition, {"condition_id"})


def _result_semantics(result: Mapping[str, object]) -> object:
    return _canonical_without_ids(result, {"result_id"})


def _exception_semantics(rule: PolicyRule) -> tuple[object, ...]:
    conditions_by_id = {
        condition["condition_id"]: _condition_semantics(condition)
        for condition in rule.conditions
    }
    results_by_id = {
        result["result_id"]: _result_semantics(result) for result in rule.results
    }
    exceptions = []
    for exception in rule.exceptions:
        exceptions.append(
            (
                ("effect", exception["effect"]),
                (
                    "conditions",
                    _canonical_unordered(
                        conditions_by_id[reference]
                        for reference in exception["condition_refs"]
                    ),
                ),
                (
                    "results",
                    _canonical_unordered(
                        results_by_id[reference]
                        for reference in exception["result_refs"]
                    ),
                ),
            )
        )
    return tuple(sorted(exceptions, key=repr))


def _canonical_input_domains(rule: PolicyRule) -> object:
    if rule.input_domains is None:
        return None
    return tuple(
        sorted(
            (
                input_id,
                _canonical_unordered(values),
            )
            for input_id, values in rule.input_domains.items()
        )
    )


def _canonical_decision_rows(rule: PolicyRule) -> tuple[object, ...]:
    rows = []
    for row in rule.decision_rows:
        rows.append(
            (
                (
                    "conditions",
                    _canonical_unordered(
                        _condition_semantics(condition)
                        for condition in row["conditions"]
                    ),
                ),
                (
                    "results",
                    _canonical_unordered(
                        _result_semantics(result) for result in row["results"]
                    ),
                ),
            )
        )
    return tuple(sorted(rows, key=repr))


def _decision_signature(rule: PolicyRule) -> object:
    return (
        rule.rule_type.value,
        _canonical_unordered(rule.inputs),
        _canonical_unordered(
            _condition_semantics(condition) for condition in rule.conditions
        ),
        _canonical_unordered(_result_semantics(result) for result in rule.results),
        _exception_semantics(rule),
        _canonical(rule.parameters),
        _canonical_input_domains(rule),
        _canonical_decision_rows(rule),
    )


def _mode_permits(package: PolicyPackage, mode: AnalysisMode) -> bool:
    if mode not in package.execution_modes:
        return False
    return not (
        package.review_status is ReviewStatus.MVP_REVIEWED
        and mode is not AnalysisMode.LOCAL_MVP
    )


def resolve_policy(
    repository: PolicyRepository, query: PolicyQuery
) -> ResolvedPolicy:
    scoped_packages = tuple(
        package
        for package in repository.list_packages()
        if package.scheme == query.scheme
        and package.topic == query.topic
        and package.jurisdiction == query.jurisdiction
        and package.applies_at(query.as_of_effective_date, query.as_known_at)
    )
    if not scoped_packages:
        raise PolicyVersionNotFoundError("no policy package matches scope and time")

    candidates = tuple(
        (package, rule)
        for package in scoped_packages
        for rule in package.rules
        if rule.scheme == query.scheme
        and rule.topic == query.topic
        and rule.jurisdiction_role is query.jurisdiction_role
        and rule.population_scope == query.population_scope
        and rule.applies_at(query.as_of_effective_date, query.as_known_at)
    )
    if not candidates:
        raise PolicyVersionNotFoundError("no policy rule matches the query")

    overridden_qualified_ids: set[str] = set()
    for package, rule in candidates:
        for reference in rule.explicit_override_refs:
            if ":" in reference:
                overridden_qualified_ids.add(reference)
            else:
                overridden_qualified_ids.add(f"{package.package_id}:{reference}")
    survivors = tuple(
        (package, rule)
        for package, rule in candidates
        if _qualified_rule_id(package, rule) not in overridden_qualified_ids
    )
    if not survivors:
        raise AmbiguousPolicyRuleError(
            (_qualified_rule_id(package, rule) for package, rule in candidates),
            (ConflictDimension.RULE_OVERRIDE,),
        )

    highest_rank = max(
        _HIERARCHY_RANK[rule.legal_hierarchy] for _, rule in survivors
    )
    survivors = tuple(
        (package, rule)
        for package, rule in survivors
        if _HIERARCHY_RANK[rule.legal_hierarchy] == highest_rank
    )

    signatures = {_decision_signature(rule) for _, rule in survivors}
    if len(signatures) > 1:
        raise AmbiguousPolicyRuleError(
            (_qualified_rule_id(package, rule) for package, rule in survivors),
            (
                ConflictDimension.LEGAL_HIERARCHY,
                ConflictDimension.RULE_OVERRIDE,
            ),
        )

    selected = tuple(
        sorted(survivors, key=lambda pair: _qualified_rule_id(*pair))
    )
    selected_rules = tuple(rule for _, rule in selected)
    selected_rule_ids = {id(rule) for rule in selected_rules}
    selected_packages = tuple(
        sorted(
            (
                package
                for package in scoped_packages
                if any(id(rule) in selected_rule_ids for rule in package.rules)
            ),
            key=lambda package: (package.package_id, package.version),
        )
    )
    if not all(
        _is_compatible(query.engine_version, package.engine_compatibility)
        for package in selected_packages
    ):
        raise RulesetIncompatibleError(
            "the applicable precedence winner is incompatible with the engine"
        )
    if not all(
        _mode_permits(package, query.analysis_mode) for package in selected_packages
    ):
        raise PolicyVersionNotFoundError(
            "the applicable precedence winner is not executable in this mode"
        )
    return ResolvedPolicy(packages=selected_packages, rules=selected_rules)
