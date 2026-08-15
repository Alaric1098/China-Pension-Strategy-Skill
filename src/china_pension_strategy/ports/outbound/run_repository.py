"""Outbound analysis run repository boundary."""

from pathlib import Path
from typing import Protocol

from china_pension_strategy.domain.run import AnalysisRun


class RunRepositoryError(Exception):
    """Base class for repository failures."""


class RunNotFoundError(RunRepositoryError):
    """Raised when no stored run exists for the requested run_id."""

    code = "RUN_NOT_FOUND"


class ManifestIntegrityError(RunRepositoryError):
    """Raised when a stored manifest fails integrity checks."""

    code = "MANIFEST_INTEGRITY_FAILED"


class ManifestDigestMismatchError(ManifestIntegrityError):
    """Raised when a stored manifest run_id disagrees with its content digests."""

    code = "MANIFEST_DIGEST_MISMATCH"


class ManifestSemanticsError(ManifestIntegrityError):
    """Raised when a stored manifest fails semantic consistency checks."""

    code = "MANIFEST_SEMANTICS_INVALID"


class ManifestInvalidError(ManifestIntegrityError):
    """Raised when a stored manifest is structurally invalid."""

    code = "MANIFEST_INVALID"


class RunRepository(Protocol):
    """Boundary for persisting and loading immutable analysis runs."""

    def save(self, run: AnalysisRun) -> Path:
        """Persist the run manifest atomically and return its path."""

    def load(self, run_id: str) -> AnalysisRun:
        """Load the run identified by run_id, verifying manifest integrity."""

    def exists(self, run_id: str) -> bool:
        """Return whether a stored manifest exists for run_id."""
