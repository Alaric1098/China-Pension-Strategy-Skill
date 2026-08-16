"""Person-input loading from JSON with schema and governance validation.

The loader is deliberately conservative: it refuses missing consent or
insufficient classification metadata, rejects expired inputs, and never leaks
file contents into error messages (schema failures report field paths only).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from china_pension_strategy.adapters.data_root import data_root

CODE_FILE_NOT_FOUND = "INPUT_FILE_NOT_FOUND"
CODE_JSON_INVALID = "INPUT_JSON_INVALID"
CODE_SCHEMA_INVALID = "INPUT_SCHEMA_INVALID"
CODE_EXPIRED = "INPUT_EXPIRED"
CODE_CONSENT_MISSING = "INPUT_CONSENT_MISSING"
CODE_CLASSIFICATION_INSUFFICIENT = "INPUT_CLASSIFICATION_INSUFFICIENT"
CODE_PURPOSE_MISSING = "INPUT_PURPOSE_MISSING"

_DEFAULT_SCHEMA_PATH = data_root() / "schemas" / "person-input.schema.json"
_ACCEPTED_CLASSIFICATIONS = ("S2-CONFIDENTIAL", "S3-RESTRICTED")
_EXPIRED_DELETION_STATUSES = ("EXPIRED", "DELETED")


class InputError(Exception):
    """Base class for person-input loading failures."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class InputFileNotFoundError(InputError):
    def __init__(self, path: str) -> None:
        super().__init__(CODE_FILE_NOT_FOUND, f"person input file not found: {path}")


class InputJsonDecodeError(InputError):
    def __init__(self) -> None:
        super().__init__(CODE_JSON_INVALID, "person input is not valid JSON")


class InputSchemaError(InputError):
    def __init__(self, detail: str) -> None:
        super().__init__(CODE_SCHEMA_INVALID, f"person input failed schema validation: {detail}")


class InputExpiredError(InputError):
    def __init__(self) -> None:
        super().__init__(CODE_EXPIRED, "person input is expired")


class InputGovernanceError(InputError):
    """Raised when consent, classification, or purpose metadata is refused."""


class PersonInputLoader:
    """Loads and validates person-input documents from JSON files."""

    def __init__(self, schema_path: Path | None = None) -> None:
        schema_file = Path(schema_path) if schema_path is not None else _DEFAULT_SCHEMA_PATH
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        self._validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def load(self, path: str | Path, *, now: datetime | None = None) -> dict[str, Any]:
        """Load, validate, and return the person-input document.

        Raises typed InputError subclasses with stable codes; error messages
        never contain the document contents.
        """
        input_path = Path(path)
        if not input_path.is_file():
            raise InputFileNotFoundError(str(input_path))
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise InputJsonDecodeError() from error
        if not isinstance(data, dict):
            raise InputSchemaError("<root> is not an object")
        self.require_governance(data)
        self._require_schema(data)
        self._require_not_expired(data, now)
        return data

    def require_governance(self, data: dict[str, Any]) -> None:
        """Refuse input missing consent, classification, or purpose metadata."""
        if not data.get("consent_id"):
            raise InputGovernanceError(CODE_CONSENT_MISSING, "person input refuses consent_id")
        if data.get("classification") not in _ACCEPTED_CLASSIFICATIONS:
            raise InputGovernanceError(
                CODE_CLASSIFICATION_INSUFFICIENT,
                "person input classification is not S2-CONFIDENTIAL or stricter",
            )
        if data.get("purpose") != "pension_strategy_analysis":
            raise InputGovernanceError(CODE_PURPOSE_MISSING, "person input refuses purpose")

    def _require_schema(self, data: dict[str, Any]) -> None:
        errors = sorted(
            self._validator.iter_errors(data), key=lambda error: list(error.absolute_path)
        )
        if not errors:
            return
        details = "; ".join(
            "/".join(str(part) for part in error.absolute_path) or "<root>" for error in errors[:3]
        )
        raise InputSchemaError(details)

    def _require_not_expired(self, data: dict[str, Any], now: datetime | None) -> None:
        if data.get("deletion_status") in _EXPIRED_DELETION_STATUSES:
            raise InputExpiredError()
        expires_at = datetime.fromisoformat(str(data["expires_at"]))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        current = now if now is not None else datetime.now(UTC)
        if current >= expires_at:
            raise InputExpiredError()
