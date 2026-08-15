"""Append-only JSONL audit log with pre-logging redaction.

Audit entries are timestamped, serialized one JSON object per line, and
redacted before writing: sensitive field names are replaced with a fixed
placeholder and remaining string values are passed through :func:`safe_text`
so embedded identifiers never reach the log.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REDACTED_PLACEHOLDER = "<redacted>"

SENSITIVE_FIELD_NAMES = frozenset(
    {
        "name",
        "full_name",
        "user_name",
        "phone",
        "mobile",
        "telephone",
        "phone_number",
        "address",
        "id_card",
        "identity_card",
        "id_number",
        "bank_card",
        "card_number",
        "social_security",
        "ssn",
        "verification_code",
        "query_serial",
        "serial",
        "password",
        "token",
        "secret",
        "content",
        "raw",
        "details",
        "body",
        "text",
        "note",
        "notes",
        "remark",
        "remarks",
        "comment",
        "comments",
    }
)

_SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b1[3-9]\d{9}\b"), "[phone]"),
    (re.compile(r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|[12]\d|3[01])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"), "[id-card]"),
    (re.compile(r"\b\d{16,19}\b"), "[bank-card]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[ssn]"),
    (re.compile(r"\b[A-Za-z]{1,4}\d{8,16}\b"), "[serial]"),
)


def safe_text(value: object) -> str:
    """Render a value for logs with embedded sensitive identifiers masked."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    for pattern, placeholder in _SENSITIVE_PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


class AuditLog:
    """Append-only JSONL audit log writing one safe entry per line."""

    def __init__(
        self, path: str | Path, *, sensitive_fields: frozenset[str] | None = None
    ) -> None:
        self.path = Path(path)
        self._sensitive_fields = (
            sensitive_fields if sensitive_fields is not None else SENSITIVE_FIELD_NAMES
        )

    def append(self, entry: Mapping[str, Any]) -> None:
        """Redact, timestamp, and append one JSONL entry."""
        stamped = {"logged_at": datetime.now(timezone.utc).isoformat()}
        stamped.update(self.redact(entry))
        line = json.dumps(stamped, ensure_ascii=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()

    def entries(self) -> list[dict[str, Any]]:
        """Read all previously appended entries, in order."""
        if not self.path.is_file():
            return []
        parsed: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                parsed.append(json.loads(line))
        return parsed

    def redact(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        """Return a copy of the entry with sensitive fields redacted."""
        return {key: self._redact_value(value, key) for key, value in entry.items()}

    def _redact_value(self, value: Any, key: str) -> Any:
        if key in self._sensitive_fields:
            return REDACTED_PLACEHOLDER
        if isinstance(value, dict):
            return {child: self._redact_value(child_value, child) for child, child_value in value.items()}
        if isinstance(value, list):
            return [self._redact_value(item, key) for item in value]
        if isinstance(value, str):
            return safe_text(value)
        return value