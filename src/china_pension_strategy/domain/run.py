"""Immutable analysis run identity, state machine, and manifest projection."""

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, cast

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import AnalysisMode, ReviewStatus

SCHEMA_VERSION = "2.0.0"
"""Run manifest JSON Schema version projected by AnalysisRun.to_manifest."""

MANIFEST_VERSION = "2.0.0"
"""Run manifest contract version projected by AnalysisRun.to_manifest."""

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_VALIDATION_KEYS = frozenset(
    {
        "input_schema_valid",
        "policy_schema_valid",
        "output_schema_valid",
        "invariants_valid",
    }
)


class RunStatus(StrEnum):
    """Lifecycle state of an analysis run."""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class PublicationStatus(StrEnum):
    """Publication lifecycle of a stored run."""

    LOCAL_ONLY = "LOCAL_ONLY"
    VALIDATED = "VALIDATED"
    RENDERED = "RENDERED"
    PUBLISHED = "PUBLISHED"


class RunStateTransitionError(DomainValidationError):
    """Raised when a run would leave the RunStatus state machine."""

    code = "RUN_STATE_TRANSITION_INVALID"


class PublicationTransitionError(DomainValidationError):
    """Raised when a run would leave the PublicationStatus state machine."""

    code = "PUBLICATION_TRANSITION_INVALID"


class PublicationProhibitedError(DomainValidationError):
    """Raised when a run whose review statuses contain MVP_REVIEWED is published."""

    code = "MVP_REVIEWED_PUBLICATION_PROHIBITED"


class MissingProductionApprovalError(DomainValidationError):
    """Raised when a run without PRODUCTION_APPROVED review is published."""

    code = "PUBLISHED_REQUIRES_PRODUCTION_APPROVED"


_RUN_TRANSITIONS: Mapping[RunStatus, frozenset[RunStatus]] = {
    RunStatus.RUNNING: frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED}),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
}

_PUBLICATION_TRANSITIONS: Mapping[PublicationStatus, frozenset[PublicationStatus]] = {
    PublicationStatus.LOCAL_ONLY: frozenset(
        {
            PublicationStatus.VALIDATED,
            PublicationStatus.RENDERED,
            PublicationStatus.PUBLISHED,
        }
    ),
    PublicationStatus.VALIDATED: frozenset(
        {PublicationStatus.RENDERED, PublicationStatus.PUBLISHED}
    ),
    PublicationStatus.RENDERED: frozenset({PublicationStatus.PUBLISHED}),
    PublicationStatus.PUBLISHED: frozenset(),
}


class _FrozenDict(Mapping[str, Any]):
    """Immutable mapping over a snapshot of items."""

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._items = tuple(values.items())

    def __getitem__(self, key: str) -> Any:
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


@dataclass(frozen=True)
class ComponentVersions:
    """Version pins for the components a run was produced with."""

    engine: str
    input_schema: str
    output_schema: str
    manifest_schema: str
    rounding_profile: str

    def __post_init__(self) -> None:
        for field_name in ("engine", "input_schema", "output_schema"):
            if _VERSION_RE.fullmatch(getattr(self, field_name)) is None:
                raise DomainValidationError(f"{field_name} must be a semantic version")
        if self.manifest_schema != MANIFEST_VERSION:
            raise DomainValidationError("manifest_schema must match the manifest version")
        _require_text(self.rounding_profile, "rounding_profile")


@dataclass(frozen=True)
class RulesetReference:
    """Immutable reference to one policy ruleset consumed by a run."""

    package_id: str
    ruleset_id: str
    version: str
    digest: str

    def __post_init__(self) -> None:
        _require_text(self.package_id, "package_id")
        _require_text(self.ruleset_id, "ruleset_id")
        if _VERSION_RE.fullmatch(self.version) is None:
            raise DomainValidationError("version must be a semantic version")
        if _DIGEST_RE.fullmatch(self.digest) is None:
            raise DomainValidationError("digest must be a sha256 digest")


@dataclass(frozen=True)
class AnalysisRun:
    """Immutable identity of one analysis run with guarded state transitions."""

    parent_run_id: str | None
    analysis_mode: AnalysisMode
    review_statuses: tuple[ReviewStatus, ...]
    component_versions: ComponentVersions
    policy_rulesets: tuple[RulesetReference, ...]
    input_snapshot_digest: str
    assumption_set_digest: str
    objective_digest: str
    output_digest: str
    artifact_digests: tuple[str, ...]
    adapter_versions: Mapping[str, str]
    validation: Mapping[str, bool]
    validation_suite: str
    warnings_count: int
    unresolved_conflicts_count: int
    duration_ms: int
    created_at: datetime
    status: RunStatus = RunStatus.RUNNING
    publication_status: PublicationStatus = PublicationStatus.LOCAL_ONLY
    run_id: str = field(init=False, default="")

    def __post_init__(self) -> None:
        if self.parent_run_id is not None:
            _require_text(self.parent_run_id, "parent_run_id")
        if not isinstance(self.analysis_mode, AnalysisMode):
            raise DomainValidationError("analysis_mode must be an AnalysisMode")

        statuses = tuple(self.review_statuses)
        if not statuses or not all(isinstance(value, ReviewStatus) for value in statuses):
            raise DomainValidationError("review_statuses must contain ReviewStatus values")
        if len(statuses) != len(set(statuses)):
            raise DomainValidationError("review_statuses cannot contain duplicates")
        object.__setattr__(self, "review_statuses", statuses)

        if not isinstance(self.component_versions, ComponentVersions):
            raise DomainValidationError("component_versions must be a ComponentVersions")
        rulesets = tuple(self.policy_rulesets)
        if not rulesets or not all(isinstance(ruleset, RulesetReference) for ruleset in rulesets):
            raise DomainValidationError("policy_rulesets must contain RulesetReference values")
        object.__setattr__(self, "policy_rulesets", rulesets)

        for field_name in (
            "input_snapshot_digest",
            "assumption_set_digest",
            "objective_digest",
            "output_digest",
        ):
            if _DIGEST_RE.fullmatch(getattr(self, field_name)) is None:
                raise DomainValidationError(f"{field_name} must be a sha256 digest")
        artifacts = tuple(self.artifact_digests)
        if any(_DIGEST_RE.fullmatch(digest) is None for digest in artifacts):
            raise DomainValidationError("artifact_digests must contain sha256 digests")
        object.__setattr__(self, "artifact_digests", artifacts)

        if not isinstance(self.adapter_versions, Mapping):
            raise DomainValidationError("adapter_versions must be a mapping")
        adapters: dict[str, str] = {}
        for name, version in self.adapter_versions.items():
            if _IDENTIFIER_RE.fullmatch(name) is None:
                raise DomainValidationError(f"adapter version key {name!r} is invalid")
            if _VERSION_RE.fullmatch(version) is None:
                raise DomainValidationError(
                    f"adapter version value for {name!r} must be a semantic version"
                )
            adapters[name] = version
        object.__setattr__(self, "adapter_versions", _FrozenDict(adapters))

        if not isinstance(self.validation, Mapping) or set(self.validation) != _VALIDATION_KEYS:
            raise DomainValidationError("validation must declare the four schema gates")
        if not all(isinstance(value, bool) for value in self.validation.values()):
            raise DomainValidationError("validation gates must be boolean values")
        if not all(self.validation.values()):
            raise DomainValidationError("validation gates must all pass")
        object.__setattr__(self, "validation", _FrozenDict(dict(self.validation)))

        _require_text(self.validation_suite, "validation_suite")
        for field_name in (
            "warnings_count",
            "unresolved_conflicts_count",
            "duration_ms",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DomainValidationError(f"{field_name} must be a non-negative integer")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise DomainValidationError("created_at must be a timezone-aware datetime")
        if not isinstance(self.status, RunStatus):
            raise DomainValidationError("status must be a RunStatus")
        if not isinstance(self.publication_status, PublicationStatus):
            raise DomainValidationError("publication_status must be a PublicationStatus")

        if (
            ReviewStatus.MVP_REVIEWED in statuses
            and self.analysis_mode is not AnalysisMode.LOCAL_MVP
        ):
            raise DomainValidationError("MVP_REVIEWED runs must use LOCAL_MVP analysis mode")
        if self.analysis_mode is AnalysisMode.PRODUCTION and any(
            value is not ReviewStatus.PRODUCTION_APPROVED for value in statuses
        ):
            raise DomainValidationError(
                "PRODUCTION runs require PRODUCTION_APPROVED review statuses"
            )
        if self.publication_status is PublicationStatus.PUBLISHED:
            if ReviewStatus.MVP_REVIEWED in statuses:
                raise DomainValidationError("MVP_REVIEWED runs cannot be PUBLISHED")
            if ReviewStatus.PRODUCTION_APPROVED not in statuses:
                raise DomainValidationError(
                    "PUBLISHED runs require PRODUCTION_APPROVED review status"
                )

        object.__setattr__(self, "run_id", self._compute_run_id())

    def _compute_run_id(self) -> str:
        canonical = json.dumps(
            {
                "input": self.input_snapshot_digest,
                "rules": [ruleset.digest for ruleset in self.policy_rulesets],
                "engine": self.component_versions.engine,
                "objective": self.objective_digest,
                "assumptions": self.assumption_set_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "run-" + hashlib.sha256(canonical).hexdigest()

    def mark_succeeded(self) -> None:
        """Transition this run from RUNNING to SUCCEEDED."""
        self._transition_status(RunStatus.SUCCEEDED)

    def mark_failed(self) -> None:
        """Transition this run from RUNNING to FAILED."""
        self._transition_status(RunStatus.FAILED)

    def publish(self) -> None:
        """Publish this run after the review and publication gates pass."""
        if ReviewStatus.MVP_REVIEWED in self.review_statuses:
            raise PublicationProhibitedError("MVP_REVIEWED runs cannot be published")
        if ReviewStatus.PRODUCTION_APPROVED not in self.review_statuses:
            raise MissingProductionApprovalError(
                "PUBLISHED runs require PRODUCTION_APPROVED review status"
            )
        self._transition_publication(PublicationStatus.PUBLISHED)

    def _transition_status(self, target: RunStatus) -> None:
        if target not in _RUN_TRANSITIONS[self.status]:
            raise RunStateTransitionError(
                f"cannot transition run status from {self.status.value} to {target.value}"
            )
        object.__setattr__(self, "status", target)

    def _transition_publication(self, target: PublicationStatus) -> None:
        if target not in _PUBLICATION_TRANSITIONS[self.publication_status]:
            raise PublicationTransitionError(
                f"cannot transition publication status from "
                f"{self.publication_status.value} to {target.value}"
            )
        object.__setattr__(self, "publication_status", target)

    def to_manifest(self) -> dict[str, object]:
        """Project this run onto the v2 run manifest contract."""
        component = self.component_versions
        return {
            "schema_version": SCHEMA_VERSION,
            "manifest_version": MANIFEST_VERSION,
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "created_at": self.created_at.isoformat(),
            "analysis_mode": self.analysis_mode.value,
            "review_statuses": [status.value for status in self.review_statuses],
            "component_versions": {
                "engine": component.engine,
                "input_schema": component.input_schema,
                "output_schema": component.output_schema,
                "manifest_schema": component.manifest_schema,
                "rounding_profile": component.rounding_profile,
            },
            "policy_rulesets": [
                {
                    "package_id": ruleset.package_id,
                    "ruleset_id": ruleset.ruleset_id,
                    "version": ruleset.version,
                    "digest": ruleset.digest,
                }
                for ruleset in self.policy_rulesets
            ],
            "input_snapshot_digest": self.input_snapshot_digest,
            "assumption_set_digest": self.assumption_set_digest,
            "objective_digest": self.objective_digest,
            "engine_version": component.engine,
            "rounding_profile": component.rounding_profile,
            "output_digest": self.output_digest,
            "artifact_digests": list(self.artifact_digests),
            "adapter_versions": dict(self.adapter_versions),
            "digests": {
                "input": self.input_snapshot_digest,
                "rules": [ruleset.digest for ruleset in self.policy_rulesets],
                "assumptions": self.assumption_set_digest,
                "objective": self.objective_digest,
                "output": self.output_digest,
                "artifacts": list(self.artifact_digests),
            },
            "validation": dict(self.validation),
            "validation_suite": self.validation_suite,
            "validation_status": "passed",
            "warnings_count": self.warnings_count,
            "unresolved_conflicts_count": self.unresolved_conflicts_count,
            "duration_ms": self.duration_ms,
            "publication_status": self.publication_status.value,
        }

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, object]) -> "AnalysisRun":
        """Reconstruct a run from its v2 manifest, recomputing its run_id."""
        try:
            manifest = cast(dict[str, Any], manifest)
            return cls(
                parent_run_id=manifest["parent_run_id"],
                analysis_mode=AnalysisMode(manifest["analysis_mode"]),
                review_statuses=tuple(ReviewStatus(value) for value in manifest["review_statuses"]),
                component_versions=ComponentVersions(
                    engine=manifest["component_versions"]["engine"],
                    input_schema=manifest["component_versions"]["input_schema"],
                    output_schema=manifest["component_versions"]["output_schema"],
                    manifest_schema=manifest["component_versions"]["manifest_schema"],
                    rounding_profile=manifest["component_versions"]["rounding_profile"],
                ),
                policy_rulesets=tuple(
                    RulesetReference(
                        package_id=ruleset["package_id"],
                        ruleset_id=ruleset["ruleset_id"],
                        version=ruleset["version"],
                        digest=ruleset["digest"],
                    )
                    for ruleset in manifest["policy_rulesets"]
                ),
                input_snapshot_digest=manifest["input_snapshot_digest"],
                assumption_set_digest=manifest["assumption_set_digest"],
                objective_digest=manifest["objective_digest"],
                output_digest=manifest["output_digest"],
                artifact_digests=tuple(manifest["artifact_digests"]),
                adapter_versions=dict(manifest["adapter_versions"]),
                validation=dict(manifest["validation"]),
                validation_suite=manifest["validation_suite"],
                warnings_count=manifest["warnings_count"],
                unresolved_conflicts_count=manifest["unresolved_conflicts_count"],
                duration_ms=manifest["duration_ms"],
                created_at=datetime.fromisoformat(manifest["created_at"]),
                publication_status=PublicationStatus(manifest["publication_status"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise DomainValidationError(f"invalid run manifest: {error}") from error
