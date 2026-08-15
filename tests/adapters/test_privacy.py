"""Privacy scanner and person-input loader adapter tests."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from china_pension_strategy.adapters.input.json_input import (
    CODE_CONSENT_MISSING,
    CODE_FILE_NOT_FOUND,
    CODE_JSON_INVALID,
    CODE_SCHEMA_INVALID,
    CODE_EXPIRED,
    CODE_CLASSIFICATION_INSUFFICIENT,
    CODE_PURPOSE_MISSING,
    InputExpiredError,
    InputFileNotFoundError,
    InputGovernanceError,
    InputJsonDecodeError,
    InputSchemaError,
    PersonInputLoader,
)
from china_pension_strategy.adapters.privacy.scanner import (
    CATEGORY_ADDRESS,
    CATEGORY_BANK_CARD,
    CATEGORY_FILE_PATH,
    CATEGORY_FREE_TEXT,
    CATEGORY_IDENTITY_CARD,
    CATEGORY_MONEY,
    CATEGORY_NAME,
    CATEGORY_PHONE,
    CATEGORY_QUERY_SERIAL,
    CATEGORY_SOCIAL_SECURITY,
    CATEGORY_VERIFICATION_CODE,
    PrivacyScanner,
    ScanAction,
    ScanFinding,
)

VALID_IDENTITY_CARD = "11010519491231002X"
INVALID_CHECKSUM_ID = "110105194912310021"


@pytest.fixture
def scanner() -> PrivacyScanner:
    return PrivacyScanner()


def test_clean_text_is_allowed(scanner):
    decision = scanner.scan_text("已确认缴费月数：179个月，缺口1个月")

    assert decision.action is ScanAction.ALLOW
    assert decision.findings == ()
    assert decision.redacted == "已确认缴费月数：179个月，缺口1个月"


def test_valid_identity_card_is_blocked(scanner):
    text = f"身份证号：{VALID_IDENTITY_CARD}"

    decision = scanner.scan_text(text)

    assert decision.action is ScanAction.BLOCK
    categories = [finding.category for finding in decision.findings]
    assert CATEGORY_IDENTITY_CARD in categories
    assert VALID_IDENTITY_CARD not in decision.redacted
    identity = next(finding for finding in decision.findings if finding.category == CATEGORY_IDENTITY_CARD)
    assert identity.reason == "chinese identity card with valid checksum"


def test_identity_card_checksum_must_validate(scanner):
    decision = scanner.scan_text(f"号码：{INVALID_CHECKSUM_ID}")

    assert not any(
        finding.category == CATEGORY_IDENTITY_CARD for finding in decision.findings
    )


def test_phone_bank_card_and_social_security_detected(scanner):
    phone = scanner.scan_text("联系电话 13800138000")
    assert phone.action is ScanAction.REDACT
    assert any(f.category == CATEGORY_PHONE for f in phone.findings)
    assert "13800138000" not in phone.redacted

    bank = scanner.scan_text("银行卡号 6222020202020202020")
    assert bank.action is ScanAction.BLOCK
    assert any(f.category == CATEGORY_BANK_CARD for f in bank.findings)

    for social in ("社保号码 123-45-6789", "社保号码 110105194912"):
        decision = scanner.scan_text(social)
        assert decision.action is ScanAction.BLOCK
        assert any(f.category == CATEGORY_SOCIAL_SECURITY for f in decision.findings)


def test_name_and_address_redacted(scanner):
    text = "联系人：王小明，地址：北京市朝阳区建国路88号"

    decision = scanner.scan_text(text)

    assert decision.action is ScanAction.REDACT
    categories = {finding.category for finding in decision.findings}
    assert {CATEGORY_NAME, CATEGORY_ADDRESS} <= categories
    assert "王小明" not in decision.redacted
    assert "北京市朝阳区建国路88号" not in decision.redacted


def test_monetary_amounts_redacted(scanner):
    decision = scanner.scan_text("每月缴费 ¥1,400.00，合计 1400.00元")

    assert decision.action is ScanAction.REDACT
    assert len([f for f in decision.findings if f.category == CATEGORY_MONEY]) == 2
    assert "1400.00" not in decision.redacted


def test_file_paths_blocked(scanner):
    decision = scanner.scan_text(r"证据文件位于 C:\Users\ExampleUser\secret-2026.txt")

    assert decision.action is ScanAction.BLOCK
    assert any(f.category == CATEGORY_FILE_PATH for f in decision.findings)
    assert "secret-2026.txt" not in decision.redacted


def test_verification_code_and_query_serial_blocked(scanner):
    text = "短信验证码：4821，查询单号 CX20260811000123"

    decision = scanner.scan_text(text)

    assert decision.action is ScanAction.BLOCK
    categories = {finding.category for finding in decision.findings}
    assert {CATEGORY_VERIFICATION_CODE, CATEGORY_QUERY_SERIAL} <= categories
    assert "4821" not in decision.redacted
    assert "CX20260811000123" not in decision.redacted


def test_long_free_text_run_redacted(scanner):
    text = "这是一段包含个人生活经历描述的扩展自由文本没有任何标点符号也没有数字总共四十二个汉字"

    decision = scanner.scan_text(text)

    assert decision.action is ScanAction.REDACT
    assert any(f.category == CATEGORY_FREE_TEXT for f in decision.findings)
    assert text not in decision.redacted


def test_block_dominates_redact(scanner):
    decision = scanner.scan_text("13800138000 6222020202020202020")

    assert decision.action is ScanAction.BLOCK
    assert "6222020202020202020" not in decision.redacted


def test_scan_record_reports_nested_paths_and_redacts_record(scanner):
    record = {
        "case_id": "case-001",
        "personal": {"name": "李四", "phone": "13900139000"},
        "facts": [{"value": VALID_IDENTITY_CARD}],
        "notes": "长期服用药物记录",
        "amounts": ["1400.00元", "¥1,400.00"],
    }

    findings = scanner.scan_record(record)

    paths = {finding.path for finding in findings}
    assert ("personal", "name") in paths
    assert ("personal", "phone") in paths
    assert ("facts", 0, "value") in paths
    assert ("notes",) in paths
    assert any(f.category == CATEGORY_IDENTITY_CARD for f in findings)

    decision, redacted = scanner.redact_record(record)
    assert decision.action is ScanAction.BLOCK
    assert redacted["case_id"] == "case-001"
    assert redacted["personal"]["name"] == "<NAME>"
    assert redacted["personal"]["phone"] == "<PHONE>"
    assert redacted["facts"][0]["value"] == "<IDENTITY_CARD>"
    assert redacted["notes"] == "<FREE_TEXT>"
    assert redacted["amounts"] == ["<MONEY>", "<MONEY>"]


@given(text=st.text())
def test_scan_findings_are_bounded_and_non_overlapping(text):
    decision = PrivacyScanner().scan_text(text)

    assert decision.action in ScanAction
    spans = [(finding.start, finding.end) for finding in decision.findings]
    for start, end in spans:
        assert 0 <= start <= end <= len(text)
    for (first_start, first_end), (second_start, second_end) in zip(spans, spans[1:]):
        assert first_end <= second_start


@pytest.fixture
def loader() -> PersonInputLoader:
    return PersonInputLoader()


@pytest.fixture
def person_input() -> dict:
    return {
        "schema_version": "1.0.0",
        "case_id": "synthetic-case-001",
        "analysis_mode": "LOCAL_MVP",
        "classification": "S2-CONFIDENTIAL",
        "purpose": "pension_strategy_analysis",
        "consent_id": "consent-synthetic-001",
        "created_at": "2026-08-11T10:00:00+08:00",
        "expires_at": "2026-09-10T10:00:00+08:00",
        "deletion_status": "ACTIVE",
        "requested_capabilities": ["CONTRIBUTION_GAP"],
        "facts": [
            {
                "fact_id": "fact-pension-months",
                "fact_type": "CONFIRMED_CONTRIBUTION_MONTHS",
                "value": 179,
                "as_of_date": "2026-08-11",
                "source_ref": "synthetic-account-summary",
                "required_for": ["CONTRIBUTION_GAP"],
            }
        ],
    }


def write_input(tmp_path: Path, payload: object, name: str = "input.json") -> Path:
    target = tmp_path / name
    target.write_text(
        json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload,
        encoding="utf-8",
    )
    return target


def test_loader_returns_valid_person_input(loader, person_input, tmp_path):
    path = write_input(tmp_path, person_input)

    loaded = loader.load(path, now=datetime(2026, 9, 1, tzinfo=timezone.utc))

    assert loaded == person_input
    assert loaded["consent_id"] == "consent-synthetic-001"


def test_loader_missing_file_has_stable_code(loader, tmp_path):
    with pytest.raises(InputFileNotFoundError) as error:
        loader.load(tmp_path / "missing.json")

    assert error.value.code == CODE_FILE_NOT_FOUND


def test_loader_invalid_json_error_does_not_leak_contents(loader, tmp_path):
    path = write_input(tmp_path, "not json at all SENTINEL-99887766")

    with pytest.raises(InputJsonDecodeError) as error:
        loader.load(path)

    assert error.value.code == CODE_JSON_INVALID
    assert "SENTINEL-99887766" not in str(error.value)


def test_loader_schema_error_does_not_leak_contents(loader, person_input, tmp_path):
    invalid = dict(person_input)
    invalid["unexpected_property"] = "SENTINEL-424242"
    invalid["facts"] = [dict(person_input["facts"][0], secret_extra="SENTINEL-111111")]
    path = write_input(tmp_path, invalid)

    with pytest.raises(InputSchemaError) as error:
        loader.load(path, now=datetime(2026, 9, 1, tzinfo=timezone.utc))

    assert error.value.code == CODE_SCHEMA_INVALID
    assert "SENTINEL-424242" not in str(error.value)
    assert "SENTINEL-111111" not in str(error.value)


def test_loader_refuses_missing_or_insufficient_governance(loader, person_input, tmp_path):
    without_consent = dict(person_input)
    del without_consent["consent_id"]
    with pytest.raises(InputGovernanceError) as error:
        loader.load(write_input(tmp_path, without_consent, "no-consent.json"))
    assert error.value.code == CODE_CONSENT_MISSING

    internal = dict(person_input, classification="S1-INTERNAL")
    with pytest.raises(InputGovernanceError) as error:
        loader.load(write_input(tmp_path, internal, "internal.json"))
    assert error.value.code == CODE_CLASSIFICATION_INSUFFICIENT

    wrong_purpose = dict(person_input, purpose="marketing")
    with pytest.raises(InputGovernanceError) as error:
        loader.load(write_input(tmp_path, wrong_purpose, "purpose.json"))
    assert error.value.code == CODE_PURPOSE_MISSING


def test_loader_rejects_expired_input(loader, person_input, tmp_path):
    path = write_input(tmp_path, person_input)

    with pytest.raises(InputExpiredError) as error:
        loader.load(path, now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert error.value.code == CODE_EXPIRED

    already_deleted = dict(person_input, deletion_status="DELETED")
    with pytest.raises(InputExpiredError) as error:
        loader.load(
            write_input(tmp_path, already_deleted, "deleted.json"),
            now=datetime(2026, 8, 12, tzinfo=timezone.utc),
        )
    assert error.value.code == CODE_EXPIRED


def test_scan_record_returns_scan_findings_type():
    finding = ScanFinding(CATEGORY_PHONE, ScanAction.REDACT, ("phone",), 0, 11, "mobile phone number")

    assert finding.category == CATEGORY_PHONE
    assert finding.action is ScanAction.REDACT
