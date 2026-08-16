"""Filesystem-backed analysis run repository with atomic manifest writes."""

import json
import os
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from china_pension_strategy.application.manifest_validation import (
    ManifestSemanticValidationError,
    validate_manifest_semantics,
)
from china_pension_strategy.domain.errors import DomainValidationError
from china_pension_strategy.domain.run import AnalysisRun
from china_pension_strategy.ports.outbound.run_repository import (
    ManifestDigestMismatchError,
    ManifestInvalidError,
    ManifestSemanticsError,
    RunNotFoundError,
)

MANIFEST_FILENAME = "manifest.json"


def _replace_with_retry(temp: Path, target: Path) -> None:
    """Replace ``temp`` over ``target``, tolerating transient Windows locks.

    Antivirus/indexing scans can briefly hold a freshly written sibling file,
    making ``os.replace`` fail with ``PermissionError``; retry before giving up.
    """
    for attempt in range(10):
        try:
            os.replace(temp, target)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


class FileRunRepository:
    """Stores one run manifest per run directory under a configurable root."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def manifest_path(self, run_id: str) -> Path:
        """Return the manifest file path for a run_id."""
        return self._root / run_id / MANIFEST_FILENAME

    def save(self, run: AnalysisRun) -> Path:
        """Persist the run manifest atomically after integrity gates pass."""
        return self.write_manifest(run.to_manifest())

    def write_manifest(self, manifest: Mapping[str, Any]) -> Path:
        """Atomically write a manifest, rejecting semantic inconsistencies."""
        try:
            validate_manifest_semantics(manifest)
        except ManifestSemanticValidationError as error:
            raise ManifestSemanticsError(
                f"refusing to store semantically invalid manifest: {error}"
            ) from error
        target = self.manifest_path(str(manifest["run_id"]))
        self._write_atomic(target, manifest)
        return target

    def load(self, run_id: str) -> AnalysisRun:
        """Load a stored manifest, verifying semantics and run_id integrity."""
        path = self.manifest_path(run_id)
        if not path.is_file():
            raise RunNotFoundError(f"no stored run for run_id {run_id!r}")
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            validate_manifest_semantics(manifest)
            run = AnalysisRun.from_manifest(manifest)
        except ManifestSemanticValidationError as error:
            raise ManifestSemanticsError(
                f"stored manifest for {run_id!r} fails semantic checks: {error}"
            ) from error
        except (
            DomainValidationError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            KeyError,
        ) as error:
            raise ManifestInvalidError(
                f"stored manifest for {run_id!r} is invalid: {error}"
            ) from error
        if run.run_id != manifest["run_id"]:
            raise ManifestDigestMismatchError(
                f"stored manifest for {run_id!r} run_id does not match its content digests"
            )
        return run

    def exists(self, run_id: str) -> bool:
        """Return whether a stored manifest exists for run_id."""
        return self.manifest_path(run_id).is_file()

    def _write_atomic(self, target: Path, manifest: Mapping[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f"{target.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
        try:
            temp.write_text(
                json.dumps(dict(manifest), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _replace_with_retry(temp, target)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
