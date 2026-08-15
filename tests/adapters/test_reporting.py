"""Tests for JSON envelope and Markdown reporting adapters."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from china_pension_strategy.adapters.reporting.json_renderer import (
    EnvelopeSchemaError,
    EnvelopeValidator,
    OutputValidationError,
    build_envelope,
    render_json,
)
from china_pension_strategy.adapters.reporting.markdown_renderer import render_markdown
from china_pension_strategy.domain.policy import AnalysisMode, ReviewStatus
from china_pension_strategy.domain.run import (
    AnalysisRun,
    ComponentVersions,
    RulesetReference,
)
from china_pension_strategy.version import PACKAGE_VERSION

ROOT = Path(__file__).resolve().parents[2]
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64

ENVELOPE_SCHEMA = ROOT / "schemas" / "tool-envelope.schema.json"
OUTPUT_SCHEMA = ROOT / "schemas" / "analysis-output.schema.json"


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
        created_at=datetime(2026, 8, 11, 2, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return AnalysisRun(**defaults)


def make_output(**overrides) -> dict:
    output = {
        "schema_version": "2.0.0",
        "case_id": "case-001",
        "scheme": "enterprise_employee_basic_pension",
        "as_of": "2026-08-11",
        "reconciliation": {"scheme": "enterprise_employee_basic_pension", "confirmed_months": 179},
        "scenarios": {},
        "recommendation": None,
    }
    output.update(overrides)
    return output


def validate_against(schema_path: Path, document: dict) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator = __import__(
        "jsonschema", fromlist=["Draft202012Validator"]
    ).Draft202012Validator
    validator = Draft202012Validator(
        schema, format_checker=__import__("jsonschema", fromlist=["FormatChecker"]).FormatChecker()
    )
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def test_build_envelope_is_deterministic_and_embeds_run() -> None:
    run = make_run()
    first = build_envelope(
        run,
        artifact_uri="runs/run-x/output.json",
        request_id="case-001",
    )
    second = build_envelope(
        run,
        artifact_uri="runs/run-x/output.json",
        request_id="case-001",
    )
    assert first == second
    assert first["run_id"] == run.run_id
    assert first["tool_name"] == "china-pension-strategy"
    assert first["tool_version"] == PACKAGE_VERSION
    assert first["request_id"] == "case-001"
    assert first["data"]["artifact_ref"] == "runs/run-x/output.json"
    assert first["data"]["status"] == "VALIDATED"
    assert first["metrics"] == {"duration_ms": run.duration_ms, "cache_hit": False}


def test_build_envelope_provenance_uses_ruleset_digests() -> None:
    run = make_run()
    envelope = build_envelope(
        run,
        artifact_uri="runs/run-x/output.json",
        request_id="case-001",
    )
    assert envelope["provenance"] == ["cn-pension/beijing-flex/2026.1@2026.1.0:sha256:" + "b" * 64]


def test_envelope_validates_against_tool_envelope_schema() -> None:
    run = make_run()
    envelope = build_envelope(
        run,
        artifact_uri="runs/run-x/output.json",
        request_id="case-001",
    )
    validate_against(ENVELOPE_SCHEMA, envelope)


def test_render_json_validates_output_and_envelope() -> None:
    run = make_run()
    envelope = render_json(
        run,
        make_output(),
        artifact_uri="runs/run-x/output.json",
        request_id="case-001",
    )
    assert envelope["status"] == "success"
    assert envelope["data"]["artifact_ref"] == "runs/run-x/output.json"
    validate_against(ENVELOPE_SCHEMA, envelope)


def test_render_json_rejects_invalid_output_document() -> None:
    run = make_run()
    with pytest.raises(OutputValidationError):
        render_json(
            run,
            {"not": "an output"},
            artifact_uri="runs/run-x/output.json",
            request_id="case-001",
        )


def test_envelope_validator_rejects_bad_envelope() -> None:
    run = make_run()
    envelope = build_envelope(
        run,
        artifact_uri="runs/run-x/output.json",
        request_id="case-001",
    )
    del envelope["run_id"]
    validator = EnvelopeValidator()
    with pytest.raises(EnvelopeSchemaError) as excinfo:
        validator.validate(envelope)
    assert excinfo.value.code == "ENVELOPE_SCHEMA_INVALID"


def test_render_markdown_contains_run_and_case() -> None:
    run = make_run()
    rendered = render_markdown(run, make_output())
    assert run.run_id in rendered
    assert "case-001" in rendered
    assert "## Reconciliation" in rendered
    assert "## Scenario Comparison" in rendered
    assert "## Recommendation" in rendered
    assert "179" in rendered


def test_render_markdown_is_deterministic() -> None:
    run = make_run()
    assert render_markdown(run, make_output()) == render_markdown(run, make_output())


def test_render_markdown_renders_scenario_table_and_recommendation() -> None:
    run = make_run()
    output = make_output(
        scenarios={
            "continue": {
                "scenario_id": "continue",
                "feasibility": "FEASIBLE",
                "capability_refs": [],
                "horizon": ["2026-08"],
                "cash_flows": [
                    {
                        "month": "2026-08",
                        "pension": {"currency": "CNY", "amount": "1047.73"},
                        "medical": {"currency": "CNY", "amount": "459.20"},
                        "unemployment": {"currency": "CNY", "amount": "18.72"},
                        "subsidy": {"currency": "CNY", "amount": "1017.10"},
                        "net_outflow": {"currency": "CNY", "amount": "508.55"},
                        "cumulative_outflow": {"currency": "CNY", "amount": "508.55"},
                    }
                ],
                "outcomes": {
                    "ending_confirmed_months": 180,
                    "ending_gap_months": 0,
                    "total_pension": {"currency": "CNY", "amount": "1047.73"},
                    "total_medical": {"currency": "CNY", "amount": "459.20"},
                    "total_unemployment": {"currency": "CNY", "amount": "18.72"},
                    "total_subsidy": {"currency": "CNY", "amount": "1017.10"},
                    "total_net_outflow": {"currency": "CNY", "amount": "508.55"},
                },
            }
        },
        recommendation={
            "scenario_id": "continue",
            "objective": "MINIMUM_COMPLIANCE_COST",
            "capability_dependencies": [],
            "limitations": ["MVP only", "not advice"],
            "invalidators": ["policy change"],
            "review_triggers": ["annual review"],
        },
    )
    rendered = render_markdown(run, output)
    assert "### continue" in rendered
    assert "| 2026-08 |" in rendered
    assert "508.55 CNY" in rendered
    assert "## Recommendation" in rendered
    assert "not advice" in rendered
