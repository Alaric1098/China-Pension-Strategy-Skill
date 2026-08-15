"""Deterministic privacy scanning for sensitive data.

Classifies sensitive values into ALLOW / REDACT / BLOCK decisions. The scanner
is pure and deterministic: no randomness, no external services, and every
detected item carries a safe reason string that never contains the sensitive
value itself.
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


class ScanAction(str, enum.Enum):
    ALLOW = "ALLOW"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class ScanFinding:
    """A single detected sensitive item inside scanned content."""

    category: str
    action: ScanAction
    path: tuple[str | int, ...]
    start: int
    end: int
    reason: str


@dataclass(frozen=True)
class ScanDecision:
    """Overall decision for one scanned text or record."""

    action: ScanAction
    findings: tuple[ScanFinding, ...]
    redacted: str

    @property
    def allowed(self) -> bool:
        return self.action is ScanAction.ALLOW


CATEGORY_IDENTITY_CARD = "IDENTITY_CARD"
CATEGORY_SOCIAL_SECURITY = "SOCIAL_SECURITY"
CATEGORY_BANK_CARD = "BANK_CARD"
CATEGORY_PHONE = "PHONE"
CATEGORY_QUERY_SERIAL = "QUERY_SERIAL"
CATEGORY_VERIFICATION_CODE = "VERIFICATION_CODE"
CATEGORY_MONEY = "MONEY"
CATEGORY_FILE_PATH = "FILE_PATH"
CATEGORY_ADDRESS = "ADDRESS"
CATEGORY_NAME = "NAME"
CATEGORY_FREE_TEXT = "FREE_TEXT"

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CHARS = "10X98765432"

_HAN = "\u4e00-\u9fff"

_IDENTITY_CARD_RE = re.compile(
    r"(?<!\d)\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])"
    r"(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b(?!\d)"
)
_SOCIAL_SECURITY_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{12}\b")
_BANK_CARD_RE = re.compile(r"\b\d{16,19}\b")
_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
_QUERY_SERIAL_RE = re.compile(r"\b[A-Z]{1,4}\d{8,16}\b", re.IGNORECASE)
_VERIFICATION_CODE_RE = re.compile(
    r"(?:verification code|验证码|校验码|安全码|短信码)[^\d]{0,8}(\d{4,6})",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    r"[¥￥]\s?\d+(?:,\d{3})*(?:\.\d{1,2})?"
    r"|\d+(?:,\d{3})*(?:\.\d{1,2})?\s*元"
)
_FILE_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|[/\\])(?:[A-Za-z0-9._\-\u4e00-\u9fa5]+[\\/])*"
    r"[A-Za-z0-9._\-\u4e00-\u9fa5]+"
)
_ADDRESS_RE = re.compile(
    rf"[{_HAN}]{{2,8}}(?:省|市|区|县)[{_HAN}]{{1,10}}(?:路|街|巷)"
    rf"[\d一二三四五六七八九十百]{{1,6}}号?[{_HAN}]{{0,8}}"
)
_NAME_RE = re.compile(
    rf"(?:姓名|名字|联系人|称呼|full name|name)[:：\s]{{0,4}}([{_HAN}]{{2,4}})"
    rf"|([{_HAN}]{{2,4}})(?:先生|女士|小姐|同志)",
    re.IGNORECASE,
)
_FREE_TEXT_RE = re.compile(rf"[{_HAN}]{{20,}}")

#: (category, action, regex) ordered from highest to lowest priority; a match
#: is kept only when it does not overlap any higher-priority kept match.
_PATTERNS: tuple[tuple[str, ScanAction, re.Pattern[str]], ...] = (
    (CATEGORY_IDENTITY_CARD, ScanAction.BLOCK, _IDENTITY_CARD_RE),
    (CATEGORY_SOCIAL_SECURITY, ScanAction.BLOCK, _SOCIAL_SECURITY_RE),
    (CATEGORY_BANK_CARD, ScanAction.BLOCK, _BANK_CARD_RE),
    (CATEGORY_PHONE, ScanAction.REDACT, _PHONE_RE),
    (CATEGORY_QUERY_SERIAL, ScanAction.BLOCK, _QUERY_SERIAL_RE),
    (CATEGORY_VERIFICATION_CODE, ScanAction.BLOCK, _VERIFICATION_CODE_RE),
    (CATEGORY_MONEY, ScanAction.REDACT, _MONEY_RE),
    (CATEGORY_FILE_PATH, ScanAction.BLOCK, _FILE_PATH_RE),
    (CATEGORY_ADDRESS, ScanAction.REDACT, _ADDRESS_RE),
    (CATEGORY_NAME, ScanAction.REDACT, _NAME_RE),
    (CATEGORY_FREE_TEXT, ScanAction.REDACT, _FREE_TEXT_RE),
)

_FIELD_CATEGORIES: dict[str, tuple[str, ScanAction]] = {
    "name": (CATEGORY_NAME, ScanAction.REDACT),
    "full_name": (CATEGORY_NAME, ScanAction.REDACT),
    "user_name": (CATEGORY_NAME, ScanAction.REDACT),
    "姓名": (CATEGORY_NAME, ScanAction.REDACT),
    "名字": (CATEGORY_NAME, ScanAction.REDACT),
    "联系人": (CATEGORY_NAME, ScanAction.REDACT),
    "phone": (CATEGORY_PHONE, ScanAction.REDACT),
    "mobile": (CATEGORY_PHONE, ScanAction.REDACT),
    "telephone": (CATEGORY_PHONE, ScanAction.REDACT),
    "phone_number": (CATEGORY_PHONE, ScanAction.REDACT),
    "电话": (CATEGORY_PHONE, ScanAction.REDACT),
    "手机": (CATEGORY_PHONE, ScanAction.REDACT),
    "手机号": (CATEGORY_PHONE, ScanAction.REDACT),
    "address": (CATEGORY_ADDRESS, ScanAction.REDACT),
    "住址": (CATEGORY_ADDRESS, ScanAction.REDACT),
    "地址": (CATEGORY_ADDRESS, ScanAction.REDACT),
    "id_card": (CATEGORY_IDENTITY_CARD, ScanAction.BLOCK),
    "identity_card": (CATEGORY_IDENTITY_CARD, ScanAction.BLOCK),
    "id_number": (CATEGORY_IDENTITY_CARD, ScanAction.BLOCK),
    "身份证": (CATEGORY_IDENTITY_CARD, ScanAction.BLOCK),
    "身份证号": (CATEGORY_IDENTITY_CARD, ScanAction.BLOCK),
    "bank_card": (CATEGORY_BANK_CARD, ScanAction.BLOCK),
    "银行卡": (CATEGORY_BANK_CARD, ScanAction.BLOCK),
    "卡号": (CATEGORY_BANK_CARD, ScanAction.BLOCK),
    "social_security": (CATEGORY_SOCIAL_SECURITY, ScanAction.BLOCK),
    "ssn": (CATEGORY_SOCIAL_SECURITY, ScanAction.BLOCK),
    "社保号": (CATEGORY_SOCIAL_SECURITY, ScanAction.BLOCK),
    "verification_code": (CATEGORY_VERIFICATION_CODE, ScanAction.BLOCK),
    "验证码": (CATEGORY_VERIFICATION_CODE, ScanAction.BLOCK),
    "query_serial": (CATEGORY_QUERY_SERIAL, ScanAction.BLOCK),
    "serial": (CATEGORY_QUERY_SERIAL, ScanAction.BLOCK),
    "查询单号": (CATEGORY_QUERY_SERIAL, ScanAction.BLOCK),
    "amount": (CATEGORY_MONEY, ScanAction.REDACT),
    "amounts": (CATEGORY_MONEY, ScanAction.REDACT),
    "money": (CATEGORY_MONEY, ScanAction.REDACT),
    "金额": (CATEGORY_MONEY, ScanAction.REDACT),
    "path": (CATEGORY_FILE_PATH, ScanAction.BLOCK),
    "file_path": (CATEGORY_FILE_PATH, ScanAction.BLOCK),
    "filepath": (CATEGORY_FILE_PATH, ScanAction.BLOCK),
    "source_path": (CATEGORY_FILE_PATH, ScanAction.BLOCK),
    "路径": (CATEGORY_FILE_PATH, ScanAction.BLOCK),
    "文件路径": (CATEGORY_FILE_PATH, ScanAction.BLOCK),
    "notes": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "note": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "remark": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "remarks": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "comment": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "comments": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "description": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "details": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "free_text": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "备注": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "说明": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
    "补充": (CATEGORY_FREE_TEXT, ScanAction.REDACT),
}


def _valid_identity_card(value: str) -> bool:
    """True when the 18-digit Chinese identity card checksum matches."""
    digits = value[:17]
    if not digits.isdigit():
        return False
    total = sum(int(digit) * weight for digit, weight in zip(digits, _ID_WEIGHTS))
    return value[-1].upper() == _ID_CHECK_CHARS[total % 11]


def _field_value_has_sensitive_shape(category: str, value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    text = str(value).strip()
    if not text:
        return False
    if isinstance(value, str):
        validators = {
            CATEGORY_IDENTITY_CARD: _IDENTITY_CARD_RE,
            CATEGORY_SOCIAL_SECURITY: _SOCIAL_SECURITY_RE,
            CATEGORY_BANK_CARD: _BANK_CARD_RE,
            CATEGORY_PHONE: _PHONE_RE,
            CATEGORY_QUERY_SERIAL: _QUERY_SERIAL_RE,
            CATEGORY_FILE_PATH: _FILE_PATH_RE,
        }
        if category in validators:
            return validators[category].fullmatch(text) is not None
        if category == CATEGORY_VERIFICATION_CODE:
            return re.fullmatch(r"\d{4,6}", text) is not None
        if category == CATEGORY_MONEY:
            return (
                _MONEY_RE.search(text) is not None
                or re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text.replace(",", ""))
                is not None
            )
        return True
    if not isinstance(value, int) or not text.isdigit():
        return category == CATEGORY_MONEY and isinstance(value, float)
    digit_count = len(text)
    expected_lengths = {
        CATEGORY_IDENTITY_CARD: {18},
        CATEGORY_SOCIAL_SECURITY: {12},
        CATEGORY_BANK_CARD: {16, 17, 18, 19},
        CATEGORY_PHONE: {11},
        CATEGORY_QUERY_SERIAL: set(range(9, 21)),
        CATEGORY_VERIFICATION_CODE: {4, 5, 6},
    }
    if category == CATEGORY_MONEY:
        return True
    return digit_count in expected_lengths.get(category, set())


class PrivacyScanner:
    """Detects sensitive values in text and records, deterministically."""

    def __init__(self, placeholder: str = "<{category}>") -> None:
        self._placeholder = placeholder

    def scan_text(self, text: str) -> ScanDecision:
        """Scan a single string and return the aggregate decision."""
        findings = self._findings_for_text(text, path=())
        return self._decision_for(text, findings)

    def scan_record(self, record: Mapping[str, Any]) -> tuple[ScanFinding, ...]:
        """Scan a nested record; findings carry the key/index path."""
        findings: list[ScanFinding] = []
        self._walk_record(record, (), findings)
        return tuple(sorted(findings, key=lambda f: (f.start, f.end)))

    def redact_record(self, record: Mapping[str, Any]) -> tuple[ScanDecision, dict[str, Any]]:
        """Return the aggregate decision plus a copy with values replaced."""
        findings = self.scan_record(record)
        redacted = self._replace_findings(record, findings)
        decision = self._decision_for(json.dumps(redacted, ensure_ascii=False), findings)
        return decision, redacted

    def _findings_for_text(self, text: str, path: tuple[str | int, ...]) -> list[ScanFinding]:
        findings: list[ScanFinding] = []
        kept: list[ScanFinding] = []
        for category, action, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                if category == CATEGORY_IDENTITY_CARD and not _valid_identity_card(match.group(0)):
                    continue
                if category == CATEGORY_NAME:
                    group, name = self._name_group(match)
                    start, end = match.span(group)
                    reason = "possible chinese name"
                else:
                    start, end = match.span()
                    reason = _reason_for(category)
                finding = ScanFinding(category, action, path, start, end, reason)
                if self._overlaps(finding, kept):
                    continue
                findings.append(finding)
                kept.append(finding)
        findings.sort(key=lambda f: (f.start, f.end))
        return findings

    @staticmethod
    def _name_group(match: re.Match[str]) -> tuple[int, str]:
        if match.group(1) is not None:
            return 1, match.group(1)
        return 2, match.group(2)

    @staticmethod
    def _overlaps(finding: ScanFinding, kept: list[ScanFinding]) -> bool:
        return any(
            finding.start < other.end and other.start < finding.end for other in kept
        )

    def _walk_record(
        self,
        record: Any,
        path: tuple[str | int, ...],
        findings: list[ScanFinding],
    ) -> None:
        if isinstance(record, dict):
            for key, value in record.items():
                child_path = (*path, key)
                field_policy = _FIELD_CATEGORIES.get(key)
                if key == "value" and isinstance(record.get("fact_type"), str):
                    field_policy = _FIELD_CATEGORIES.get(
                        record["fact_type"].casefold()
                    )
                if (
                    field_policy is not None
                    and not isinstance(value, (dict, list))
                    and _field_value_has_sensitive_shape(field_policy[0], value)
                ):
                    category, action = field_policy
                    text = str(value)
                    findings.append(
                        ScanFinding(
                            category,
                            action,
                            child_path,
                            0,
                            len(text),
                            f"{category} field: {key}",
                        )
                    )
                else:
                    self._walk_record(value, child_path, findings)
        elif isinstance(record, list):
            for index, value in enumerate(record):
                self._walk_record(value, (*path, index), findings)
        elif isinstance(record, str):
            findings.extend(self._findings_for_text(record, path))
        elif isinstance(record, (int, float)) and not isinstance(record, bool):
            findings.extend(
                finding
                for finding in self._findings_for_text(str(record), path)
                if finding.category == CATEGORY_IDENTITY_CARD
            )

    def _replace_findings(
        self,
        record: Any,
        findings: list[ScanFinding],
        path: tuple[str | int, ...] = (),
    ) -> Any:
        flagged = {finding.path: finding for finding in findings}
        if isinstance(record, dict):
            return {
                key: self._placeholder_for(flagged[(*path, key)])
                if (*path, key) in flagged
                else self._replace_findings(value, findings, (*path, key))
                for key, value in record.items()
            }
        if isinstance(record, list):
            return [
                self._placeholder_for(flagged[(*path, index)])
                if (*path, index) in flagged
                else self._replace_findings(value, findings, (*path, index))
                for index, value in enumerate(record)
            ]
        return record

    def _placeholder_for(self, finding: ScanFinding) -> str:
        return self._placeholder.format(category=finding.category)

    def _decision_for(self, text: str, findings: list[ScanFinding]) -> ScanDecision:
        ordered = sorted(findings, key=lambda f: (f.start, f.end))
        if any(f.action is ScanAction.BLOCK for f in ordered):
            action = ScanAction.BLOCK
        elif ordered:
            action = ScanAction.REDACT
        else:
            action = ScanAction.ALLOW
        redacted = self._apply_placeholders(text, ordered)
        return ScanDecision(action, tuple(ordered), redacted)

    def _apply_placeholders(self, text: str, findings: list[ScanFinding]) -> str:
        for finding in reversed(findings):
            placeholder = self._placeholder.format(category=finding.category)
            text = text[: finding.start] + placeholder + text[finding.end :]
        return text


def _reason_for(category: str) -> str:
    reasons = {
        CATEGORY_IDENTITY_CARD: "chinese identity card with valid checksum",
        CATEGORY_SOCIAL_SECURITY: "social security number",
        CATEGORY_BANK_CARD: "bank card number",
        CATEGORY_PHONE: "mobile phone number",
        CATEGORY_QUERY_SERIAL: "query serial number",
        CATEGORY_VERIFICATION_CODE: "verification code",
        CATEGORY_MONEY: "monetary amount",
        CATEGORY_FILE_PATH: "file path",
        CATEGORY_ADDRESS: "chinese address",
        CATEGORY_NAME: "possible chinese name",
        CATEGORY_FREE_TEXT: "long free text run",
    }
    return reasons[category]
