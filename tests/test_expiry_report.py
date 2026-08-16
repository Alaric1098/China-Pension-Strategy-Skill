"""Policy expiry report classification tests.

Historical packages must be listed under HISTORICAL and must NOT drive the
exit code; only non-historical (current) packages/ rules do.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "scripts" / "policy_expiry_report.py"


def _package_record(
    package_id: str,
    effective_to: str,
    *,
    historical: bool = False,
    rule_effective_to: str | None = None,
) -> dict:
    rules = [
        {
            "rule_id": "test-rule",
            "scheme": "enterprise_employee_basic_pension",
            "topic": "flexible_employment_contribution",
            "jurisdiction_role": "LOCAL_IMPLEMENTATION",
            "population_scope": "test",
            "exceptions": [],
            "effective_from": "2024-01-01",
            "effective_to": rule_effective_to,
            "transaction_from": "2026-08-14T10:00:00Z",
            "transaction_to": None,
            "legal_hierarchy": "MUNICIPAL_REGULATION",
            "explicit_override_refs": [],
            "source_refs": ["test-source"],
            "rule_type": "POLICY_RULE",
            "inputs": [],
            "conditions": [],
            "results": [],
            "parameters": {},
            "test_vectors": [],
        }
    ]
    return {
        "schema_version": "1.0.0",
        "package_id": package_id,
        "version": "1.0.0",
        "scheme": "enterprise_employee_basic_pension",
        "jurisdiction": "CN-XX",
        "topic": "flexible_employment_contribution",
        "review_status": "MVP_REVIEWED",
        "execution_modes": ["LOCAL_MVP"],
        "local_only": True,
        "historical": historical,
        "engine_compatibility": ">=0.1,<1.0",
        "effective_from": "2024-01-01",
        "effective_to": effective_to,
        "transaction_from": "2026-08-14T10:00:00Z",
        "transaction_to": None,
        "content_digest": "sha256:" + "a" * 64,
        "provenance": [],
        "rules": rules,
        "engineering_review": {
            "reviewer_id": "test",
            "reviewed_at": "2026-08-14T09:00:00Z",
            "schema_validation_passed": True,
            "rule_tests_passed": True,
        },
        "production_approval": None,
    }


def _write_packages(tmp_path: Path, records: list[dict]) -> Path:
    pkg_dir = tmp_path / "packages"
    pkg_dir.mkdir()
    for i, record in enumerate(records):
        (pkg_dir / f"pkg-{i}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
    return pkg_dir


def _run_report(packages_dir: Path, as_of: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(REPORT),
            "--as-of",
            as_of,
            "--horizon-months",
            "18",
            "--packages-dir",
            str(packages_dir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT)},
    )


def test_historical_packages_do_not_affect_exit_code(tmp_path) -> None:
    """A historical package that expired long ago lists HISTORICAL, exit 0."""
    pkg_dir = _write_packages(
        tmp_path,
        [_package_record("cn-pension/test/flex-medical-2024.1", "2025-12-31", historical=True)],
    )
    result = _run_report(pkg_dir, "2026-08-14")
    assert "HISTORICAL" in result.stdout
    assert result.returncode == 0


def test_current_expired_package_drives_exit_code(tmp_path) -> None:
    """A current package whose rule version expired keeps the gate red."""
    pkg_dir = _write_packages(
        tmp_path,
        [
            _package_record(
                "cn-pension/test/flex-employment-2026.1", None, rule_effective_to="2026-06-30"
            )
        ],
    )
    result = _run_report(pkg_dir, "2026-08-14")
    assert "[CURRENT]" in result.stdout
    assert "EXPIRED" in result.stdout
    assert result.returncode == 1


def test_mixed_scenario_counts_only_current(tmp_path) -> None:
    """Historical entries plus one expiring current rule => exit 1 with both sections."""
    pkg_dir = _write_packages(
        tmp_path,
        [
            _package_record("cn-pension/test/flex-medical-2024.1", "2025-12-31", historical=True),
            _package_record(
                "cn-pension/test/flex-medical-2026.1", None, rule_effective_to="2026-12-31"
            ),
        ],
    )
    result = _run_report(pkg_dir, "2026-08-14")
    assert "HISTORICAL" in result.stdout
    assert "[CURRENT]" in result.stdout
    assert result.returncode == 1


def test_no_expiry_returns_zero(tmp_path) -> None:
    pkg_dir = _write_packages(
        tmp_path,
        [_package_record("cn-pension/test/flex-employment-2026.1", None, rule_effective_to=None)],
    )
    result = _run_report(pkg_dir, "2026-08-14")
    assert result.returncode == 0
