"""Retention manager and JSONL audit log adapter tests."""

import json
import os
import stat
from datetime import UTC, datetime

import pytest

from china_pension_strategy.adapters.audit.jsonl_audit import (
    REDACTED_PLACEHOLDER,
    AuditLog,
    safe_text,
)
from china_pension_strategy.adapters.persistence.retention import (
    RetentionManager,
)

FIXED_NOW = datetime(2026, 8, 11, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def manager(tmp_path) -> RetentionManager:
    return RetentionManager(tmp_path, clock=lambda: FIXED_NOW)


def test_expiry_boundary_and_deletion_status(manager):
    record = {"deletion_status": "ACTIVE", "expires_at": "2026-08-11T10:00:00+00:00"}

    assert manager.is_expired(record, now=FIXED_NOW)
    assert not manager.is_expired(record, now=datetime(2026, 8, 11, 9, 59, 59, tzinfo=UTC))
    assert not manager.is_expired(
        {"deletion_status": "ACTIVE", "expires_at": "2027-01-01T00:00:00+00:00"}, now=FIXED_NOW
    )
    assert not manager.is_expired({"deletion_status": "ACTIVE"}, now=FIXED_NOW)
    assert manager.is_expired({"deletion_status": "DELETED"}, now=FIXED_NOW)
    assert manager.is_expired(
        {"deletion_status": "EXPIRED", "expires_at": "2099-01-01T00:00:00+00:00"}, now=FIXED_NOW
    )


def test_flag_expired_returns_marked_copy_without_mutating_input(manager):
    original = {"case_id": "case-001", "deletion_status": "ACTIVE"}

    flagged = manager.flag_expired(original)

    assert flagged["deletion_status"] == "EXPIRED"
    assert flagged["case_id"] == "case-001"
    assert original["deletion_status"] == "ACTIVE"


def test_delete_artifacts_removes_files_and_writes_manifest(tmp_path, manager):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "facts").mkdir()
    (tmp_path / "inputs" / "case-001.json").write_text("{}", encoding="utf-8")
    (tmp_path / "facts" / "case-001.json").write_text("{}", encoding="utf-8")

    result = manager.delete_artifacts(
        ["inputs/case-001.json", "facts/case-001.json", "missing/ghost.json"]
    )

    assert result.deleted_artifacts == ("facts/case-001.json", "inputs/case-001.json")
    assert not (tmp_path / "inputs" / "case-001.json").exists()
    assert not (tmp_path / "facts" / "case-001.json").exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["reason"] == "expired"
    assert manifest["count"] == 2
    assert manifest["artifacts"] == ["facts/case-001.json", "inputs/case-001.json"]
    datetime.fromisoformat(manifest["deleted_at"])
    assert result.manifest_path.name.startswith("deletion-")


def test_manifest_write_is_atomic_and_leaves_no_temp_on_success(tmp_path, manager):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "case-001.json").write_text("{}", encoding="utf-8")

    manager.delete_artifacts(["inputs/case-001.json"])

    temp_files = [path for path in tmp_path.rglob("*.tmp")] + [
        path for path in (tmp_path / "manifests").glob(".*.tmp")
    ]
    assert temp_files == []
    assert list((tmp_path / "manifests").iterdir())


def test_manifest_write_failure_cleans_up_temp(tmp_path, manager, monkeypatch):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "case-001.json").write_text("{}", encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(
        "china_pension_strategy.adapters.persistence.retention.os.replace", fail_replace
    )

    with pytest.raises(OSError, match="synthetic replace failure"):
        manager.delete_artifacts(["inputs/case-001.json"])

    temp_files = [path for path in (tmp_path / "manifests").glob(".*.tmp")]
    assert temp_files == []
    assert list((tmp_path / "manifests").iterdir()) == []


def test_retention_files_use_restrictive_permissions_on_posix(tmp_path, manager):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "case-001.json").write_text("{}", encoding="utf-8")

    result = manager.delete_artifacts(["inputs/case-001.json"])

    manager.enforce_permissions(result.manifest_path)
    if os.name == "posix":
        assert stat.S_IMODE(result.manifest_path.stat().st_mode) == 0o600
    assert result.manifest_path.is_file()


def test_audit_append_writes_timestamped_jsonl_lines(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    log.append({"event": "input_loaded", "case_id": "case-001"})

    entries = log.entries()
    assert len(entries) == 1
    assert entries[0]["event"] == "input_loaded"
    assert entries[0]["case_id"] == "case-001"
    logged_at = datetime.fromisoformat(entries[0]["logged_at"])
    assert logged_at.tzinfo is not None


def test_audit_log_is_append_only(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        json.dumps({"event": "preexisting", "case_id": "case-000"}) + "\n", encoding="utf-8"
    )
    log = AuditLog(path)

    log.append({"event": "first"})
    log.append({"event": "second"})

    entries = log.entries()
    assert len(entries) == 3
    assert entries[0]["event"] == "preexisting"
    assert [entry["event"] for entry in entries[1:]] == ["first", "second"]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


def test_audit_redacts_sensitive_fields_including_nested_values(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    log.append(
        {
            "event": "input_loaded",
            "case_id": "case-001",
            "phone": "13800138000",
            "amount": "1400.00",
            "personal": {
                "name": "张三",
                "id_number": "11010519491231002X",
                "contact": {"phone": "13900139000"},
            },
            "tags": ["note with bank card 6222020202020202020"],
        }
    )

    content = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "13800138000" not in content
    assert "13900139000" not in content
    assert "11010519491231002X" not in content
    assert "张三" not in content
    assert "6222020202020202020" not in content
    assert content.count(REDACTED_PLACEHOLDER) == 4
    assert "case-001" in content
    assert "1400.00" in content
    assert "input_loaded" in content


def test_audit_safe_text_masks_embedded_identifiers():
    masked = safe_text(
        "call 13800138000 id 11010519491231002X card 6222020202020202020 ssn 123-45-6789"
    )

    assert "[phone]" in masked
    assert "[id-card]" in masked
    assert "[bank-card]" in masked
    assert "[ssn]" in masked
    assert "13800138000" not in masked
    assert "11010519491231002X" not in masked
    assert "6222020202020202020" not in masked
    assert "123-45-6789" not in masked
    assert safe_text("paid 1400.00元") == "paid 1400.00元"
