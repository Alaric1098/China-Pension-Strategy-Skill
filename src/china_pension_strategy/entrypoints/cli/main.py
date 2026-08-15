"""Command-line entrypoint for the China Pension Strategy skill.

The CLI only wires adapters to use cases; it contains no business logic.
Exit codes are stable and documented:

- 0: success
- 1: unexpected runtime failure (no raw stack trace is printed)
- 2: usage error
- 3: person input invalid
- 4: policy package invalid
- 5: privacy scan blocked the input
- 6: rendering failed
- 7: run not found
- 8: cleanup failed
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from china_pension_strategy.adapters.audit.jsonl_audit import AuditLog
from china_pension_strategy.adapters.input.json_input import (
    InputError,
    PersonInputLoader,
)
from china_pension_strategy.adapters.persistence.file_run_repository import (
    FileRunRepository,
)
from china_pension_strategy.adapters.persistence.retention import RetentionManager
from china_pension_strategy.adapters.policies.json_policy_repository import (
    JsonPolicyRepository,
    PolicyPackageError,
)
from china_pension_strategy.adapters.privacy.scanner import (
    PrivacyScanner,
    ScanAction,
)
from china_pension_strategy.adapters.regions import create_region_adapter
from china_pension_strategy.adapters.regions.beijing import RegionMappingError
from china_pension_strategy.adapters.reporting.json_renderer import (
    EnvelopeValidator,
    OutputValidationError,
    OutputValidator,
    RenderError,
    render_json,
)
from china_pension_strategy.adapters.reporting.markdown_renderer import render_markdown
from china_pension_strategy.application.analyze import analyze
from china_pension_strategy.ports.outbound.clock import SystemClock

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE = 2
EXIT_INPUT_INVALID = 3
EXIT_POLICY_INVALID = 4
EXIT_PRIVACY_BLOCKED = 5
EXIT_RENDER_FAILED = 6
EXIT_RUN_NOT_FOUND = 7
EXIT_CLEANUP_FAILED = 8


class CliError(Exception):
    """Safe CLI failure with a stable exit code."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="china-pension-strategy",
        description="Beijing pension strategy analysis (LOCAL_MVP).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a person input file")
    validate.add_argument("--input", required=True, help="person input JSON file")
    validate.add_argument("--schema", default=None, help="person-input schema file")

    analyze_parser = subparsers.add_parser("analyze", help="run a pension analysis")
    analyze_parser.add_argument("--input", required=True, help="person input JSON file")
    analyze_parser.add_argument("--runs-dir", required=True, help="directory for run artifacts")
    analyze_parser.add_argument("--packages-dir", default=None, help="policy packages directory")
    analyze_parser.add_argument("--schema", default=None, help="person-input schema file")
    analyze_parser.add_argument("--engine", default="0.1.1", help="engine version (semver)")
    analyze_parser.add_argument("--audit", default=None, help="JSONL audit file")

    render = subparsers.add_parser("render", help="render a stored run")
    render.add_argument("--run-id", required=True, help="run ID to render")
    render.add_argument("--runs-dir", required=True, help="directory with run artifacts")
    render.add_argument("--format", choices=("json", "markdown"), default="markdown")
    render.add_argument("--output", default=None, help="output file (default stdout)")

    cleanup = subparsers.add_parser("cleanup", help="delete expired run artifacts")
    cleanup.add_argument("--runs-dir", required=True, help="directory with run artifacts")
    cleanup.add_argument("--expires-before", required=True, help="ISO-8601 cutoff datetime")

    return parser


def _load_input(
    input_path: str,
    schema_path: str | None,
) -> dict:
    try:
        return PersonInputLoader(
            schema_path=Path(schema_path) if schema_path else None,
        ).load(input_path)
    except InputError as error:
        raise CliError(EXIT_INPUT_INVALID, f"input error ({error.code}): {error}") from error


def _scan_input(record: Mapping[str, object]) -> tuple[dict, list[str]]:
    decision, redacted = PrivacyScanner().redact_record(record)
    if decision.action is ScanAction.BLOCK:
        raise CliError(
            EXIT_PRIVACY_BLOCKED,
            "privacy scan blocked the input; no analysis produced",
        )
    if decision.action is ScanAction.REDACT:
        return redacted, ["privacy scan redacted fields before analysis"]
    return dict(record), []


def _load_packages(packages_dir: str | None) -> JsonPolicyRepository:
    try:
        repository = JsonPolicyRepository(packages_dir=packages_dir or None)
        tuple(repository.list_packages())
        return repository
    except PolicyPackageError as error:
        raise CliError(EXIT_POLICY_INVALID, f"policy error ({error.code}): {error}") from error


def _run_analyze(
    input_path: str,
    runs_dir: str,
    packages_dir: str | None,
    schema_path: str | None,
    engine: str,
    audit_path: str | None,
) -> int:
    record = _load_input(input_path, schema_path)
    redacted, warnings = _scan_input(record)
    try:
        region = str(redacted.get("region", "beijing"))
        adapter = create_region_adapter(region, engine_version=engine)
        request = adapter.to_analysis_request(redacted)
    except RegionMappingError as error:
        raise CliError(EXIT_INPUT_INVALID, f"region mapping error ({error.code}): {error}") from error

    policy_repository = _load_packages(packages_dir)
    run_directory = Path(runs_dir)
    run_repository = FileRunRepository(run_directory)
    result = analyze(
        request,
        policy_repository,
        run_repository,
        SystemClock(),
        initial_warnings=warnings,
    )
    run_dir = run_directory / result.run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_uri = f"runs/{result.run.run_id}/analysis.json"
    (run_dir / "analysis.json").write_text(
        json.dumps(result.output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = dict(result.run.to_manifest())
    manifest["warnings"] = list(result.warnings)
    expires_at = record.get("expires_at")
    if isinstance(expires_at, str):
        manifest["expires_at"] = expires_at
    run_repository.write_manifest(manifest)
    envelope = render_json(
        result.run,
        result.output,
        artifact_uri=artifact_uri,
        request_id=request.case_id,
        status=result.envelope_status,
        warnings=result.warnings,
        envelope_validator=EnvelopeValidator(),
        output_validator=OutputValidator(),
    )
    if audit_path:
        try:
            AuditLog(audit_path).append(
                {
                    "event": "run_created",
                    "run_id": result.run.run_id,
                    "case_id": request.case_id,
                    "created_at": result.run.created_at.isoformat(),
                    "warnings": result.warnings,
                }
            )
        except OSError:
            raise CliError(EXIT_RUNTIME_ERROR, "failed to write audit record")
    sys.stdout.write(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return EXIT_OK


def _run_render(
    run_id: str,
    runs_dir: str,
    output_format: str,
    output_path: str | None,
) -> int:
    repository = FileRunRepository(Path(runs_dir))
    try:
        run = repository.load(run_id)
        manifest = json.loads(
            repository.manifest_path(run_id).read_text(encoding="utf-8")
        )
    except Exception as error:
        raise CliError(EXIT_RUN_NOT_FOUND, f"run not found: {run_id}") from error
    artifact_file = Path(runs_dir) / run_id / "analysis.json"
    if not artifact_file.is_file():
        raise CliError(EXIT_RENDER_FAILED, f"no output artifact for run {run_id}")
    try:
        output = json.loads(artifact_file.read_text(encoding="utf-8"))
        if output_format == "json":
            rendered = (
                json.dumps(
                    render_json(
                        run,
                        output,
                        artifact_uri=f"runs/{run_id}/analysis.json",
                        request_id=output.get("case_id", run_id),
                        warnings=manifest.get("warnings", ()),
                        envelope_validator=EnvelopeValidator(),
                        output_validator=OutputValidator(),
                    ),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        else:
            rendered = render_markdown(run, output) + "\n"
    except (RenderError, OutputValidationError, KeyError, TypeError, ValueError) as error:
        raise CliError(EXIT_RENDER_FAILED, f"rendering failed: {error}") from error
    if output_path:
        Path(output_path).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return EXIT_OK


def _run_cleanup(runs_dir: str, expires_before: str) -> int:
    try:
        cutoff = datetime.fromisoformat(expires_before)
    except ValueError as error:
        raise CliError(EXIT_USAGE, f"invalid expires-before timestamp: {expires_before}") from error
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    base = Path(runs_dir)
    manager = RetentionManager(base)
    expired_artifacts: list[str] = []
    for run_dir in sorted(base.iterdir()):
        manifest = run_dir / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            stored = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        record = {
            "expires_at": stored.get("expires_at"),
            "deletion_status": stored.get("deletion_status"),
        }
        if manager.is_expired(record, now=cutoff):
            expired_artifacts.append(f"{run_dir.name}/manifest.json")
            output_artifact = run_dir / "analysis.json"
            if output_artifact.is_file():
                expired_artifacts.append(f"{run_dir.name}/analysis.json")
    try:
        result = manager.delete_artifacts(
            expired_artifacts,
            reason="expired",
            now=cutoff,
        )
    except Exception as error:
        raise CliError(EXIT_CLEANUP_FAILED, f"cleanup failed: {error}") from error
    print(f"deleted {len(result.deleted_artifacts)} artifact(s) for {result.manifest_path}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            _load_input(args.input, args.schema)
            print("valid")
            return EXIT_OK
        if args.command == "analyze":
            return _run_analyze(
                args.input,
                args.runs_dir,
                args.packages_dir,
                args.schema,
                args.engine,
                args.audit,
            )
        if args.command == "render":
            return _run_render(args.run_id, args.runs_dir, args.format, args.output)
        if args.command == "cleanup":
            return _run_cleanup(args.runs_dir, args.expires_before)
    except CliError as error:
        print(f"error: {error.message}", file=sys.stderr)
        return error.code
    except Exception as error:  # noqa: BLE001 - safe failure boundary
        print(f"error: unexpected failure: {type(error).__name__}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    parser.error(f"unknown command: {args.command}")
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
