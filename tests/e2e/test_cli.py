"""End-to-end CLI tests: exit codes, envelopes, artifacts, and safe failures.

Each test drives the real composition root in a subprocess so that the
adapter wiring, exit-code contract, and artifact layout are exercised
exactly as a user would run them.
"""

import json
import subprocess
import sys
from pathlib import Path

from china_pension_strategy.adapters.policies.json_policy_repository import (
    canonical_content_digest,
)

ROOT = Path(__file__).resolve().parents[2]
CLI = ["-m", "china_pension_strategy.entrypoints.cli.main"]

EXPIRES_AT = "2026-12-31T00:00:00Z"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *CLI, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd or ROOT,
    )


def write_input(path: Path, **overrides: object) -> Path:
    record: dict = {
        "schema_version": "1.0.0",
        "case_id": "case-001",
        "analysis_mode": "LOCAL_MVP",
        "classification": "S2-CONFIDENTIAL",
        "purpose": "pension_strategy_analysis",
        "consent_id": "consent-001",
        "created_at": "2026-08-11T12:00:00Z",
        "expires_at": EXPIRES_AT,
        "deletion_status": "ACTIVE",
        "requested_capabilities": [
            "CONTRIBUTION_RECONCILIATION",
            "CONTRIBUTION_GAP",
            "FLEXIBLE_EMPLOYMENT_CONTRIBUTION",
            "SUBSIDY_ELIGIBILITY",
            "SUBSIDY_TIMING",
            "SCENARIO_COMPARISON",
            "RECOMMENDATION",
        ],
        "facts": [
            {
                "fact_id": "base-1",
                "fact_type": "contribution_base",
                "value": "7000.00",
                "as_of_date": "2026-08-11",
                "source_ref": "base-limits",
                "required_for": ["FLEXIBLE_EMPLOYMENT_CONTRIBUTION"],
            },
            {
                "fact_id": "agg-1",
                "fact_type": "aggregate_count",
                "value": 179,
                "as_of_date": "2026-08-11",
                "source_ref": "statement",
                "required_for": ["CONTRIBUTION_RECONCILIATION", "CONTRIBUTION_GAP"],
            },
            {
                "fact_id": "mon-1",
                "fact_type": "contribution_month",
                "value": "2026-06",
                "as_of_date": "2026-08-11",
                "source_ref": "statement",
                "required_for": ["CONTRIBUTION_RECONCILIATION"],
            },
            {
                "fact_id": "mon-2",
                "fact_type": "contribution_month",
                "value": "2026-07",
                "as_of_date": "2026-08-11",
                "source_ref": "statement",
                "required_for": ["CONTRIBUTION_RECONCILIATION"],
            },
            {
                "fact_id": "employment_difficulty_recognized",
                "fact_type": "subsidy_input",
                "value": True,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_ELIGIBILITY"],
            },
            {
                "fact_id": "employment_registration_days",
                "fact_type": "subsidy_input",
                "value": 45,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_ELIGIBILITY"],
            },
            {
                "fact_id": "has_earned_income",
                "fact_type": "subsidy_input",
                "value": True,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_ELIGIBILITY"],
            },
            {
                "fact_id": "paid_unemployment_premium_before",
                "fact_type": "subsidy_input",
                "value": True,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_ELIGIBILITY"],
            },
            {
                "fact_id": "months_to_retirement",
                "fact_type": "subsidy_input",
                "value": 36,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_TIMING"],
            },
            {
                "fact_id": "subsidy_months_used",
                "fact_type": "subsidy_input",
                "value": 0,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_TIMING"],
            },
            {
                "fact_id": "application_month",
                "fact_type": "subsidy_input",
                "value": "2026-08",
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_TIMING"],
            },
            {
                "fact_id": "pension_paid",
                "fact_type": "subsidy_input",
                "value": True,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_ELIGIBILITY"],
            },
            {
                "fact_id": "medical_paid",
                "fact_type": "subsidy_input",
                "value": True,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_ELIGIBILITY"],
            },
            {
                "fact_id": "unemployment_paid",
                "fact_type": "subsidy_input",
                "value": True,
                "as_of_date": "2026-08-11",
                "source_ref": "user",
                "required_for": ["SUBSIDY_ELIGIBILITY"],
            },
        ],
    }
    record.update(overrides)
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def run_artifacts(runs_dir: Path, run_id: str) -> dict[str, Path]:
    run_dir = runs_dir / run_id
    return {
        "manifest": run_dir / "manifest.json",
        "analysis": run_dir / "analysis.json",
    }


def analyze_and_parse(input_path: Path, runs_dir: Path) -> tuple[subprocess.CompletedProcess, dict]:
    result = run_cli("analyze", "--input", str(input_path), "--runs-dir", str(runs_dir))
    assert result.returncode == 0, result.stderr
    return result, json.loads(result.stdout)


def test_analyze_happy_path_prints_envelope_and_stores_artifacts(tmp_path: Path) -> None:
    input_path = write_input(tmp_path / "input.json")
    runs_dir = tmp_path / "runs"
    _, envelope = analyze_and_parse(input_path, runs_dir)

    assert envelope["schema_version"] == "1.0.0"
    assert envelope["tool_name"] == "china-pension-strategy"
    assert envelope["status"] == "success"
    assert envelope["errors"] == []
    assert envelope["data"]["status"] == "VALIDATED"
    run_id = envelope["data"]["run_id"]
    assert envelope["run_id"] == run_id
    assert envelope["request_id"] == "case-001"
    assert envelope["data"]["artifact_ref"] == f"runs/{run_id}/analysis.json"
    assert envelope["provenance"]

    artifacts = run_artifacts(runs_dir, run_id)
    assert artifacts["manifest"].is_file()
    assert artifacts["analysis"].is_file()
    stored = json.loads(artifacts["analysis"].read_text(encoding="utf-8"))
    assert stored["schema_version"] == "2.0.0"
    assert stored["case_id"] == "case-001"
    manifest = json.loads(artifacts["manifest"].read_text(encoding="utf-8"))
    assert manifest["expires_at"] == EXPIRES_AT


def test_requested_capability_without_output_is_reported_as_partial(tmp_path: Path) -> None:
    input_path = ROOT / "evals" / "fixtures" / "partial-beijing-benefit.json"
    runs_dir = tmp_path / "runs"

    _, envelope = analyze_and_parse(input_path, runs_dir)

    assert envelope["status"] == "partial"
    assert any(
        warning["message"].startswith("CAPABILITY_PARTIAL: PENSION_ESTIMATION")
        for warning in envelope["warnings"]
    )
    run_id = envelope["data"]["run_id"]
    stored = json.loads(
        (runs_dir / run_id / "analysis.json").read_text(encoding="utf-8")
    )
    assert "pension_estimation" not in stored
    dependencies = {
        item["capability_id"]: item["status"]
        for item in stored["recommendation"]["capability_dependencies"]
    }
    assert dependencies["PENSION_ESTIMATION"] == "PARTIAL"
    assert stored["capability_statuses"]["PENSION_ESTIMATION"] == "PARTIAL"

    rendered = run_cli(
        "render",
        "--run-id",
        run_id,
        "--runs-dir",
        str(runs_dir),
        "--format",
        "json",
    )
    assert rendered.returncode == 0, rendered.stderr
    re_envelope = json.loads(rendered.stdout)
    assert re_envelope["status"] == "partial"
    assert re_envelope["warnings"] == envelope["warnings"]


def test_unimplemented_retirement_age_capability_is_partial(tmp_path: Path) -> None:
    input_path = write_input(
        tmp_path / "input.json",
        requested_capabilities=[
            "CONTRIBUTION_RECONCILIATION",
            "CONTRIBUTION_GAP",
            "FLEXIBLE_EMPLOYMENT_CONTRIBUTION",
            "SCENARIO_COMPARISON",
            "RECOMMENDATION",
            "RETIREMENT_AGE",
        ],
    )
    runs_dir = tmp_path / "runs"

    _, envelope = analyze_and_parse(input_path, runs_dir)

    assert envelope["status"] == "partial"
    run_id = envelope["data"]["run_id"]
    stored = json.loads(
        (runs_dir / run_id / "analysis.json").read_text(encoding="utf-8")
    )
    assert stored["capability_statuses"]["RETIREMENT_AGE"] == "PARTIAL"


def test_cross_region_without_cross_region_facts_is_partial(tmp_path: Path) -> None:
    input_path = write_input(
        tmp_path / "input.json",
        requested_capabilities=[
            "CONTRIBUTION_RECONCILIATION",
            "CONTRIBUTION_GAP",
            "FLEXIBLE_EMPLOYMENT_CONTRIBUTION",
            "SCENARIO_COMPARISON",
            "RECOMMENDATION",
            "CROSS_REGION_COMPARISON",
        ],
    )
    record = json.loads(input_path.read_text(encoding="utf-8"))
    record["facts"].append(
        {
            "fact_id": "birth-only",
            "fact_type": "birth_year_month",
            "value": "1976-02",
            "as_of_date": "2026-08-11",
            "source_ref": "synthetic-input",
            "required_for": ["CROSS_REGION_COMPARISON"],
        }
    )
    input_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    _, envelope = analyze_and_parse(input_path, tmp_path / "runs")

    assert envelope["status"] == "partial"
    run_id = envelope["data"]["run_id"]
    stored = json.loads(
        (tmp_path / "runs" / run_id / "analysis.json").read_text(encoding="utf-8")
    )
    assert stored["capability_statuses"]["CROSS_REGION_COMPARISON"] == "PARTIAL"
    assert "cross_region_comparison" not in stored


def test_validate_command_accepts_input(tmp_path: Path) -> None:
    input_path = write_input(tmp_path / "input.json")
    result = run_cli("validate", "--input", str(input_path))
    assert result.returncode == 0
    assert result.stdout.strip() == "valid"


def test_policy_invalid_exits_4_without_traceback(tmp_path: Path) -> None:
    source = ROOT / "policy-data" / "packages" / "national-enterprise-pension.json"
    tampered = json.loads(source.read_text(encoding="utf-8"))
    for rule in tampered["rules"]:
        if rule["rule_id"] == "national-minimum-180-months":
            rule["conditions"][0]["value"] = 999
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()
    (packages_dir / "tampered.json").write_text(
        json.dumps(tampered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    input_path = write_input(tmp_path / "input.json")
    runs_dir = tmp_path / "runs"
    result = run_cli(
        "analyze",
        "--input",
        str(input_path),
        "--runs-dir",
        str(runs_dir),
        "--packages-dir",
        str(packages_dir),
    )
    assert result.returncode == 4
    assert "policy" in result.stderr.lower()
    assert "Traceback" not in result.stderr
    assert not (runs_dir / "manifests").exists()


def test_input_invalid_exits_3(tmp_path: Path) -> None:
    input_path = write_input(tmp_path / "input.json", consent_id="")
    result = run_cli("analyze", "--input", str(input_path), "--runs-dir", str(tmp_path / "runs"))
    assert result.returncode == 3
    assert "input" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_privacy_block_exits_5_and_produces_nothing(tmp_path: Path) -> None:
    ssn_fact = {
        "fact_id": "leaked-ssn",
        "fact_type": "subsidy_input",
        "value": "123-45-6789",
        "as_of_date": "2026-08-11",
        "source_ref": "note",
        "required_for": ["SUBSIDY_ELIGIBILITY"],
    }
    input_path = write_input(tmp_path / "input.json")
    record = json.loads(input_path.read_text(encoding="utf-8"))
    record["facts"].append(ssn_fact)
    input_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    result = run_cli("analyze", "--input", str(input_path), "--runs-dir", str(runs_dir))
    assert result.returncode == 5
    assert "privacy" in result.stderr.lower()
    assert "Traceback" not in result.stderr
    assert not runs_dir.exists()


def test_numeric_identity_card_exits_5_and_produces_nothing(tmp_path: Path) -> None:
    identity_fact = {
        "fact_id": "numeric-identity-card",
        "fact_type": "id_number",
        "value": 110101199001011237,
        "as_of_date": "2026-08-11",
        "source_ref": "synthetic-privacy-test",
        "required_for": ["CONTRIBUTION_RECONCILIATION"],
    }
    input_path = write_input(tmp_path / "input.json")
    record = json.loads(input_path.read_text(encoding="utf-8"))
    record["facts"].append(identity_fact)
    input_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    result = run_cli("analyze", "--input", str(input_path), "--runs-dir", str(runs_dir))

    assert result.returncode == 5
    assert "privacy" in result.stderr.lower()
    assert "Traceback" not in result.stderr
    assert not runs_dir.exists()


def test_privacy_redact_warns_and_redacts_stored_value(tmp_path: Path) -> None:
    phone_fact = {
        "fact_id": "phone-note",
        "fact_type": "subsidy_input",
        "value": "13800138000",
        "as_of_date": "2026-08-11",
        "source_ref": "note",
        "required_for": ["SUBSIDY_ELIGIBILITY"],
    }
    input_path = write_input(tmp_path / "input.json")
    record = json.loads(input_path.read_text(encoding="utf-8"))
    record["facts"].append(phone_fact)
    input_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    runs_dir = tmp_path / "runs"
    _, envelope = analyze_and_parse(input_path, runs_dir)
    assert any("redacted" in warning["message"] for warning in envelope["warnings"])
    run_id = envelope["data"]["run_id"]
    stored = (runs_dir / run_id / "analysis.json").read_text(encoding="utf-8")
    assert "13800138000" not in stored
    manifest = json.loads(
        (runs_dir / run_id / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["warnings_count"] == len(envelope["warnings"])


def test_render_by_run_id_markdown_and_json(tmp_path: Path) -> None:
    input_path = write_input(tmp_path / "input.json")
    runs_dir = tmp_path / "runs"
    _, envelope = analyze_and_parse(input_path, runs_dir)
    run_id = envelope["data"]["run_id"]

    markdown = run_cli(
        "render",
        "--run-id",
        run_id,
        "--runs-dir",
        str(runs_dir),
        "--format",
        "markdown",
    )
    assert markdown.returncode == 0, markdown.stderr
    assert run_id in markdown.stdout
    assert "case-001" in markdown.stdout
    assert "## Recommendation" in markdown.stdout

    rendered = run_cli(
        "render",
        "--run-id",
        run_id,
        "--runs-dir",
        str(runs_dir),
        "--format",
        "json",
    )
    assert rendered.returncode == 0, rendered.stderr
    re_envelope = json.loads(rendered.stdout)
    assert re_envelope["schema_version"] == "1.0.0"
    assert re_envelope["status"] == "success"
    assert re_envelope["data"]["artifact_ref"] == f"runs/{run_id}/analysis.json"


def test_cleanup_deletes_expired_artifacts_and_writes_deletion_manifest(
    tmp_path: Path,
) -> None:
    input_path = write_input(tmp_path / "input.json")
    runs_dir = tmp_path / "runs"
    _, envelope = analyze_and_parse(input_path, runs_dir)
    run_id = envelope["data"]["run_id"]
    artifacts = run_artifacts(runs_dir, run_id)
    assert artifacts["manifest"].is_file()
    assert artifacts["analysis"].is_file()

    kept = run_cli("cleanup", "--runs-dir", str(runs_dir), "--expires-before", "2026-09-01T00:00:00Z")
    assert kept.returncode == 0, kept.stderr
    assert artifacts["manifest"].is_file()

    cleanup = run_cli("cleanup", "--runs-dir", str(runs_dir), "--expires-before", "2027-01-01T00:00:00Z")
    assert cleanup.returncode == 0, cleanup.stderr
    assert not artifacts["manifest"].exists()
    assert not artifacts["analysis"].exists()

    manifests = sorted((runs_dir / "manifests").glob("deletion-*.json"))
    assert manifests
    deletion = json.loads(manifests[-1].read_text(encoding="utf-8"))
    assert deletion["reason"] == "expired"
    assert deletion["count"] == 2
    assert any(run_id in artifact for artifact in deletion["artifacts"])


def test_unsafe_policy_fails_safely_exit_1(tmp_path: Path) -> None:
    source = ROOT / "policy-data" / "packages" / "beijing-flex-employment.json"
    package = json.loads(source.read_text(encoding="utf-8"))
    for rule in package["rules"]:
        if rule["rule_id"] == "beijing-flex-pension-contribution":
            rule["results"][0]["value"] = {
                "kind": "EXPRESSION",
                "operator": "DIVIDE",
                "value_type": "DECIMAL",
                "operands": [
                    {
                        "kind": "REFERENCE",
                        "reference_type": "INPUT",
                        "reference_id": "contribution_base",
                        "value_type": "DECIMAL",
                    },
                    {"kind": "LITERAL", "value_type": "DECIMAL", "value": "0.00"},
                ],
            }
    package["content_digest"] = canonical_content_digest(package)
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()
    (packages_dir / "unsafe.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    input_path = write_input(tmp_path / "input.json")
    result = run_cli(
        "analyze",
        "--input",
        str(input_path),
        "--runs-dir",
        str(tmp_path / "runs"),
        "--packages-dir",
        str(packages_dir),
    )
    assert result.returncode == 1
    assert "unexpected failure" in result.stderr
    assert "Traceback" not in result.stderr
