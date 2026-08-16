"""Tests for the filesystem-backed analysis run repository."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

import china_pension_strategy.adapters.persistence.file_run_repository as repo_module
from china_pension_strategy.adapters.persistence.file_run_repository import (
    MANIFEST_FILENAME,
    FileRunRepository,
)
from china_pension_strategy.domain.policy import AnalysisMode, ReviewStatus
from china_pension_strategy.domain.run import AnalysisRun, ComponentVersions, RulesetReference
from china_pension_strategy.ports.outbound.run_repository import (
    ManifestDigestMismatchError,
    ManifestSemanticsError,
    RunNotFoundError,
)

ROOT = Path(__file__).resolve().parents[2]
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def component() -> ComponentVersions:
    return ComponentVersions(
        engine="0.1.0",
        input_schema="1.0.0",
        output_schema="2.0.0",
        manifest_schema="2.0.0",
        rounding_profile="CNY-half-up-v1",
    )


def ruleset() -> RulesetReference:
    return RulesetReference(
        package_id="cn-pension/beijing-flex/2026.1",
        ruleset_id="cn-pension/beijing-flex/2026.1",
        version="2026.1.0",
        digest=DIGEST_B,
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
        created_at=datetime(2026, 8, 11, 2, 0, tzinfo=UTC),
    )
    defaults.update(overrides)
    return AnalysisRun(**defaults)


def assert_manifest_schema_valid(manifest: dict) -> None:
    schema = json.loads((ROOT / "schemas" / "run-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(manifest)
    )
    assert not errors, "\n".join(error.message for error in errors)


def test_save_writes_manifest_at_expected_path(tmp_path) -> None:
    run = make_run()
    repo = FileRunRepository(tmp_path)
    path = repo.save(run)
    assert path == repo.manifest_path(run.run_id)
    assert path.name == MANIFEST_FILENAME
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == run.to_manifest()
    assert_manifest_schema_valid(stored)


def test_save_is_idempotent_and_leaves_no_temp_files(tmp_path) -> None:
    run = make_run()
    repo = FileRunRepository(tmp_path)
    first = repo.save(run)
    second = repo.save(run)
    assert first == second
    assert list(first.parent.iterdir()) == [first]


def test_save_failure_removes_temp_file_without_leaving_target(tmp_path, monkeypatch) -> None:
    run = make_run()
    repo = FileRunRepository(tmp_path)

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(repo_module.os, "replace", fail_replace)
    with pytest.raises(OSError):
        repo.save(run)
    assert not repo.manifest_path(run.run_id).exists()
    assert list(repo.manifest_path(run.run_id).parent.iterdir()) == []


def test_write_manifest_rejects_semantically_invalid_manifest(tmp_path) -> None:
    repo = FileRunRepository(tmp_path)
    manifest = make_run().to_manifest()
    manifest["engine_version"] = "9.9.9"
    with pytest.raises(ManifestSemanticsError) as excinfo:
        repo.write_manifest(manifest)
    assert excinfo.value.code == "MANIFEST_SEMANTICS_INVALID"
    assert not repo.manifest_path(manifest["run_id"]).exists()


def test_load_round_trip_returns_equal_run(tmp_path) -> None:
    run = make_run()
    repo = FileRunRepository(tmp_path)
    repo.save(run)
    assert repo.load(run.run_id) == run


def test_load_missing_run_raises_not_found(tmp_path) -> None:
    repo = FileRunRepository(tmp_path)
    with pytest.raises(RunNotFoundError) as excinfo:
        repo.load("run-missing")
    assert excinfo.value.code == "RUN_NOT_FOUND"


def test_load_detects_tampered_run_id(tmp_path) -> None:
    run = make_run()
    repo = FileRunRepository(tmp_path)
    path = repo.save(run)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["run_id"] = "run-" + "f" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestDigestMismatchError) as excinfo:
        repo.load(run.run_id)
    assert excinfo.value.code == "MANIFEST_DIGEST_MISMATCH"


def test_load_rejects_semantically_invalid_stored_manifest(tmp_path) -> None:
    run = make_run()
    repo = FileRunRepository(tmp_path)
    manifest = run.to_manifest()
    manifest["rounding_profile"] = "other-profile"
    path = repo.manifest_path(run.run_id)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestSemanticsError) as excinfo:
        repo.load(run.run_id)
    assert excinfo.value.code == "MANIFEST_SEMANTICS_INVALID"


def test_exists_reflects_saved_runs(tmp_path) -> None:
    run = make_run()
    repo = FileRunRepository(tmp_path)
    assert not repo.exists(run.run_id)
    repo.save(run)
    assert repo.exists(run.run_id)
    assert not repo.exists("run-other")
