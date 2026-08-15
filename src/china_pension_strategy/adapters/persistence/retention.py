"""Retention management: expiry checks and atomic deletion manifests.

Data expires at ``expires_at``; expired records are flagged for deletion and
their artifacts are removed with an atomically written manifest (temp sibling
file + ``os.replace``). Temporary files are cleaned up on both success and
failure paths, and restrictive permissions are applied on platforms that
support them (POSIX).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

EXPIRED_DELETION_STATUSES = ("EXPIRED", "DELETED")
_MANIFEST_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class DeletionResult:
    manifest_path: Path
    deleted_artifacts: tuple[str, ...]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RetentionManager:
    """Checks expiry and deletes expired artifacts under a base directory."""

    def __init__(
        self,
        base_dir: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
        manifest_dir: str | Path | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.manifest_dir = Path(manifest_dir) if manifest_dir is not None else self.base_dir / "manifests"
        self._clock = clock if clock is not None else _utc_now

    def is_expired(self, record: Mapping[str, Any], *, now: datetime | None = None) -> bool:
        """True when the record's deletion status or expiry time says expired."""
        if record.get("deletion_status") in EXPIRED_DELETION_STATUSES:
            return True
        raw = record.get("expires_at")
        if not isinstance(raw, str):
            return False
        try:
            expires_at = datetime.fromisoformat(raw)
        except ValueError:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        current = now if now is not None else self._clock()
        return current >= expires_at

    def flag_expired(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Return a copy of the record flagged for deletion, leaving input untouched."""
        return {**record, "deletion_status": "EXPIRED"}

    def delete_artifacts(
        self,
        artifact_paths: Sequence[str | Path],
        *,
        reason: str = "expired",
        now: datetime | None = None,
    ) -> DeletionResult:
        """Delete artifact files and record the deletion in an atomic manifest."""
        deleted: list[str] = []
        for artifact in artifact_paths:
            target = Path(artifact)
            if not target.is_absolute():
                target = self.base_dir / target
            try:
                target.unlink()
            except FileNotFoundError:
                continue
            deleted.append(self._artifact_name(target))
        current = now if now is not None else self._clock()
        manifest_id = f"deletion-{current.strftime('%Y%m%dT%H%M%S%f')}"
        manifest_path = self.manifest_dir / f"{manifest_id}.json"
        payload = {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "manifest_id": manifest_id,
            "reason": reason,
            "deleted_at": current.isoformat(),
            "count": len(deleted),
            "artifacts": sorted(deleted),
        }
        self._atomic_write_json(manifest_path, payload)
        return DeletionResult(manifest_path, tuple(sorted(deleted)))

    def enforce_permissions(self, path: str | Path) -> None:
        """Restrict permissions to 0o600 on POSIX; a no-op elsewhere."""
        if os.name == "posix":
            os.chmod(path, 0o600)

    def _artifact_name(self, target: Path) -> str:
        try:
            return target.resolve().relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            return target.as_posix()

    def _atomic_write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            descriptor, temp_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            os.close(descriptor)
            temp_path = Path(temp_name)
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            temp_path = None
            self.enforce_permissions(path)
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
