"""Tests for the immutable analysis run domain and manifest projection."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from china_pension_strategy.application.manifest_validation import (
    validate_manifest_semantics,
)
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.policy import AnalysisMode, ReviewStatus
from china_pension_strategy.domain.run import (
    AnalysisRun,
    ComponentVersions,
    MissingProductionApprovalError,
    PublicationProhibitedError,
    PublicationStatus,
    PublicationTransitionError,
    RunStatus,
    RunStateTransitionError,
    RulesetReference,
)
from china_pension_strategy.ports.outbound.clock import SystemClock

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64

EXPECTED_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "manifest_version",
        "run_id",
        "parent_run_id",
        "created_at",
        "analysis_mode",
        "review_statuses",
        "component_versions",
        "policy_rulesets",
        "adapter_versions",
        "digests",
        "validation",
        "publication_status",
        "input_snapshot_digest",
        "assumption_set_digest",
        "objective_digest",
        "engine_version",
        "rounding_profile",
        "validation_suite",
        "validation_status",
        "output_digest",
        "artifact_digests",
        "warnings_count",
        "unresolved_conflicts_count",
        "duration_ms",
    }
)
EXPECTED_COMPONENT_FIELDS = frozenset(
    {"engine", "input_schema", "output_schema", "manifest_schema", "rounding_profile"}
)
EXPECTED_RULESET_FIELDS = frozenset({"package_id", "ruleset_id", "version", "digest"})
EXPECTED_DIGESTS_FIELDS = frozenset(
    {"input", "rules", "assumptions", "objective", "output", "artifacts"}
)
EXPECTED_VALIDATION_FIELDS = frozenset(
    {
        "input_schema_valid",
        "policy_schema_valid",
        "output_schema_valid",
        "invariants_valid",
    }
)

CREATED_AT = datetime(2026, 8, 11, 2, 0, tzinfo=timezone.utc)


class FixedClock:
    """Test clock returning a fixed instant, duck-typed against Clock."""

    def __init__(self, instant: datetime = CREATED_AT) -> None:
        self.instant = instant

    def now_utc(self) -> datetime:
        return self.instant


def component(engine: str = "0.1.0") -> ComponentVersions:
    return ComponentVersions(
        engine=engine,
        input_schema="1.0.0",
        output_schema="2.0.0",
        manifest_schema="2.0.0",
        rounding_profile="CNY-half-up-v1",
    )


def ruleset(digest: str = DIGEST_B) -> RulesetReference:
    return RulesetReference(
        package_id="cn-pension/beijing-flex/2026.1",
        ruleset_id="cn-pension/beijing-flex/2026.1",
        version="2026.1.0",
        digest=digest,
    )


def make_run(**overrides) -> AnalysisRun:
    defaults = dict(
        parent_run_id=None,
        analysis_mode=AnalysisMode.LOCAL_MVP,
        review_statuses=(ReviewStatus.MVP_REVIEWED,),
        component_versions=component(),
        policy_rulesets=(ruleset(),),
        input_snapshot_digest=DIGEST_A,
        assumption_set_digest=DIGEST_A,
        objective_digest=DIGEST_B,
        output_digest=DIGEST_A,
        artifact_digests=(DIGEST_B,),
        adapter_versions={"policy_repository": "0.1.0"},
        validation={
            "input_schema_valid": True,
            "policy_schema_valid": True,
            "output_schema_valid": True,
            "invariants_valid": True,
        },
        validation_suite="architecture-and-domain-v1",
        warnings_count=0,
        unresolved_conflicts_count=0,
        duration_ms=512,
        created_at=FixedClock().now_utc(),
    )
    defaults.update(overrides)
    return AnalysisRun(**defaults)


def test_run_id_is_deterministic_for_identical_inputs() -> None:
    later = make_run(created_at=CREATED_AT + timedelta(hours=8))
    assert later.run_id == make_run().run_id
    assert later != make_run()
    assert later.run_id.startswith("run-")
    assert len(later.run_id) == 4 + 64


def test_run_id_ignores_adapter_release_versions() -> None:
    released = make_run(adapter_versions={"policy_repository": "0.1.1"})

    assert released.run_id == make_run().run_id


@pytest.mark.parametrize(
    "override",
    [
        {"input_snapshot_digest": DIGEST_B},
        {"assumption_set_digest": DIGEST_B},
        {"objective_digest": DIGEST_A},
        {"component_versions": component(engine="0.2.0")},
        {"policy_rulesets": (ruleset(digest=DIGEST_A),)},
    ],
)
def test_run_id_changes_when_any_content_component_changes(override: dict) -> None:
    assert make_run(**override).run_id != make_run().run_id


def test_running_run_can_succeed() -> None:
    run = make_run()
    run.mark_succeeded()
    assert run.status is RunStatus.SUCCEEDED


@pytest.mark.parametrize(
    "transition",
    [
        lambda run: (run.mark_succeeded(), run.mark_failed()),
        lambda run: (run.mark_failed(), run.mark_succeeded()),
    ],
)
def test_illegal_status_transitions_raise_typed_error(transition) -> None:
    run = make_run()
    with pytest.raises(RunStateTransitionError) as excinfo:
        transition(run)
    assert excinfo.value.code == "RUN_STATE_TRANSITION_INVALID"
    assert isinstance(excinfo.value, DomainValidationError)


def test_run_identity_is_frozen() -> None:
    run = make_run()
    with pytest.raises(FrozenInstanceError):
        run.run_id = "run-tampered"
    with pytest.raises(FrozenInstanceError):
        run.status = RunStatus.SUCCEEDED


def test_mvp_reviewed_run_cannot_be_published() -> None:
    run = make_run()
    with pytest.raises(PublicationProhibitedError) as excinfo:
        run.publish()
    assert excinfo.value.code == "MVP_REVIEWED_PUBLICATION_PROHIBITED"
    assert run.publication_status is PublicationStatus.LOCAL_ONLY


def test_production_approved_run_can_be_published() -> None:
    run = make_run(
        analysis_mode=AnalysisMode.PRODUCTION,
        review_statuses=(ReviewStatus.PRODUCTION_APPROVED,),
    )
    run.publish()
    assert run.publication_status is PublicationStatus.PUBLISHED
    assert run.to_manifest()["publication_status"] == "PUBLISHED"


def test_publish_is_terminal() -> None:
    run = make_run(
        analysis_mode=AnalysisMode.PRODUCTION,
        review_statuses=(ReviewStatus.PRODUCTION_APPROVED,),
    )
    run.publish()
    with pytest.raises(PublicationTransitionError) as excinfo:
        run.publish()
    assert excinfo.value.code == "PUBLICATION_TRANSITION_INVALID"


def test_published_manifest_requires_production_approved() -> None:
    assert MissingProductionApprovalError.code == "PUBLISHED_REQUIRES_PRODUCTION_APPROVED"
    manifest = make_run().to_manifest()
    manifest["publication_status"] = "PUBLISHED"
    with pytest.raises(DomainValidationError):
        AnalysisRun.from_manifest(manifest)
    manifest["review_statuses"] = ["PRODUCTION_APPROVED"]
    manifest["analysis_mode"] = "PRODUCTION"
    assert AnalysisRun.from_manifest(manifest).publication_status is PublicationStatus.PUBLISHED


def test_to_manifest_matches_fixture_field_names() -> None:
    manifest = make_run().to_manifest()
    assert set(manifest) == EXPECTED_MANIFEST_FIELDS
    assert set(manifest["component_versions"]) == EXPECTED_COMPONENT_FIELDS
    assert set(manifest["policy_rulesets"][0]) == EXPECTED_RULESET_FIELDS
    assert set(manifest["digests"]) == EXPECTED_DIGESTS_FIELDS
    assert set(manifest["validation"]) == EXPECTED_VALIDATION_FIELDS
    assert manifest["schema_version"] == "2.0.0"
    assert manifest["manifest_version"] == "2.0.0"
    assert manifest["created_at"] == "2026-08-11T02:00:00+00:00"


def test_to_manifest_passes_semantic_validation() -> None:
    manifest = make_run().to_manifest()
    validate_manifest_semantics(manifest)


def test_from_manifest_round_trip_preserves_run() -> None:
    run = make_run()
    assert AnalysisRun.from_manifest(run.to_manifest()) == run


@pytest.mark.parametrize(
    "tamper",
    [
        lambda manifest: manifest.update(input_snapshot_digest="sha256:zzz"),
        lambda manifest: manifest.update(review_statuses=["UNREVIEWED"]),
        lambda manifest: manifest.update(created_at="2026-08-11T10:00:00"),
    ],
)
def test_from_manifest_rejects_invalid_manifests(tamper) -> None:
    manifest = make_run().to_manifest()
    tamper(manifest)
    with pytest.raises(DomainValidationError):
        AnalysisRun.from_manifest(manifest)


def test_system_clock_returns_aware_utc_datetime() -> None:
    now = SystemClock().now_utc()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
