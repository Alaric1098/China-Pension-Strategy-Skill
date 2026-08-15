"""JSON envelope rendering for analysis runs.

Produces deterministic tool envelopes that embed the run ID, pass envelope
schema validation, carry the validated analysis output, and fail safely.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.run import AnalysisRun

ENVELOPE_SCHEMA_VERSION = "1.0.0"
TOOL_NAME = "china-pension-strategy"

_SOURCE_ROOT = Path(os.path.realpath(__file__)).resolve().parents[4]
_DEFAULT_ENVELOPE_SCHEMA_PATH = _SOURCE_ROOT / "schemas" / "tool-envelope.schema.json"
_DEFAULT_OUTPUT_SCHEMA_PATH = _SOURCE_ROOT / "schemas" / "analysis-output.schema.json"


class RenderError(Exception):
    """Base class for safe renderer failures."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class EnvelopeSchemaError(RenderError):
    def __init__(self, detail: str) -> None:
        super().__init__("ENVELOPE_SCHEMA_INVALID", f"envelope schema invalid: {detail}")


class OutputValidationError(DomainValidationError):
    """Raised when an analysis output document violates its schema."""

    code = "OUTPUT_SCHEMA_INVALID"


class OutputValidator:
    """Validates analysis-output documents against the JSON Schema."""

    def __init__(self, schema_path: str | Path | None = None) -> None:
        schema_file = (
            Path(schema_path)
            if schema_path is not None
            else _DEFAULT_OUTPUT_SCHEMA_PATH
        )
        self._validator = Draft202012Validator(
            json.loads(schema_file.read_text(encoding="utf-8")),
            format_checker=FormatChecker(),
        )

    def validate(self, document: Mapping[str, Any]) -> None:
        errors = sorted(
            self._validator.iter_errors(document),
            key=lambda error: list(error.path),
        )
        if errors:
            details = "; ".join(
                "/".join(str(part) for part in error.path) or "<root>"
                for error in errors[:3]
            )
            raise OutputValidationError(details)


class EnvelopeValidator:
    """Validates tool envelopes against the tool-envelope JSON Schema."""

    def __init__(self, schema_path: str | Path | None = None) -> None:
        schema_file = (
            Path(schema_path)
            if schema_path is not None
            else _DEFAULT_ENVELOPE_SCHEMA_PATH
        )
        self._validator = Draft202012Validator(
            json.loads(schema_file.read_text(encoding="utf-8")),
            format_checker=FormatChecker(),
        )

    def validate(self, envelope: Mapping[str, Any]) -> None:
        errors = sorted(
            self._validator.iter_errors(envelope),
            key=lambda error: list(error.path),
        )
        if errors:
            details = "; ".join(
                "/".join(str(part) for part in error.path) or "<root>"
                for error in errors[:3]
            )
            raise EnvelopeSchemaError(details)


def build_envelope(
    run: AnalysisRun,
    *,
    artifact_uri: str,
    request_id: str,
    status: str = "success",
    warnings: Iterable[str] = (),
    errors: Iterable[Mapping[str, Any]] = (),
    cache_hit: bool = False,
) -> dict[str, Any]:
    """Build a deterministic tool envelope referencing the run artifact."""
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "tool_name": TOOL_NAME,
        "tool_version": run.component_versions.engine,
        "run_id": run.run_id,
        "request_id": request_id,
        "status": status,
        "data": {
            "run_id": run.run_id,
            "status": "VALIDATED",
            "artifact_ref": artifact_uri,
        },
        "warnings": [
            {"code": "WARNING", "message": warning, "related_refs": []}
            for warning in warnings
        ],
        "errors": list(errors),
        "provenance": [
            f"{reference.package_id}@{reference.version}:{reference.digest}"
            for reference in run.policy_rulesets
        ],
        "metrics": {
            "duration_ms": run.duration_ms,
            "cache_hit": cache_hit,
        },
    }


def render_json(
    run: AnalysisRun,
    output: Mapping[str, Any],
    *,
    artifact_uri: str,
    request_id: str,
    status: str | None = None,
    warnings: Iterable[str] = (),
    envelope_validator: EnvelopeValidator | None = None,
    output_validator: OutputValidator | None = None,
) -> dict[str, Any]:
    """Render and validate a JSON envelope for the run and its output."""
    warning_items = tuple(warnings)
    output_validator = output_validator or OutputValidator()
    output_validator.validate(output)
    if status is None:
        capability_statuses = output.get("capability_statuses", {})
        status = (
            "partial"
            if isinstance(capability_statuses, Mapping)
            and any(value != "AVAILABLE" for value in capability_statuses.values())
            else "success"
        )
        if status == "partial" and not warning_items:
            warning_items = tuple(
                f"CAPABILITY_PARTIAL: {capability} has status {capability_status}."
                for capability, capability_status in capability_statuses.items()
                if capability_status != "AVAILABLE"
            )
    envelope = build_envelope(
        run,
        artifact_uri=artifact_uri,
        request_id=request_id,
        status=status,
        warnings=warning_items,
    )
    envelope_validator = envelope_validator or EnvelopeValidator()
    envelope_validator.validate(envelope)
    return envelope
